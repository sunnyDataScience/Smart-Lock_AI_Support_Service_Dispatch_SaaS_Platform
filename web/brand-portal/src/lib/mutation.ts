/**
 * ADR-034 mutation contract。
 *
 * 目標不是取代 React state library，而是把四個不可分割的語意固定下來：
 * 1. 同一次使用者 action 的 retry 沿用同一 idempotency key。
 * 2. optimistic 僅允許低風險、可逆操作。
 * 3. offline／5xx／409 一律 rollback，不留下假成功 UI。
 * 4. 成功後只失效宣告的 query key；不在此層廣域清空所有 GET。
 */

export type OptimisticMutationRisk =
  | "notification"
  | "preference"
  | "favorite"
  | "ui-state";

export type SensitiveMutationRisk =
  | "quote"
  | "work-order-status"
  | "dispatch"
  | "settlement"
  | "refund"
  | "permission"
  | "consent";

export type MutationRisk = OptimisticMutationRisk | SensitiveMutationRisk;

export interface MutationStateAdapter<TState> {
  read(): TState;
  write(next: TState): void;
}

export interface MutationExecutionContext {
  /** 同一次使用者 action 的穩定 UUID；直接作為 API Idempotency-Key。 */
  actionId: string;
  /** 首次為 1；同 action retry 遞增，但 actionId 不變。 */
  attempt: number;
}

interface MutationContractBase<TState, TResult> {
  id: string;
  state: MutationStateAdapter<TState>;
  execute(context: MutationExecutionContext): Promise<TResult>;
  /**
   * 伺服器成功後，以目前 state（可能含同時間其他更新）與 response 對帳。
   * 未提供時保留目前 state。
   */
  reconcile?: (current: TState, result: TResult) => TState;
  invalidateKeys?: readonly string[];
  invalidate?: (keys: readonly string[]) => void;
  actionIdFactory?: () => string;
}

export interface OptimisticMutationContract<TState, TResult>
  extends MutationContractBase<TState, TResult> {
  mode: "optimistic";
  risk: OptimisticMutationRisk;
  optimisticPatch(current: TState): TState;
  /**
   * 預設回復完整 snapshot。若 state 可能同時接收 WS／跨 tab 更新，應提供 targeted
   * rollback，只撤銷本 action 變更，避免覆蓋無關更新。
   */
  rollback?: (current: TState, snapshot: TState, error: unknown) => TState;
}

export interface ServerConfirmedMutationContract<TState, TResult>
  extends MutationContractBase<TState, TResult> {
  mode: "server-confirmed";
  risk: MutationRisk;
  optimisticPatch?: never;
  rollback?: never;
}

export type MutationContract<TState, TResult> =
  | OptimisticMutationContract<TState, TResult>
  | ServerConfirmedMutationContract<TState, TResult>;

export interface MutationOutcome<TResult> {
  actionId: string;
  result: TResult;
}

export interface MutationAction<TResult> {
  readonly actionId: string;
  readonly attempts: number;
  run(): Promise<MutationOutcome<TResult>>;
  /** 與 run 相同，但名稱明確提醒 caller 會沿用原 actionId。 */
  retry(): Promise<MutationOutcome<TResult>>;
}

interface ConflictLike {
  status?: unknown;
  errorCode?: unknown;
  details?: unknown;
  message?: unknown;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

export class MutationConflictError extends Error {
  readonly actionId: string;
  readonly errorCode: string;
  readonly currentVersion: string | number | null;
  readonly current: unknown;
  readonly cause: unknown;

  constructor(actionId: string, error: ConflictLike) {
    const details = asRecord(error.details);
    super(
      typeof error.message === "string"
        ? error.message
        : "資料已被其他操作更新，請重新載入後再試。",
    );
    this.name = "MutationConflictError";
    this.actionId = actionId;
    this.errorCode =
      typeof error.errorCode === "string"
        ? error.errorCode
        : "CONCURRENT_MODIFICATION";
    const version = details?.current_version;
    this.currentVersion =
      typeof version === "string" || typeof version === "number"
        ? version
        : null;
    this.current = details?.current;
    this.cause = error;
  }

  static is(error: unknown): error is MutationConflictError {
    return error instanceof MutationConflictError;
  }
}

const SERVER_CONFIRMED_RISKS = new Set<MutationRisk>([
  "quote",
  "work-order-status",
  "dispatch",
  "settlement",
  "refund",
  "permission",
  "consent",
]);

function newActionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function normalizeMutationError(error: unknown, actionId: string): unknown {
  const candidate = asRecord(error);
  if (candidate?.status === 409) {
    return new MutationConflictError(actionId, candidate);
  }
  return error;
}

export function createMutationAction<TState, TResult>(
  contract: MutationContract<TState, TResult>,
): MutationAction<TResult> {
  if (
    contract.mode === "optimistic" &&
    SERVER_CONFIRMED_RISKS.has(contract.risk)
  ) {
    throw new Error(
      `${contract.id}: ${contract.risk} mutation 必須使用 server-confirmed`,
    );
  }

  const actionId = (contract.actionIdFactory ?? newActionId)();
  let attempt = 0;
  let inFlight: Promise<MutationOutcome<TResult>> | null = null;

  const execute = (): Promise<MutationOutcome<TResult>> => {
    if (inFlight) return inFlight;

    attempt += 1;
    const snapshot = contract.state.read();
    if (contract.mode === "optimistic") {
      contract.state.write(contract.optimisticPatch(snapshot));
    }

    inFlight = contract
      .execute({ actionId, attempt })
      .then((result) => {
        if (contract.reconcile) {
          contract.state.write(
            contract.reconcile(contract.state.read(), result),
          );
        }
        const keys = contract.invalidateKeys ?? [];
        if (keys.length > 0) contract.invalidate?.(keys);
        return { actionId, result };
      })
      .catch((error: unknown) => {
        if (contract.mode === "optimistic") {
          const current = contract.state.read();
          contract.state.write(
            contract.rollback
              ? contract.rollback(current, snapshot, error)
              : snapshot,
          );
        }
        throw normalizeMutationError(error, actionId);
      })
      .finally(() => {
        inFlight = null;
      });

    return inFlight;
  };

  return {
    actionId,
    get attempts() {
      return attempt;
    },
    run: execute,
    retry: execute,
  };
}
