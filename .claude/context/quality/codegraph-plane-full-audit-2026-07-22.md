# Plane × Code 全面狀態稽核報告(codegraph workflow)

- **日期**: 2026-07-22 10:45
- **任務**: 34 代理 workflow(`wf_839f9a31-1cc`)全面驗證 38 張 Plane 卡狀態 vs 工作樹實況;改動建議全過 3 人反方驗證(正確性/部署殘項/證據充分性)
- **範圍**: 全 repo(baseline=dev-ding 含 CR-0176 `6cff4688`+CR-0177 `248dd838`+WBS 標注 `9334d81b`)

## 結論

- **34 筆判定:29 keep、5 change(全數對抗驗證通過)**
- 已套用(無爭議):**3.3.1 Todo→In Progress**(provision_brand.py+開站 SOP+0712 acme-demo dry-run 已落地,殘=OPS 上雲)、**3.5.1 Todo→In Progress**(SOP 文件化+dry-run 已做,殘=綁 LINE/部署/PM 親演)
- 待業主裁決(Done→In Progress 降級建議,與 WBS 正典 ✅ 衝突故不擅動):
  - **2.2.1 RAG 語義層**:code 全在,但雲端 RAG 不可用(RAG_TENANT_ID 移除+agent image 缺 mcp 套件,cloud-deploy-report:43-45)
  - **2.2.2 語料灌注**:249 chunk 只在本機/UAT,雲端 0 chunk
  - **2.3.3 LiveSkill**:0719 雲端鐵證完成,唯一殘=業主親驗版(卡雲端帳密)
- 留言補正:seq38(merge 已完成、補列 S3/S5 殘項)、2.1.1(補列 R2 prod 映射重驗+refinery interim auth 移交落空)、2.4.2(WBS 遺留「雲端套 089/090+GCS+i18n」查無實證,標準不一致提示)

## 行動項目

- [ ] 業主裁決 2.2.1/2.2.2/2.3.3 三張「code 完成但雲端殘」卡的狀態哲學(維持 Done+留言 vs 降 In Progress)
- [ ] 完整性批判建議:quick-wins 批次(merge 5bbec92c:FallbackProvider/outbox p99/五因子/結案地址門檻+144 條覆蓋稽核)無對應卡,可補建 Done 卡或擴列 seq38 範圍
- [ ] 1.4.1 的「三站複製」是 code 面缺口(tech-portal/landing/platform-console 零 OTel 接線),非純 OPS——可排工

## 影響評估

- **嚴重度**: LOW(狀態簿記,無功能影響)
- **影響範圍**: Plane LOCK 專案 38 卡;smartlock-docs WBS 狀態欄(已另以標注銷差)
- 完整 findings 34 筆含 file:line 證據:workflow transcript `wf_839f9a31-1cc`(journal.jsonl)
