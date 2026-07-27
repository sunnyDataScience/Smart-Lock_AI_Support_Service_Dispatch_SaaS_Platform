# @smartlock/shared-contract

ADR-039 的窄共享套件，只能包含 API generated types、RFC7807 error、
mutation/idempotency/conflict、capability 與 session facade 契約。

禁止放入 React／Next UI、theme、i18n、route policy、portal navigation 或站台業務流程。
四站各自以 lockfile 固定 `0.1.0` 的 vendored tarball；正式 registry 可用時，將相同
tarball 發布至 Artifact Registry npm repository，不改 package 內容。
