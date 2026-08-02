"""四站台 .env 必須維持 symlink 形式（2026-08-02 資安掃描）。

`web/{brand-portal,tech-portal,platform-console,landing}/.env` 這四個路徑
**已在版控中**，但存的是 symlink 本身（內容為字串 `../../.env`），
不是目標檔案的內容——所以目前**沒有**機密外洩，根 `.env` 也確實未進版控。

風險在於「已追蹤」這件事本身：`.gitignore` 的 `.env` / `.env.*` 規則
**對已追蹤的路徑無效**。任何人只要把其中一個 symlink 換成實體檔案
（例如想給某站台單獨設定），那個檔案就會被 `git add` 收進去——
而根 `.env` 目前有 9 個 `*_KEY` / `*_SECRET` / `*_TOKEN` 之類的變數。

symlink 進版控是**刻意的便利設計**（clone 之後四站台自動共用根 `.env`），
移除它會打壞開發流程。所以這裡不移除，改成擋住「退化成實體檔案」。

若某站台日後真的需要獨立的 env，正確做法是新增
`web/<站台>/.env.local`（未追蹤）而不是把這個 symlink 實體化。
"""

from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.unit

# git 的 symlink mode。實體檔案是 100644 / 100755。
_SYMLINK_MODE = "120000"

_TRACKED_ENV_SYMLINKS = (
    "web/brand-portal/.env",
    "web/tech-portal/.env",
    "web/platform-console/.env",
    "web/landing/.env",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    ).stdout


@pytest.mark.parametrize("path", _TRACKED_ENV_SYMLINKS)
def test_tracked_env_is_still_a_symlink(path: str):
    """實體化其中任何一個，就會把根 .env 的機密一起 commit 進去。"""
    out = _git("ls-files", "-s", "--", path).strip()
    if not out:
        pytest.skip(f"{path} 已不在版控（可能被刻意移除，非本測試要擋的退化）")
    mode = out.split()[0]
    assert mode == _SYMLINK_MODE, (
        f"{path} 的 git mode 是 {mode}（實體檔案），不是 symlink。\n"
        f"這會讓根 .env 的機密被 commit——.gitignore 對已追蹤路徑無效。\n"
        f"若該站台需要獨立設定，請改用未追蹤的 web/<站台>/.env.local。"
    )


def test_root_env_is_not_tracked():
    """根 .env 本身永遠不可進版控——它是那四個 symlink 的目標。"""
    tracked = _git("ls-files", "--", ".env").strip()
    assert not tracked, f".env 進版控了：{tracked}"


def test_no_other_real_env_file_sneaks_in():
    """除了 *.example 與已知的部署參數檔，不該有其他 .env 實體檔進版控。"""
    allowed = {
        ".env.example",
        ".env.gcp.example",
        ".env.local.example",
        "agent/.env.example",
        # 品牌部署參數（非機密，是 build-time 的站台設定）
        "scripts/deploy/brands/locksmart.env",
    }
    offenders = []
    for line in _git("ls-files", "-s").splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue
        mode, path = parts[0], parts[3]
        if not (path.endswith(".env") or ".env." in path.rsplit("/", 1)[-1]):
            continue
        if path in allowed or mode == _SYMLINK_MODE:
            continue
        offenders.append(f"{path} (mode={mode})")
    assert not offenders, (
        "有非預期的 .env 實體檔進版控，請確認裡面沒有機密：\n  " + "\n  ".join(offenders)
    )
