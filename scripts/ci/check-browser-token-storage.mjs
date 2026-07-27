#!/usr/bin/env node

/**
 * ADR-034 / CR-0190：阻擋 browser storage 再次持久化 access/refresh token。
 * 舊 key 字串只允許出現在 api.ts 的一次性 migration/cleanup；任何 setItem 寫 token、
 * SSO fragment 或 WS/SSE URL query 帶 token 都直接讓 CI fail。
 */

import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const portals = ["brand-portal", "tech-portal", "platform-console", "landing"];
const violations = [];

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(?:ts|tsx|js|mjs)$/.test(entry.name) ? [path] : [];
  });
}

for (const portal of portals) {
  const apiPath = resolve(root, "web", portal, "src/lib/api.ts");
  const source = readFileSync(apiPath, "utf8");
  for (const pattern of [
    /localStorage\.setItem\(\s*["']smartlock\.access_token/g,
    /localStorage\.setItem\(\s*["']smartlock\.refresh_token/g,
    /writeToken\(\s*STORAGE_KEYS\.(?:access|refresh)/g,
  ]) {
    if (pattern.test(source)) violations.push(`${portal}/src/lib/api.ts: ${pattern}`);
  }
  for (const path of sourceFiles(resolve(root, "web", portal, "src"))) {
    const productionSource = readFileSync(path, "utf8");
    for (const pattern of [
      /searchParams\.set\(\s*["'](?:access_token|refresh_token)["']/g,
      /sso-complete#/g,
      /[?&](?:access_token|refresh_token)=/g,
      /[?&]state=smartlock(?:&|["'`]|$)/g,
    ]) {
      if (pattern.test(productionSource)) {
        violations.push(`${path}: token entered browser URL (${pattern})`);
      }
    }
  }
}

for (const portal of ["brand-portal", "tech-portal", "platform-console"]) {
  const callbackPath = resolve(
    root,
    "web",
    portal,
    "src/app/auth/callback/route.ts",
  );
  const source = readFileSync(callbackPath, "utf8");
  if (/sso-complete#/.test(source) || /fragment\s*=/.test(source)) {
    violations.push(`${portal} SSO callback 仍把 token 放進 fragment`);
  }
  if (
    !source.includes('searchParams.get("state")') ||
    !source.includes("request.cookies.get(OAUTH_STATE_COOKIE)") ||
    !source.includes("state !== expectedState") ||
    !source.includes("redirect_uri: redirectUri")
  ) {
    violations.push(`${portal} SSO callback 缺 OAuth state/redirect_uri 驗證`);
  }
  const startSource = readFileSync(
    resolve(root, "web", portal, "src/app/auth/start/route.ts"),
    "utf8",
  );
  if (
    !startSource.includes("randomUUID()") ||
    !startSource.includes("httpOnly: true") ||
    !startSource.includes('authorize.searchParams.set("state", state)') ||
    !startSource.includes('path: "/auth"') ||
    !startSource.includes("maxAge: 600")
  ) {
    violations.push(`${portal} SSO start 缺短效 HttpOnly 隨機 state`);
  }
}

if (violations.length) {
  process.stderr.write(`Browser token storage contract failed:\n${violations.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("Browser token storage contract: OK\n");
