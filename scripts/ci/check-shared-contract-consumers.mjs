import { readFile, stat } from "node:fs/promises";
import { createHash } from "node:crypto";

const root = new URL("../../", import.meta.url);
const portals = ["brand-portal", "tech-portal", "platform-console", "landing"];
const expected =
  "file:../shared-contract/smartlock-shared-contract-0.1.0.tgz";
const errors = [];
const tarball = await readFile(
  new URL("web/shared-contract/smartlock-shared-contract-0.1.0.tgz", root),
);
const expectedIntegrity = `sha512-${createHash("sha512").update(tarball).digest("base64")}`;

const shared = JSON.parse(
  await readFile(new URL("web/shared-contract/package.json", root), "utf8"),
);
if (shared.name !== "@smartlock/shared-contract" || shared.version !== "0.1.0") {
  errors.push("shared package name/version drift");
}
for (const name of Object.keys(shared.dependencies ?? {})) {
  if (/^(react|react-dom|next|tailwind|lucide|recharts)/.test(name)) {
    errors.push(`shared package forbidden dependency: ${name}`);
  }
}

for (const portal of portals) {
  const dir = new URL(`web/${portal}/`, root);
  const pkg = JSON.parse(await readFile(new URL("package.json", dir), "utf8"));
  if (pkg.dependencies?.["@smartlock/shared-contract"] !== expected) {
    errors.push(`${portal}: dependency is not pinned vendored 0.1.0`);
  }
  const lock = JSON.parse(
    await readFile(new URL("package-lock.json", dir), "utf8"),
  );
  const locked = lock.packages?.["node_modules/@smartlock/shared-contract"];
  if (locked?.resolved !== expected) {
    errors.push(`${portal}: lockfile missing pinned tarball`);
  }
  if (locked?.integrity !== expectedIntegrity) {
    errors.push(`${portal}: lockfile integrity does not match vendored tarball`);
  }
  const facade = new URL("src/types/api.generated.ts", dir);
  if ((await stat(facade)).size > 500) {
    errors.push(`${portal}: generated facade contains duplicated contract`);
  }
  const api = await readFile(new URL("src/lib/api.ts", dir), "utf8");
  if (!api.includes("@smartlock/shared-contract/errors")) {
    errors.push(`${portal}: RFC7807 decoder not shared`);
  }
  if (api.includes("export interface ApiErrorResponse")) {
    errors.push(`${portal}: duplicate ApiErrorResponse remains`);
  }
}

if (errors.length) {
  process.stderr.write(`${errors.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write("shared-contract consumers: OK\n");
