import { describe, expect, it } from "vitest";

import {
  ApiError,
  decodeApiError,
  hasCapability,
  isSessionClaims,
} from "../src/index";

describe("shared security contracts", () => {
  it("decodes RFC7807 and legacy extensions consistently", () => {
    const decoded = decodeApiError(409, {
      type: "urn:smartlock:error:concurrent_modification",
      detail: "version mismatch",
      details: [{ current_version: 4 }],
      request_id: "req-1",
    });
    expect(decoded).toEqual({
      message: "version mismatch",
      errorCode: "CONCURRENT_MODIFICATION",
      details: [{ current_version: 4 }],
      requestId: "req-1",
    });
    expect(new ApiError(409, { detail: "x" }).name).toBe("ApiError");
  });

  it("requires both grant and required context", () => {
    const grants = new Set(["work_orders.read"] as const);
    expect(
      hasCapability(
        grants,
        {
          requiredCapability: "work_orders.read",
          contextRequirement: "tenant",
        },
        { role: "dispatcher", tenantId: null },
      ),
    ).toBe(false);
  });

  it("validates the session facade without accepting token material", () => {
    expect(
      isSessionClaims({
        userId: "u1",
        role: "admin",
        tenantId: "t1",
        portal: "brand",
      }),
    ).toBe(true);
    expect(isSessionClaims({ accessToken: "secret" })).toBe(false);
  });
});
