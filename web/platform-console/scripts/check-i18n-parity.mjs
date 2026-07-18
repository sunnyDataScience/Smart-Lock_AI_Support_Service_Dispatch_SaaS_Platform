#!/usr/bin/env node
/**
 * i18n 鍵數比對回歸檢查 — zh-TW / en 兩份 messages 的巢狀鍵集合必須完全相等。
 *
 * UAT W6-2 收尾要求:每次新增文案必同步兩語系;缺鍵時 translate() 會
 * fallback 到預設語系(en 模式看到中文)或直接露出 key path,都算回歸。
 *
 * 用法:node scripts/check-i18n-parity.mjs(或 npm run check:i18n)
 * 鍵集合不相等時非零退出,列出雙向差集。
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const messagesDir = join(root, "src", "i18n", "messages");

function loadMessages(name) {
  return JSON.parse(readFileSync(join(messagesDir, name), "utf8"));
}

function flattenKeys(obj, prefix = "") {
  const keys = new Set();
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      for (const k of flattenKeys(value, path)) keys.add(k);
    } else {
      keys.add(path);
    }
  }
  return keys;
}

const zh = flattenKeys(loadMessages("zh-TW.json"));
const en = flattenKeys(loadMessages("en.json"));

const onlyZh = [...zh].filter((k) => !en.has(k)).sort();
const onlyEn = [...en].filter((k) => !zh.has(k)).sort();

if (onlyZh.length > 0 || onlyEn.length > 0) {
  console.error(`i18n 鍵數比對失敗:zh-TW ${zh.size} 鍵 / en ${en.size} 鍵`);
  if (onlyZh.length > 0) {
    console.error(`\n只存在於 zh-TW(${onlyZh.length} 鍵):`);
    for (const k of onlyZh) console.error(`  - ${k}`);
  }
  if (onlyEn.length > 0) {
    console.error(`\n只存在於 en(${onlyEn.length} 鍵):`);
    for (const k of onlyEn) console.error(`  - ${k}`);
  }
  process.exit(1);
}

console.log(`i18n 鍵數比對通過:zh-TW / en 各 ${zh.size} 鍵,集合完全相等。`);
