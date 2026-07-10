# CR-0147 — M2 SIT(WBS 2.6.1)

- **日期**:2026-07-10
- **範圍**:M2 全線(身分/知識/技師平台/收斂)系統整合測試;UAT=業主(M2 Release gate=M1+M2 全數驗收,1.7.2 亦未跑)

## §1 SIT 結果(scratch 5463 全新 bootstrap 合跑)

| 套件 | 結果 |
|---|---|
| api(含 CR-0141/0143/0144/0145 全部新面) | **1738 passed** 0 failed(2 skipped=live 憑證) |
| agent | **162 passed** |
| rag(含新增 agent→MCP→RAG 整合測試 2——SIT 缺口銷案) | **7 passed** |
| refinery(修測試密鑰跟隨 env——合跑 401 假紅) | **12 passed** |
| 四站 tsc | 0 錯(brand 本輪覆核;四站同 lib 當日全綠) |

## §2 live 實證(本日累計,SIT 等級證據)

1. Casdoor:bootstrap 同步+password grant+api 驗證器映射(CR-0141)
2. OIDC 授權碼流瀏覽器全流程:SSO→授權→cookie→dashboard(CR-0146)
3. **refinery live LLM 煉製**:真 Vertex 把 UAT knowledge_ready 卡煉成 1 case_entry+2 behavior 草稿(CR-0139/0140 遺留銷案——精煉迴路全鏈 live 證完)
4. RAG:UAT 灌注 249 chunk+檢索基準 83%(CR-0142)
5. requote 通道:TC-DISPATCH-07 核心 5 測試(CR-0144)

## §3 跨線 mini-SIT 對照(19_Test_Plan/風險登記 L178)

身分線=①②;知識線=③④;技師平台線=⑤;每線皆有本日 live 證據+套件綠。

## §8 遺留(業主/排程)

- **UAT**:M1 1.7.2+M2 業主驗收(合約紅線 K1/K3/K8)——22_UAT_Report 框架就緒
- ACT-01 cutover(R3)、三站 SSO 複製、v1 遷移/移除(CR-0145 §8 三待決)、Casdoor prod HA/密碼、schemathesis/k6 導入(19_Test_Plan 🔜)

### 進度

- ✅ SIT done(2026-07-10,branch `test/m2-sit`)
