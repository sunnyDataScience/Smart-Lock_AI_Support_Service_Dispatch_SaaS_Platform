#!/usr/bin/env bash
# check-prereqs.sh — 檢查本機是否有 Docker / Node / Python / 等工具
# 沒有就明確告訴使用者去裝什麼，並 exit 1。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

log_title "前置工具檢查"

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
      git)     version=$(git --version 2>/dev/null) ;;
      curl)    version=$(curl --version 2>/dev/null | head -1 | awk '{print $1, $2}') ;;
      *) version="installed" ;;
    esac
    log_ok "$name — $version"
  else
    if [[ "$optional" == "yes" ]]; then
      log_warn "$name — 未安裝（選用，$install_hint）"
    else
      log_err "$name — 未安裝。請執行：$install_hint"
      ALL_OK=0
    fi
  fi
}

check_tool docker  "Docker"  "從 https://www.docker.com/products/docker-desktop 下載"
check_tool node    "Node.js" "brew install node 或 https://nodejs.org（建議 v20+）"
check_tool npm     "npm"     "通常隨 Node.js 一起安裝"
check_tool python3 "Python3" "macOS 內建；或 brew install python@3.11"
check_tool git     "Git"     "macOS 內建 / brew install git"
check_tool curl    "curl"    "macOS 內建"

# Docker daemon 是否在跑
if have docker; then
  if docker info >/dev/null 2>&1; then
    log_ok "Docker daemon 已啟動"
  else
    log_err "Docker daemon 未啟動 — 請打開 Docker Desktop"
    ALL_OK=0
  fi
fi

# Node 版本檢查（建議 >= 20）
if have node; then
  node_major=$(node --version | sed 's/v//' | cut -d. -f1)
  if (( node_major < 20 )); then
    log_warn "Node 版本 < 20，建議升級至 v20+（目前 v$node_major）"
  fi
fi

# Python 版本檢查（建議 >= 3.10）
if have python3; then
  py_minor=$(python3 -c 'import sys; print(sys.version_info[1])')
  if (( py_minor < 10 )); then
    log_warn "Python 版本 < 3.10，agent 需要 Python 3.10+（目前 3.$py_minor）"
  fi
fi

if (( ALL_OK == 1 )); then
  echo ""
  log_ok "前置檢查全部通過"
  exit 0
else
  echo ""
  log_err "請先補齊上述工具後再執行"
  exit 1
fi
