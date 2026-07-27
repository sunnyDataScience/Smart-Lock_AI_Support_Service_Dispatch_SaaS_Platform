/** RFC7807 + legacy extension member 的唯一 decoder。 */
export interface ApiErrorResponse {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  error_code?: string;
  message?: string;
  details?: unknown;
  request_id?: string;
  timestamp?: string;
}

export function deriveErrorCode(type: string | undefined): string | undefined {
  if (!type) return undefined;
  const match = /^urn:smartlock:error:(.+)$/.exec(type);
  return match?.[1]?.toUpperCase();
}

export function decodeApiError(
  status: number,
  value: unknown,
): {
  message: string;
  errorCode: string;
  details?: unknown;
  requestId?: string;
} {
  const body =
    typeof value === "object" && value !== null
      ? (value as ApiErrorResponse)
      : {};
  return {
    message: body.detail ?? body.message ?? body.title ?? `HTTP ${status}`,
    errorCode:
      body.error_code ?? deriveErrorCode(body.type) ?? "UNKNOWN",
    details: body.details,
    requestId: body.request_id ?? body.instance,
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(status: number, body: ApiErrorResponse | unknown) {
    const decoded = decodeApiError(status, body);
    super(decoded.message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = decoded.errorCode;
    this.details = decoded.details;
    this.requestId = decoded.requestId;
  }
}
