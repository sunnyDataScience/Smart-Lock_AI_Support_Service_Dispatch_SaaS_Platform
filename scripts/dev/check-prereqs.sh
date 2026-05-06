#!/usr/bin/env bash
# scripts/dev/check-prereqs.sh — Verify local toolchain readiness
#
# 檢查本機是否齊備 dev/dev-up.sh 與 dev/dev-up-gcp.sh 所需工具。
# 沒有就明確告訴使用者去裝什麼，並 exit 1。
#
# Usage:
#   ./scripts/dev/check-prereqs.sh

set -euo pipefail

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_BOLD=$'\033[1m'
else
  C_RESET=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_BOLD=''
fi

ok()   { printf '%s✓%s %s\n'  "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s⚠%s %s\n'  "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf '%s✗%s %s\n'  "$C_RED" "$C_RESET" "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

ALL_OK=1

check_tool() {
  local cmd="$1" name="$2" install_hint="$3" optional="${4:-no}"
  if have "$cmd"; then
    local version=""
    case "$cmd" in
      docker)  version=$(docker --version 2>/dev/null | head -1) ;;
      node)    version=$(node --version 2>/dev/null) ;;
      npm)     version=$(npm --version 2>/dev/null) ;;
      python3) version=$(python3 --version 2>/dev/null) ;;
      uv)      version=$(uv --version 2>/dev/null) ;;
      git)     version=$(git --version 2>/dev/null) ;;
      curl)    version=$(curl --version 2>/dev/null | head -1 | awk '{print $1, $2}') ;;
      gcloud)  version=$(gcloud --version 2>/dev/null | head -1) ;;
      ngrok)   version=$(ngrok --version 2>/dev/null | head -1) ;;
      *)       version="installed" ;;
    esac
    ok "$name — $version"
  else
    if [[ "$optional" == "yes" ]]; then
      warn "$name — 未安裝（選用，$install_hint）"
    else
      err "$name — 未安裝。請執行：$install_hint"
      ALL_OK=0
    fi
  fi
}

printf '\n%s=== 前置工具檢查 ===%s\n' "$C_BOLD" "$C_RESET"

# 必要工具
check_tool docker  "Docker"  "從 https://www.docker.com/products/docker-desktop 下載"
check_tool uv      "uv"      "pip install --user uv 或 pipx install uv（Python 套件管理，唯一真路）"
check_tool node    "Node.js" "建議透過 nvm 安裝 v20+：nvm install 20"
check_tool npm     "npm"     "通常隨 Node.js 一起安裝"
check_tool python3 "Python3" "macOS 內建；或 brew install python@3.11"
check_tool git     "Git"     "macOS 內建 / brew install git"
check_tool curl    "curl"    "macOS 內建"

# 選用工具（依情境而定）
check_tool gcloud  "gcloud" "情境 B（連 GCP Cloud SQL）才需要：brew install --cask google-cloud-sdk" yes
check_tool ngrok   "ngrok"  "本機 LINE webhook 才需要：brew install ngrok 或 https://ngrok.com/download" yes

# Docker daemon 是否在跑
if have docker; then
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon 已啟動"
  else
    err "Docker daemon 未啟動 — 請打開 Docker Desktop"
    ALL_OK=0
  fi
fi

# Node 版本檢查（建議 >= 20）
if have node; then
  node_major=$(node --version | sed 's/v//' | cut -d. -f1)
  if (( node_major < 20 )); then
    warn "Node 版本 < 20，建議升級至 v20+（目前 v$node_major）"
  fi
fi

# Python 版本檢查（uv workspace 鎖 3.11）
if have python3; then
  py_minor=$(python3 -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)
  if (( py_minor < 10 )); then
    warn "Python 版本 < 3.10，agent / api 需要 Python 3.10+（目前 3.$py_minor）"
  fi
fi

if (( ALL_OK == 1 )); then
  echo ""
  ok "前置檢查全部通過"
  exit 0
else
  echo ""
  err "請先補齊上述工具後再執行"
  exit 1
fi
