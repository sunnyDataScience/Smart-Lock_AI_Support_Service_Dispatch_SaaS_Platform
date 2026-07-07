# Enterprise 文件組合 — Smart Lock AI 客服與派工 SaaS 平台

> **版本:** 1.0 | **建立:** 2026-07-07 | **依據:** `../software_development_documentation_guide_zh_tw.docx` §14.3 Enterprise 文件組合
>
> 本目錄是平台級的正典開發文件集(27 份)。逐系統深度細節沿各文件的 `upstream:` frontmatter 進入 `../{system}/P1–P4`;衝突時以本組合與 `../` 各系統文件互相對照,無法證實者標 `[待確認]`。

## 文件地圖

| 層 | 文件 | 回答的問題 |
| :--- | :--- | :--- |
| 商業/產品 | [00_Product_Strategy](./00_Product_Strategy.md) · [01_MRD](./01_MRD.md) | 為什麼做?市場機會在哪? |
| 需求 | [02_BRD](./02_BRD.md) · [03_PRD](./03_PRD.md) · [04_SRS](./04_SRS.md) · [05_NFR](./05_NFR.md) | 業務規則、功能需求、品質指標 |
| UX | [06_UX_Research_Report](./06_UX_Research_Report.md) · [07_Journey_Map](./07_Journey_Map.md) · [08_User_Flow](./08_User_Flow.md) · [09_IA](./09_IA.md) | 四方角色如何完成任務? |
| UI | [10_UI_Spec](./10_UI_Spec.md) · [11_Design_System](./11_Design_System.md) | 畫面與元件如何呈現? |
| 架構 | [12_SAD](./12_SAD.md) · [13_Security_Architecture](./13_Security_Architecture.md) · [14_ADR/](./14_ADR/00_INDEX.md) | 系統怎麼組成?為何這樣選? |
| 技術設計 | [15_SDS](./15_SDS.md) · [16_API_Spec.yaml](./16_API_Spec.yaml) · [17_AsyncAPI.yaml](./17_AsyncAPI.yaml) · [18_DB_Design](./18_DB_Design.md) | 工程師如何實作? |
| QA | [19_Test_Plan](./19_Test_Plan.md) · [20_Test_Cases](./20_Test_Cases.md) · [21_Traceability_Matrix](./21_Traceability_Matrix.md) · [22_UAT_Report](./22_UAT_Report.md) | 如何證明系統符合需求? |
| 維運 | [23_Deployment_Guide](./23_Deployment_Guide.md) · [24_Runbook](./24_Runbook.md) · [25_Monitoring_Spec](./25_Monitoring_Spec.md) · [26_Incident_Postmortem](./26_Incident_Postmortem.md) | 如何部署、監控與救火? |
| 推進計畫 | [27_Product_Roadmap_WBS](./27_Product_Roadmap_WBS.md) | 階段/里程碑/WBS——開發團隊該做什麼、驗收是什麼?(階段一鎖匠垂直深耕,階段二平台化橫向展開) |

## 使用規則

1. **本組合是平台級入口**,不重複各系統細節 —— 每份文件的 frontmatter `upstream:` 列出其真相源。
2. **ADR append-only**:`14_ADR/` 已 Accepted 的決策不改內容,推翻須新開 ADR。
3. **`[待確認]` 標記**:表示該數字/行為尚未由 code 或量測證實,補證後移除。
4. **🔜 規劃中(Phase N)**:表示已定案設計但尚未落地的能力。
