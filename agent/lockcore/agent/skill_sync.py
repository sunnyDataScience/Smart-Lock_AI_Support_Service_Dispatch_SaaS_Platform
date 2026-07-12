"""SkillSync —— 品牌庫 skill 物化到 workspace overlay（CR-0167 / LiveSkill）。

把 saas.skill_revision 的 published 版本拉下來、落盤到 ``workspace/skills/``，
SkillsLoader 的 overlay 機制（skills.py:_skill_entries_from_dir，workspace 優先於
builtin）即讓 agent 下一 turn 用到新知識——**不重佈**。

設計約束（CR-0167 §5.5）：
- **lockcore 核心零改動**：本檔是新增 DI 元件，SkillsLoader 一行不動。
- **HD-3 DB 直讀**：agent 以 POSTGRES_URI 連品牌庫（RAG 已在用同一連線環境）。
- **HD-4 60s 輪詢**：查 skill_bundle.published_stamp，變了才全量重拉。
- **fail-soft**：DB/tenant 未配置或連線失敗 → 不動現有 overlay、log warning，
  agent 續用上次物化版或 image builtin（對齊 RAG RAG_UNAVAILABLE 哲學）。
- **原子換裝**：materialize 到版本目錄 + symlink 原子重指，turn 進行中讀檔不撕裂。

未配置（缺 POSTGRES_URI 或 tenant_id）→ SkillSync.enabled=False，行為與現況完全一致。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("lockcore.skill_sync")

_DEFAULT_POLL_SECONDS = 60


class SkillSync:
    def __init__(
        self,
        *,
        workspace: Path,
        uri: str | None,
        tenant_id: str | None,
        poll_interval: int = _DEFAULT_POLL_SECONDS,
    ) -> None:
        self.workspace = Path(workspace)
        self.uri = uri or ""
        self.tenant_id = (tenant_id or "").strip()
        self.poll_interval = poll_interval
        self.enabled = bool(self.uri and self.tenant_id)
        self._last_stamp: int | None = None
        self._task: asyncio.Task | None = None
        self._version_seq = 0
        # workspace/skills 是 SkillsLoader.workspace_skills（overlay 讀取點）
        self._skills_link = self.workspace / "skills"

    async def start(self) -> None:
        """啟動：先做一次同步（block 到 overlay 就位），再起背景輪詢。

        fail-soft：任何失敗都不 raise——啟動失敗只代表沒有 DB overlay，
        agent 照常以 builtin 服務。
        """
        if not self.enabled:
            logger.info(
                "SkillSync 未啟用（缺 %s）→ 使用 image builtin skills（行為不變）",
                "POSTGRES_URI" if not self.uri else "tenant_id",
            )
            return
        try:
            await self._sync_once()
        except Exception:  # noqa: BLE001 — 啟動同步失敗不致命
            logger.warning("SkillSync 啟動同步失敗（fail-soft，續用 builtin）", exc_info=True)
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "SkillSync 啟用：tenant=%s… poll=%ss → workspace/skills overlay",
            self.tenant_id[:8], self.poll_interval,
        )

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self.poll_interval)
            try:
                await self._sync_once()
            except Exception:  # noqa: BLE001 — 單輪失敗不終止輪詢
                logger.warning("SkillSync 輪詢同步失敗（fail-soft，下輪重試）", exc_info=True)

    async def _sync_once(self) -> bool:
        """查 stamp；變了才全量重拉並物化。回傳是否有換裝。"""
        stamp = await self._fetch_stamp()
        if stamp is None:
            return False  # 無 bundle 記錄 = 此租戶尚未發佈任何 skill → 不動 overlay
        if stamp == self._last_stamp:
            return False
        skills = await self._fetch_published_skills()
        if not skills:
            logger.info("SkillSync：stamp=%s 但無 published skill → 保留現況", stamp)
            self._last_stamp = stamp
            return False
        self._materialize(skills)
        self._last_stamp = stamp
        logger.info("SkillSync 換裝完成：stamp=%s，%d 個 skill", stamp, len(skills))
        return True

    # ── DB 讀取（psycopg async，autocommit）───────────────────────────────────

    async def _fetch_stamp(self) -> int | None:
        from psycopg import AsyncConnection

        async with await AsyncConnection.connect(self.uri, autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT published_stamp FROM saas.skill_bundle WHERE tenant_id = %s::uuid",
                (self.tenant_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else None

    async def _fetch_published_skills(self) -> dict[str, dict]:
        """{ skill_name: {rel_path: content} }（僅 status='published'）。"""
        from psycopg import AsyncConnection

        async with await AsyncConnection.connect(self.uri, autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT skill_name, files FROM saas.skill_revision "
                "WHERE tenant_id = %s::uuid AND status = 'published'",
                (self.tenant_id,),
            )
            rows = await cur.fetchall()
        return {r[0]: (r[1] or {}) for r in rows}

    # ── 原子物化（版本目錄 + symlink 重指）────────────────────────────────────

    def _materialize(self, skills: dict[str, dict]) -> None:
        self._version_seq += 1
        version_dir = self.workspace / f".skills-v{self._version_seq}"
        if version_dir.exists():
            shutil.rmtree(version_dir, ignore_errors=True)
        version_dir.mkdir(parents=True, exist_ok=True)

        for skill_name, files in skills.items():
            self._write_skill(version_dir, skill_name, files)

        # 原子重指：symlink swap（os.replace 對 symlink 於 POSIX 為原子操作）
        self._atomic_symlink(version_dir, self._skills_link)
        self._gc_old_versions(keep=version_dir.name)

    def _write_skill(self, version_dir: Path, skill_name: str, files: dict) -> None:
        """落盤單一 skill。二次防禦：service 端已驗 path traversal，此處再擋一次。"""
        skill_root = version_dir / skill_name
        for rel_path, content in files.items():
            if not self._safe_rel(rel_path):
                logger.warning("SkillSync 略過非法路徑 %r（skill=%s）", rel_path, skill_name)
                continue
            target = skill_root / rel_path
            # 確認落點仍在 skill_root 內（symlink/traversal 兜底）
            try:
                target.resolve().relative_to(skill_root.resolve())
            except (ValueError, OSError):
                logger.warning("SkillSync 略過越界路徑 %r（skill=%s）", rel_path, skill_name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content if isinstance(content, str) else str(content), encoding="utf-8")

    @staticmethod
    def _safe_rel(rel_path: str) -> bool:
        if not rel_path or rel_path.startswith("/") or "\\" in rel_path or "\x00" in rel_path:
            return False
        return all(seg not in ("", ".", "..") for seg in rel_path.split("/"))

    @staticmethod
    def _atomic_symlink(target_dir: Path, link_path: Path) -> None:
        tmp_link = link_path.parent / (link_path.name + ".tmp")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        os.symlink(target_dir.name, tmp_link)  # 相對 symlink（同層）
        os.replace(tmp_link, link_path)        # 原子換裝

    def _gc_old_versions(self, keep: str) -> None:
        for p in self.workspace.glob(".skills-v*"):
            if p.name != keep and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
