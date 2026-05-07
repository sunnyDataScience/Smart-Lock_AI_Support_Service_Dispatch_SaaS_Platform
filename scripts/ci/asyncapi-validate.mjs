#!/usr/bin/env node
/**
 * scripts/ci/asyncapi-validate.mjs — AsyncAPI envelope validator
 *
 * 對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §10 #22 與 §14。
 * 用 @asyncapi/parser 解析 docs/02-design/specs/asyncapi.yaml，驗證：
 *   1. spec 本身語法 / 結構合法（標準 spec lint，補 spectral 看不到的事）
 *   2. 列出所有 channel + payload 形狀（給 reviewer 看）
 *   3. （未來）驗證 tests/golden/events/*.json 對應 channel 的 envelope
 *
 * 用法：
 *   cd scripts/ci && npm install      # 首次裝 @asyncapi/parser
 *   node scripts/ci/asyncapi-validate.mjs
 *   node scripts/ci/asyncapi-validate.mjs --quiet    # 只報錯，不列 channel
 *
 * 設計原則：
 *   - 純驗證，不修改 spec；CI 失敗時印明確 line:col
 *   - 跨平台：用 Node fs/path（不用 bash glob）
 */

import { Parser } from '@asyncapi/parser';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..');
const SPEC_PATH = resolve(REPO_ROOT, 'docs/02-design/specs/asyncapi.yaml');

const QUIET = process.argv.includes('--quiet');

const log = (...args) => console.log('\x1b[36m[asyncapi]\x1b[0m', ...args);
const warn = (...args) => console.warn('\x1b[33m[asyncapi]\x1b[0m', ...args);
const err = (...args) => console.error('\x1b[31m[asyncapi]\x1b[0m', ...args);

if (!existsSync(SPEC_PATH)) {
  err(`AsyncAPI spec not found: ${SPEC_PATH}`);
  process.exit(1);
}

log(`spec: ${SPEC_PATH}`);

const parser = new Parser();
const specYaml = readFileSync(SPEC_PATH, 'utf8');

const { document, diagnostics } = await parser.parse(specYaml);

// ── 1. 語法 / 結構錯誤 ────────────────────────────────────────────
const errors = diagnostics.filter((d) => d.severity === 0);
const warnings = diagnostics.filter((d) => d.severity === 1);

if (errors.length > 0) {
  err(`✗ ${errors.length} error(s) in spec:`);
  for (const e of errors) {
    err(`  - ${e.code}: ${e.message}`);
    if (e.range?.start) {
      err(`    at line ${e.range.start.line + 1}:${e.range.start.character + 1}`);
    }
  }
  process.exit(1);
}

if (warnings.length > 0 && !QUIET) {
  warn(`${warnings.length} warning(s):`);
  for (const w of warnings) {
    warn(`  - ${w.code}: ${w.message}`);
  }
}

if (!document) {
  err('✗ Parser returned no document (unknown failure)');
  process.exit(1);
}

// ── 2. 列出 channel（AsyncAPI 2.x：operations API 因版本差異不便用，
//      只列 channel id；channel-level publish/subscribe 細節由 spectral 守） ──
if (!QUIET) {
  log(`✓ spec valid: AsyncAPI ${document.version()}, ${document.info().title()}`);
  const channels = document.channels();
  log(`  channels: ${channels.length}`);
  for (const ch of channels) {
    log(`    - ${ch.id()}`);
  }
}

log(`✓ AsyncAPI envelope validation passed (0 error, ${warnings.length} warning)`);
process.exit(0);
