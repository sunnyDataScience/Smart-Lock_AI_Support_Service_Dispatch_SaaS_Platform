import { api, queryCachePrefix, tenantPath } from "./api";
import { cacheInvalidate } from "./cache";
import { createMutationAction, type MutationAction } from "./mutation";

export type PreferenceKey =
  | "saved_views"
  | "table_columns"
  | "default_filters"
  | "notification_preferences"
  | "favorites";

export interface UserPreference<T = unknown> {
  id: string;
  portal: "brand";
  preference_key: PreferenceKey;
  value: T;
  version: number;
  last_action_id: string;
  updated_at: string;
}

export interface SavedView {
  id: string;
  label: string;
  route: string;
}

interface PreferenceEnvelope<T> {
  data: T;
}

export async function listPreferences(): Promise<UserPreference[]> {
  const response = await api.get<PreferenceEnvelope<UserPreference[]>>(
    tenantPath("/me/preferences"),
  );
  return response.data;
}

export async function listSavedViews(): Promise<SavedView[]> {
  const preference = (await listPreferences()).find(
    (item) => item.preference_key === "saved_views",
  );
  if (!preference || !Array.isArray(preference.value)) return [];
  return preference.value.filter(
    (item): item is SavedView =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as SavedView).id === "string" &&
      typeof (item as SavedView).label === "string" &&
      typeof (item as SavedView).route === "string" &&
      (item as SavedView).route.startsWith("/"),
  );
}

/**
 * 偏好寫入是 ADR-034 的真實 CAS reference：同一 action retry 保持 actionId；
 * 409 由 mutation contract 正規化並 rollback，不 silent overwrite。
 */
export function createPreferenceMutation<T>(options: {
  key: PreferenceKey;
  current: UserPreference<T> | null;
  value: T;
  write(next: UserPreference<T> | null): void;
}): MutationAction<PreferenceEnvelope<UserPreference<T>>> {
  const { key, current, value, write } = options;
  const listPath = tenantPath("/me/preferences");
  return createMutationAction({
    id: `preference.${key}`,
    mode: "optimistic",
    risk: "preference",
    state: {
      read: () => current,
      write,
    },
    optimisticPatch: (snapshot) =>
      snapshot
        ? { ...snapshot, value }
        : ({
            id: "optimistic",
            portal: "brand",
            preference_key: key,
            value,
            version: 0,
            last_action_id: "",
            updated_at: new Date().toISOString(),
          } as UserPreference<T>),
    execute: ({ actionId }) =>
      api.put<PreferenceEnvelope<UserPreference<T>>>(
        tenantPath(`/me/preferences/${encodeURIComponent(key)}`),
        {
          value,
          expected_version: current?.version ?? 0,
        },
        { idempotencyKey: actionId, invalidate: false },
      ),
    reconcile: (_state, response) => response.data,
    invalidateKeys: [queryCachePrefix(listPath)],
    invalidate: (keys) => {
      for (const keyPrefix of keys) cacheInvalidate(keyPrefix);
    },
  });
}
