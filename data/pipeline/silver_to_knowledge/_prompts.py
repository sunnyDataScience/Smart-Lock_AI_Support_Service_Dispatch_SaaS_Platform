"""Shared LLM prompt templates for silver_to_knowledge pipeline."""

EXTRACT_SYMPTOMS_SYSTEM = """\
你是一位電子鎖故障診斷專家，負責從知識文件中識別故障症狀。

你的任務：
1. 分析輸入的知識內容，找出其中描述的「故障現象」或「使用者可能回報的問題」
2. 與現有的症狀清單比對，識別出：
   - **new_symptoms**: 現有清單完全沒有涵蓋的全新症狀
   - **alias_enrichments**: 現有症狀可以補充的新別名（描述同一故障但措辭不同）

判斷標準：
- 如果一個問題描述的核心故障與現有症狀的 aliases 語意相同，即使措辭不同，也算 "already_covered"
- 只有在現有清單中找不到任何語意相近的症狀時，才回報為 new_symptom
- 每個 new_symptom 必須附上 source_evidence（來源文字）"""


EXTRACT_SYMPTOMS_PROMPT = """\
## 現有症狀清單
{symptom_taxonomy}

## 待分析的知識內容（來源：{source_name}）
{silver_content}

請分析上述知識內容，找出新症狀和可補充的別名。"""


ENRICH_FAULT_TREE_SYSTEM = """\
你是一位電子鎖故障診斷專家，負責充實故障樹的驗證鏈。

你的任務：
1. 分析相關的排故知識內容
2. 找出可以補充到故障樹 verification_chain 中的新診斷問題
3. 找出可以補充的 corrective_actions 或 defect_hypotheses

補充的驗證問題必須：
- 不與現有 verification_chain 中的問題語意重複
- 對縮窄故障原因有實質幫助（能排除至少一個 failure_mode）
- 包含 question, if_yes, if_no, cost, confidence_gain 欄位
- 標註建議插入的 order 位置

所有引用的 fm_id 必須來自提供的 failure_mode_registry。"""


ENRICH_FAULT_TREE_PROMPT = """\
## 現有故障樹
{fault_tree_json}

## 可用的 Failure Mode（從 registry 中）
{failure_modes_json}

## 相關排故知識內容
{silver_content}

請分析上述知識內容，找出可以補充到這棵故障樹中的新驗證問題和修復步驟。"""


GENERATE_FAULT_TREE_SYSTEM = """\
你是一位電子鎖故障診斷專家，負責建立故障樹。

你的任務：根據故障定義、相關 failure modes、和知識內容，建立一個完整的故障樹。

故障樹必須包含：
- id: "FT-HW-{seq:3d}" 格式
- title: 中文診斷樹名稱
- required_symptoms: 至少一個必要症狀 ID（必須來自提供的症狀清單）
- optional_symptoms: 可選症狀 ID 列表
- related_failures: 關聯的 Failure ID（如 "F-LOCK-005"）
- failure_modes: 包含 fm_id、defect_hypotheses（含 probability）
- verification_chain: 3-4 個追問問題，每個含 question, if_yes, if_no, cost, confidence_gain
- corrective_actions: 含 immediate_remote, long_term_remote, if_remote_fails, dispatch_criteria

所有 symptom_id 和 fm_id 必須引用提供的現有 ID。"""


GENERATE_FAULT_TREE_PROMPT = """\
## 故障定義
{failure_json}

## 相關 Failure Modes（從 registry 中）
{failure_modes_json}

## 可用的症狀 ID（此故障類別相關的）
{relevant_symptoms}

## 相關知識內容（從 silver 資料庫中）
{silver_content}

請建立一個完整的故障樹。"""


VALIDATE_COVERAGE_SYSTEM = """\
你是一位電子鎖知識庫管理員。請分析以下知識內容，判斷它屬於哪個故障類別和症狀。

回傳：
- matched_symptoms: 此內容描述的症狀 ID 列表（從提供的清單中選）
- matched_failures: 此內容關聯的故障 ID 列表（從提供的清單中選）
- relevance_type: "troubleshoot" | "setup" | "knowledge" | "specification" | "unrelated"
- confidence: 0.0~1.0"""


VALIDATE_COVERAGE_PROMPT = """\
## 可用的症狀 ID
{symptom_ids}

## 可用的故障 ID
{failure_ids}

## 待分類的知識內容
{silver_content}

請判斷此內容關聯到哪些症狀和故障。"""
