import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src/", import.meta.url));
const forbiddenImports = [
  "react",
  "react-dom",
  "next",
  "tailwind",
  "lucide",
  "recharts",
];
const forbiddenNames = [
  "component",
  "theme",
  "i18n",
  "layout",
  "page",
  "routepolicy",
  "navigation",
];

async function files(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const result = [];
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) result.push(...(await files(path)));
    else if (entry.name.endsWith(".ts")) result.push(path);
  }
  return result;
}

const violations = [];
for (const path of await files(root)) {
  const rel = relative(root, path);
  const normalized = rel.toLowerCase().replaceAll("-", "");
  if (forbiddenNames.some((name) => normalized.includes(name))) {
    violations.push(`${rel}: forbidden portal/UI filename`);
  }
  const source = await readFile(path, "utf8");
  for (const dependency of forbiddenImports) {
    const pattern = new RegExp(`from\\\\s+["']${dependency}(?:/[^"']*)?["']`);
    if (pattern.test(source)) violations.push(`${rel}: forbidden import ${dependency}`);
  }
  if (/["']use client["']/.test(source) || /JSX\./.test(source)) {
    violations.push(`${rel}: browser UI directive/type forbidden`);
  }
}

if (violations.length) {
  process.stderr.write(`${violations.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write("shared-contract boundary: OK\n");
