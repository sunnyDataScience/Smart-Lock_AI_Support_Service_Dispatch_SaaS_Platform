"""Smart Lock enterprise 四書的靜態展示資料。

需求、NFR、TC、ADR 與 WBS 不在這裡重複維護，一律由生成器讀取
enterprise 正典 Markdown。本檔只放顯示分群、管理視角與 QA 場景。
"""

GENERATED_ON = "2026-07-22"

# 驗收控制表的 PM／業務語言投影。
#
# - voc：將 SRS 技術規格翻成「誰遇到什麼問題、為什麼需要」。
# - prd_acceptance：只描述 UAT 看得到的行為與結果，不重複 API／事件／資料庫流程。
#
# 原始「前置／主流」仍以 04_SRS.md 為真相源，並完整投影到
# 驗收活頁簿的「技術流程對照」分頁。
FR_BUSINESS_COPY = {
    "FR-AGT-01": {
        "voc": "客戶透過 LINE 詢問時，希望訊息能被可靠接收並得到明確回覆，不因格式或系統異常失聯。",
        "prd_acceptance": "當客戶傳送文字或照片時，合法訊息會進入客服流程並收到回覆；無效來源被拒絕，系統異常時仍有友善說明。",
    },
    "FR-AGT-02": {
        "voc": "客戶希望每次對話都能承接上文，不需反覆重述同一問題。",
        "prd_acceptance": "同一客戶連續對話時，系統能保留必要脈絡並完成當次回覆；個別記憶儲存失敗不得中斷對話。",
    },
    "FR-AGT-03": {
        "voc": "客戶需要先獲得可自助解決的建議；若仍未解決，希望系統主動確認並安排人員協助。",
        "prd_acceptance": "當問題卡資訊完整時，客戶會先收到相符的解決建議並被詢問是否已釐清；連續三次未釐清時自動轉人工。",
    },
    "FR-AGT-04": {
        "voc": "遇到被鎖在外、受困、安全風險或高度負面情緒時，客戶希望立即得到人員協助，不要繼續與 AI 周旋。",
        "prd_acceptance": "標記為急件的對話不再繼續一般自助流程，會在五分鐘內進入人工協助並可追查轉接原因。",
    },
    "FR-AGT-05": {
        "voc": "當案件涉及金額、派工、急件或客戶要求真人時，業務希望每件都有人承接，不會因 AI 說已轉接而實際漏案。",
        "prd_acceptance": "任一需轉人工的對話都會出現在後台待處理清單；即使 AI 轉接動作未完成，系統也會自動補建案件。",
    },
    "FR-AGT-06": {
        "voc": "回訪客戶希望客服記得已確認的資訊，同時不會看到其他人或其他品牌的資料。",
        "prd_acceptance": "同一品牌、同一客戶再次對話時可沿用已確認事實；缺少身分資訊時不讀寫記憶，且跨客戶、跨品牌不得混用。",
    },
    "FR-AGT-07": {
        "voc": "客戶期待 AI 依品牌 SOP 和已核可知識回答，遇到冷門問題也能找到有來源的資訊。",
        "prd_acceptance": "以代表性常見與長尾問題驗收時，AI 回覆符合 SOP、能追溯到核可資料；新檢索能力未通過品質關卡前保留已核可備援。",
    },
    "FR-AGT-08": {
        "voc": "品牌與營運方需要可信任的 AI 客服，只能使用核准能力，不得擅自操作敏感功能。",
        "prd_acceptance": "客服 AI 只能執行核准的六類工具；嘗試呼叫其他工具時必須被拒絕，新增工具前必須完成變更審查。",
    },
    "FR-AGT-09": {
        "voc": "客服人員接手後，需要 AI 暫停發言，但完整對話仍要保留，避免雙方同時回覆或記錄斷裂。",
        "prd_acceptance": "人工接管期間 AI 不再自動回覆，客戶與客服的所有訊息持續完整留存；接管狀態查詢異常不得讓客戶無法取得回應。",
    },
    "FR-AGT-10": {
        "voc": "客戶常會把一句話分成多則 LINE 訊息，希望系統能合併理解，不要重複回答。",
        "prd_acceptance": "短時間連續訊息視為同一次提問處理；同一事件被平台重送時不得重複產生回覆或案件。",
    },
    "FR-AGT-11": {
        "voc": "客戶需要清楚知道 AI 只能提供參考價格，不會擅自報定案金額或對客戶照片進行未授權辨識。",
        "prd_acceptance": "金額情境中 AI 僅提供區間與適當免責說明，不宣告最終價；照片僅作存證，任何影像辨識嘗試均被阻擋。",
    },
    "FR-API-01": {
        "voc": "客服需要將零散對話整理成完整案情，並在資訊確認後才進入報價與派工。",
        "prd_acceptance": "AI 可草擬問題卡，客服能補齊與確認；未達完整度或未經客服確認時，不得自動轉成工單。",
    },
    "FR-API-02": {
        "voc": "客戶希望收到清楚、可確認的報價；品牌希望報價經過內部核准，且不暴露成本資訊。",
        "prd_acceptance": "報價必須依序完成內部核准、客戶送達與客戶確認；保固或專案報價不得由 AI 直接送出，客戶畫面不顯示成本欄位。",
    },
    "FR-API-03": {
        "voc": "客服需要一致且可追溯的計價結果；若自動計價暫時不可用，仍要能安全完成報價。",
        "prd_acceptance": "相同價格規則與輸入產生一致結果，工單與結算可追溯當時報價；計價不可用時明確提示客服並允許有紀錄的人工處理。",
    },
    "FR-API-04": {
        "voc": "客服希望在客戶同意報價後快速建立工單，同時避免重複建單或 AI 未經授權自行開單。",
        "prd_acceptance": "報價已獲客戶確認或符合急件例外時，客服可一次操作建立工單；重複送出不產生第二張工單，並留下建單來源。",
    },
    "FR-API-05": {
        "voc": "客戶與派工人員希望系統快速找到合適且可服務的技師，急件應優先處理，無人可派時不能靜默失敗。",
        "prd_acceptance": "新工單會依距離、技能、評分、工作量與公平性推薦技師並送出通知；急件優先就近與高評分，無候選人時進入待處理並通知營運。",
    },
    "FR-API-06": {
        "voc": "派工人員需要在特殊情況下改派指定技師，並讓主管能回查誰為什麼覆寫自動建議。",
        "prd_acceptance": "有權限的派工人員可指定技師；每次人工覆寫都必須填寫理由並保留操作人與時間。",
    },
    "FR-API-07": {
        "voc": "營運人員需要掌握技師是否及時接單與到達，超時案件必須被看見並升級處理。",
        "prd_acceptance": "一般與急件工單依約定時間等待接單；連續無人接單時擴大媒合並通知客服，預計到達超過服務水準時對主管標示與提醒。",
    },
    "FR-API-08": {
        "voc": "客戶與品牌都需要完整的到府、施工、材料與簽名記錄，作為驗收、保固與爭議處理依據。",
        "prd_acceptance": "技師可上傳到場與施工證據、登錄受控材料並取得客戶簽名；證據不齊或現場範圍變更未完成必要確認時不得結案。",
    },
    "FR-API-09": {
        "voc": "品牌希望只有資訊、報價與必要審核都完整的工單才能結案，避免事後無法對帳或處理爭議。",
        "prd_acceptance": "結案時會檢查服務地址、客戶確認報價與必要的急件補審；任一項未完成時明確拒絕結案並告知缺項。",
    },
    "FR-API-10": {
        "voc": "客戶希望能用約定方式付款、取得憑證，付款失敗或爭議時知道案件正被處理。",
        "prd_acceptance": "已完工且金額大於零的工單可使用現金、Apple Pay 或 LINE Pay 付款；重複通知不重複記帳，成功後可取得憑證，失敗與爭議有明確狀態。",
    },
    "FR-API-11": {
        "voc": "客戶希望退款與取消費按責任和服務進度公平計算，業務需要能處理例外並保留理由。",
        "prd_acceptance": "退款依責任類型、取消費依案件進度產生正確結果；客服覆寫必須留存理由，已記帳金額以反向分錄更正而不篡改原紀錄。",
    },
    "FR-API-12": {
        "voc": "財務與營運需要在月底看到客收、技師應付、現金、品牌結算、佣金、退款與稅務一致的帳務。",
        "prd_acceptance": "月結可產生七類帳本與例外清單，各筆借貸平衡且有原因代碼；差異在結算前可被找出、處理與追溯。",
    },
    "FR-API-13": {
        "voc": "業務希望 AI 與後台之間的對話、轉人工、接管與客戶回應不漏件，也不被外部未授權來源冒用。",
        "prd_acceptance": "已授權的內部服務可送入對話、升級與客戶回應；缺少或錯誤憑證的請求被拒絕，不得寫入業務資料。",
    },
    "FR-API-14": {
        "voc": "客服、派工與技師希望不需重新整理畫面就能看到工單與派工變化，且只收到自己有權限的訊息。",
        "prd_acceptance": "已授權使用者可即時收到所屬頻道更新，未授權訂閱被拒絕；即時服務暫時不可用時主流作業仍可繼續。",
    },
    "FR-API-15": {
        "voc": "營運需要通知重送、SLA 提醒、個資刪除與自動結案等定時工作持續執行，不重複、不漏跑。",
        "prd_acceptance": "每項定時作業依排程完成並可查看結果；多台服務同時運作時同一批次不重複執行，失敗案有重試或告警。",
    },
    "FR-API-16": {
        "voc": "客戶提出刪除個人資料時，希望在承諾時間內被處理；若受法律保全限制，需及時得到說明。",
        "prd_acceptance": "忘卻請求在七日內完成可見資料失效，或因法律保全而在同期間通知客戶；後續完成實體刪除，處理歷程可稽核。",
    },
    "FR-API-17": {
        "voc": "客戶希望保固案按設備適用規則處理，不被當作一般付費案錯誤報價或結案。",
        "prd_acceptance": "各類保固模式能正確影響報價、結案與退款決策；保固案的報價必須由授權人員處理，不得由 AI 直接送客。",
    },
    "FR-API-18": {
        "voc": "品牌需要把改期、爭議與其他例外案集中處理，並避免同一人從申請到核准全程自行完成。",
        "prd_acceptance": "例外案會進入統一收件匣並顯示待處理狀態；申請、核准與執行任二角色為同一人時，敏感操作必須被阻擋。",
    },
    "FR-API-19": {
        "voc": "急件可先救急施作，但客戶與品牌仍需要在事後快速完成報價、審核與同意記錄。",
        "prd_acceptance": "急件現場作業結束後自動建立四小時內的補審任務；未完成報價補送與客戶事後確認前不得結案，逾時案升級主管。",
    },
    "FR-WEB-01": {
        "voc": "派工、技師、品牌客戶與平台管理者希望進入各自清楚的入口，不會誤入不相關或未授權功能。",
        "prd_acceptance": "四種網站入口各自只顯示適用路徑與行動；從一個入口前往另一個入口時會被導向正確頁面。",
    },
    "FR-WEB-02": {
        "voc": "使用者只應看到職責需要的頁面，敏感功能不得因手動輸入網址而被繞過。",
        "prd_acceptance": "合法登入後依角色顯示可用頁面；未登入、角色不符或未列入許可的路徑均不可進入，登入憑證不暴露給頁面腳本。",
    },
    "FR-WEB-03": {
        "voc": "派工人員需要在同一個工作台掌握待派、進行中與超時案件，即時通道中斷時仍能工作。",
        "prd_acceptance": "派工人員可查看工單看板、待派佇列與即時更新；即時連線中斷時畫面不崩潰，仍可查詢與完成核心作業。",
    },
    "FR-WEB-04": {
        "voc": "主管需要看懂服務量、SLA 與例外趨勢，並能匯出可對帳的報表支援管理決策。",
        "prd_acceptance": "有權限的主管可看到關鍵指標、逾時標示與篩選後報表；畫面與匯出數字在相同條件下一致。",
    },
    "FR-WEB-05": {
        "voc": "稽核與治理人員需要查詢與匯出變更記錄，但不能在查閱過程中改動歷史。",
        "prd_acceptance": "授權人員可依條件查詢與匯出稽核記錄；畫面不提供修改功能，每次查閱或匯出也會留下存取紀錄。",
    },
    "FR-WEB-06": {
        "voc": "客戶希望在 LINE 內看懂報價、條款與服務進度，並以明確動作表示同意。",
        "prd_acceptance": "客戶可查看報價明細、分層閱讀條款、勾選同意並追蹤工單進度；簡化備援方式也會準確記錄客戶同意來源。",
    },
    "FR-WEB-07": {
        "voc": "使用者遇到網路或服務異常時，需要知道發生什麼事、是否可重試，而不是看到空白頁面。",
        "prd_acceptance": "任一主要 API、網路或頁面錯誤都顯示可理解的狀態、影響與下一步建議；錯誤不導致整個應用程式崩潰。",
    },
    "FR-DAT-01": {
        "voc": "內容營運與稽核人員需要知識資料來源清楚、可重建，不因重跑處理而重複或失真。",
        "prd_acceptance": "五類資料可保留原始來源、轉為可治理與可使用的知識；重複執行不產生重複結果，PDF 僅保留來源連結而不複製內文。",
    },
    "FR-DAT-02": {
        "voc": "品牌希望系統升級時資料結構可控、可追溯，不會因不同環境版本漂移而停機或損壞資料。",
        "prd_acceptance": "資料結構變更有唯一編號與套用記錄，在已套用或不同環境重新執行時不破壞現有資料；版本差異能在上線前被發現。",
    },
    "FR-DAT-03": {
        "voc": "各品牌、技師平台與平台治理資料必須明確隔離，客戶不接受任何跨租戶資料暴露。",
        "prd_acceptance": "使用各類正常、錯誤與越權身分進行查詢與寫入時，只能存取所屬資料範圍；品牌、技師與平台資料零交叉洩漏。",
    },
    "FR-DAT-04": {
        "voc": "品牌希望 AI 使用同一套已核可事實資料，回答可找到來源，不因多份知識複本而互相矛盾。",
        "prd_acceptance": "代表性查詢可從品牌所屬事實語料找到相關手冊或案例，結果可追溯且不混入其他品牌；未完成的檢索元件不列入上線驗收。",
    },
    "FR-DAT-05": {
        "voc": "業務希望從客戶進線、建案、派工到現場存證的每一步狀態一致，不漏件、不重複。",
        "prd_acceptance": "代表性案件從進線到完工可在各相關畫面查到一致狀態；重複送出或短暫中斷後重試不會產生重複案件，未同步事件可補送。",
    },
    "FR-DAT-06": {
        "voc": "風控與稽核人員需要知道每個人、每次變更與 AI 決策是否來自合法身分，且歷史不可被改寫。",
        "prd_acceptance": "從登入身分、業務變更到 AI 決策均能以同一身分脈絡追查；修改或刪除稽核歷史的嘗試能被發現。",
    },
    "FR-REF-01": {
        "voc": "內容團隊需要將實際客服對話、案例與產品素材統一收集，成為可審查的知識候選內容。",
        "prd_acceptance": "核准的對話與產品素材可進入同一收集流程，保留來源與使用權限；在收集方式定案前，不將未驗證通道視為已驗收。",
    },
    "FR-REF-02": {
        "voc": "內容團隊希望 AI 把素材區分為「可回答的事實」與「客服應遵守的行為」，並保留每次精煉歷史。",
        "prd_acceptance": "每份素材精煉後明確進入事實或行為待審清單，可看到來源與差異；新結果只能新增版本，不刪改既有記錄。",
    },
    "FR-REF-03": {
        "voc": "品牌不希望未審核的 AI 產出直接影響客戶，內容人員需要看到差異後才決定核准、拒絕或退回。",
        "prd_acceptance": "審核人員能查看新舊差異並選擇核准、拒絕或退回；未核准內容不得出現在正式知識庫或 AI 行為規則中。",
    },
    "FR-REF-04": {
        "voc": "核准後的知識需要正確發布到事實檢索與客服行為兩個用途，並維持品牌隔離與版本可追溯。",
        "prd_acceptance": "已核准的事實可被所屬品牌檢索，已核准的行為規則可在新版本中使用；發布前會拒絕非核准來源，且可追查每次新增。",
    },
    "FR-REF-05": {
        "voc": "高風險 SOP 需要同時得到客服管理與領域專家認可，並由家族覆核角色在時限內確認。",
        "prd_acceptance": "高風險 SOP 只有在客服主管、領域專家雙簽且 Family Reviewer 覆核後才能發布；任一覆核逾時則暫停發布並升級。",
    },
    "FR-TEC-01": {
        "voc": "技師希望只註冊一次就能維護個人資料、技能與想服務的品牌，不必為每個品牌重複建檔。",
        "prd_acceptance": "技師可建立單一身分、完成個人檔案與技能設定，並申請服務一個或多個品牌；身分不隸屬任一品牌租戶。",
    },
    "FR-TEC-02": {
        "voc": "品牌與客戶需要確保只有身分、證照與品牌授權都有效的技師才能被派案。",
        "prd_acceptance": "技師可上傳 KYC 與認證資料供人工審核；只有審核通過且已獲品牌授權者進入派工候選名單。",
    },
    "FR-TEC-03": {
        "voc": "各品牌希望共用一個技師媒合能力，按技能、地區、授權與可用時間找到候選人，不直接暴露技師庫。",
        "prd_acceptance": "品牌送出媒合條件後可取得符合條件且排序合理的候選技師；未授權品牌不可查詢技師原始資料或進行指派。",
    },
    "FR-TEC-04": {
        "voc": "技師需要即時收到新派工並清楚回覆接單或拒單，品牌需要及時得到結果以便繼續派工。",
        "prd_acceptance": "新派工會推播到目標技師，技師可接單或拒單，品牌後台及時看到回應；連線中斷後狀態可補齊而不丟失。",
    },
    "FR-TEC-05": {
        "voc": "技師需要在一個工作台看到跨品牌必要工單資訊，但不應取得與施工無關的客戶或品牌敏感資料。",
        "prd_acceptance": "技師工作台顯示已指派工單的摘要、地址、狀態、時窗與必要金額；未指派或與作業無關的資料不可見。",
    },
    "FR-TEC-06": {
        "voc": "技師希望跨品牌收入可在統一對帳單查看，品牌與平台需要在付款前對齊每張工單佣金。",
        "prd_acceptance": "期末可產生技師跨品牌對帳單與待付款金額；品牌逐案計費與平台匯總不一致時必須阻擋出款並列出差異。",
    },
    "FR-TEC-07": {
        "voc": "技師到場後若發現工項與原診斷不同，需要發起報價修正，但不能自行定價或跳過客戶確認。",
        "prd_acceptance": "只有當班且工單處於現場或施工中的指派技師可提交事由與工項差異；技師不輸入金額，由品牌產生新版報價並回傳狀態。",
    },
    "FR-TEC-08": {
        "voc": "技師需要維護可服務時間，品牌需要在技師停權或認證失效後立即停止派案。",
        "prd_acceptance": "有效技師可設定排班與可用狀態；停權或認證撤銷後，所有已授權品牌的派工候選名單及時移除該技師。",
    },
    "FR-PLT-01": {
        "voc": "品牌、技師與平台人員希望使用同一套帳號邏輯登入各自服務，租戶管理者可自助開帳。",
        "prd_acceptance": "使用者以統一身分登入後只進入所屬品牌與授權服務；租戶管理者可建立帳號，前端不以可被腳本讀取的方式保存登入憑證。",
    },
    "FR-PLT-02": {
        "voc": "組織需要客服、派工、主管與審核者只能執行職責內操作，高風險功能未明確授權就應拒絕。",
        "prd_acceptance": "以四方角色矩陣驗收每個敏感功能：授權者可完成作業，未授權者無論從畫面或直接請求都被拒絕。",
    },
    "FR-PLT-03": {
        "voc": "平台營運希望品牌申請通過後，可按合約開通專屬環境、資料庫、LINE 與選購模組。",
        "prd_acceptance": "核准品牌後可依 License 開通正確模組與獨立環境，未授權模組不可用；開通結果可由平台與品牌管理者查看。",
    },
    "FR-PLT-04": {
        "voc": "多品牌與多台服務運作時，業務事件、即時更新與定時作業必須不丟失、不重複、可復原。",
        "prd_acceptance": "在多實例、短暫斷線與訂閱者重啟情境下，工單、派工與通知最終恢復一致；同一定時作業不因橫向擴展而重複執行。",
    },
    "FR-PLT-05": {
        "voc": "平台希望可依產業、成本與可用性切換 AI 模型供應商，不需重寫產品流程。",
        "prd_acceptance": "以主模型、備援模型與異常情境驗收：模型可透過配置切換，主供應失敗時依政策降級或轉用備援，業務邏輯不需改寫。",
    },
    "FR-PLT-06": {
        "voc": "營運與技術團隊需要快速看到 LINE、模型、資料庫、即時與派工的服務健康，以便在客戶大量報修前處理異常。",
        "prd_acceptance": "營運儀表板可查看關鍵成功率、延遲與事件積壓，並能從告警追到受影響服務與案件；必要管理資料不暴露客戶個資。",
    },
    "FR-PLT-07": {
        "voc": "平台希望把不同產業 SOP 組成可管理的工單流程，但 AI 產出涉及金流、派工與同意書時必須有人審核。",
        "prd_acceptance": "已核准的產業流程可由受控積木執行並留存版本；任何 AI 草擬且會影響金流、派工或客戶同意的流程在人工核准前不得生效。",
    },
    "FR-PLT-08": {
        "voc": "品牌希望能自助調整 AI 知識、行為與提示詞，同時不能覆寫安全、轉人工等平台保護規則。",
        "prd_acceptance": "授權品牌管理者可建立、比較、測試與分階段發布可客製配置；受保護規則不可被覆寫，每次變更與回滾都可追溯。",
    },
    "FR-PLT-09": {
        "voc": "平台營運需要在一個受控後台處理品牌申請、技師平台審核與跨租戶治理，不直接修改各品牌業務資料。",
        "prd_acceptance": "平台管理者可審核品牌與技師平台申請、查看跨租戶健康與治理資訊；管理平面使用獨立安全邊界，跨品牌業務資料僅可讀。",
    },
}

SUBSYSTEMS = {
    "AGT": {
        "name": "agent（LockCore AI 客服）",
        "short": "AI 客服",
        "component": "line_gateway; AgentLoop / AgentRunner; LiteLLMProvider; MemoryManager + Store / EscalationStore; SkillsLoader + 2 builtin skills; 記憶 DB",
        "sad": "12_SAD §4.1 L138–149",
        "sds": "15_SDS §5.1 L358–374; 附錄 L724–729",
        "path": "agent/lockcore/; agent/scripts/line_gateway.py",
        "description": "LINE 進線、Turn 編排、知識檢索、記憶、轉真人與 AI 邊界治理。",
    },
    "API": {
        "name": "api（派工營運控制平面）",
        "short": "派工控制",
        "component": "FastAPI dispatch / tech / platform surfaces",
        "sad": "12_SAD §4.2 L151–164",
        "sds": "15_SDS §6.1 L422–472; 附錄 L730–733",
        "path": "api/routers/; api/services/; api/core/; api/realtime/",
        "description": "問題卡、報價、工單、派工、現場存證、金流結算、隱私與稽核。",
    },
    "WEB": {
        "name": "web（多站前端）",
        "short": "多站前端",
        "component": "dispatch-web / tech-web / landing-web / platform-web / LIFF",
        "sad": "12_SAD §4.3 L166–177",
        "sds": "15_SDS §8.1 L564–578; 附錄 L734–735",
        "path": "web/src/components/; web/src/lib/; web/types/",
        "description": "品牌營運、師傅、平台維運與消費者 LIFF 介面。",
    },
    "DAT": {
        "name": "data-pipeline（資料與 schema）",
        "short": "資料平台",
        "component": "Medallion pipeline / PostgreSQL / pgvector / migrations",
        "sad": "12_SAD §4.6 L199–208",
        "sds": "15_SDS §3.1 L81–124; 附錄 L736",
        "path": "knowledge-pipeline/pipeline/; knowledge-pipeline/storage/; SQL/",
        "description": "raw→bronze→silver、三庫物理隔離、語義語料、migration 與跨系統同步。",
    },
    "REF": {
        "name": "knowledge-refinery（知識精煉）",
        "short": "知識精煉",
        "component": "Refinery service / HITL review UI / Publisher",
        "sad": "12_SAD §4.4 L179–187",
        "sds": "15_SDS §9.1 L603–619; 附錄 L736–737",
        "path": "knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/",
        "description": "診斷與素材汲取、LLM 事實/行為分流、HITL 審核與雙路發佈。",
    },
    "TEC": {
        "name": "technician-platform（技師共享池）",
        "short": "技師平台",
        "component": "technician API / OHS / technician web / lock_tech",
        "sad": "12_SAD §4.5 L189–197",
        "sds": "15_SDS §7.1 L503–518; 附錄 L738",
        "path": "technician-platform 獨立 codebase（SDS 尚待確認）",
        "description": "跨租戶技師身分、KYC、品牌授權、媒合、工單投影與結算。",
    },
    "PLT": {
        "name": "00_platform（平台整合層）",
        "short": "平台核心",
        "component": "Casdoor / Kafka / Redis / SigNoz / OPIK / Config Registry",
        "sad": "12_SAD §8.1–8.3 L353–376; §9 L384–401",
        "sds": "15_SDS §2–3 L34–205; §10–11 L639–677",
        "path": "跨系統共用平台；依各正式元件所屬路徑",
        "description": "身分與 License、事件骨幹、可觀測性、模型編排、工單積木與配置治理。",
    },
}

# L2 僅是四書顯示群組，不是新增的追溯主鍵。追溯一律使用 SRS FR ID。
MODULES = {
    "AGT": [
        ("CHN", "通道與 Turn 編排", {"01", "02", "10"}),
        ("RES", "診斷與轉真人", {"03", "04", "05", "09"}),
        ("KNW", "記憶與知識", {"06", "07"}),
        ("GOV", "AI 邊界治理", {"08", "11"}),
    ],
    "API": [
        ("CASE", "問題卡與報價", {"01", "02", "03", "17", "19"}),
        ("WO", "工單與現場", {"04", "08", "09"}),
        ("DISP", "派工與 SLA", {"05", "06", "07"}),
        ("FIN", "付款與結算", {"10", "11", "12"}),
        ("INT", "內部整合與即時通道", {"13", "14", "15"}),
        ("GOV", "隱私與例外審批", {"16", "18"}),
    ],
    "WEB": [
        ("SHELL", "入口、權限與降級", {"01", "02", "07"}),
        ("OPS", "派工營運與報表", {"03", "04"}),
        ("AUD", "稽核治理", {"05"}),
        ("CX", "消費者 LIFF", {"06"}),
    ],
    "DAT": [
        ("MED", "Medallion 知識資料", {"01"}),
        ("SCH", "Schema 與 migration", {"02", "03"}),
        ("RAG", "向量語料", {"04"}),
        ("SYNC", "同步與稽核基座", {"05", "06"}),
    ],
    "REF": [
        ("INTAKE", "素材汲取", {"01"}),
        ("REFINE", "LLM 提煉分流", {"02"}),
        ("HITL", "HITL 審核", {"03", "05"}),
        ("PUB", "Publisher 雙路落地", {"04"}),
    ],
    "TEC": [
        ("ID", "身分、KYC 與生命週期", {"01", "02", "08"}),
        ("MATCH", "OHS 媒合與接單", {"03", "04", "07"}),
        ("PROJ", "工單投影", {"05"}),
        ("SET", "技師結算", {"06"}),
    ],
    "PLT": [
        ("IAM", "身分、RBAC 與 License", {"01", "02", "03"}),
        ("EVT", "事件與即時骨幹", {"04"}),
        ("LLM", "模型編排", {"05"}),
        ("OBS", "可觀測性", {"06"}),
        ("FLOW", "工單積木引擎", {"07"}),
        ("CFG", "Agent 配置與平台治理", {"08", "09"}),
    ],
}

# L2 能力群→正式 SAD/SDS 元件的人工投影。
# 元件名稱沿用 12_SAD / 15_SDS 用語；L2 不是新的架構元件或追溯主鍵。
MODULE_ARCH = {
    "AGT.CHN": {
        "component": "line_gateway; AgentLoop; AgentRunner",
        "sad": "12_SAD §4.1 L138–149",
        "sds": "15_SDS §5.1 L358–374",
        "path": "agent/lockcore/channels/line_gateway.py; agent/lockcore/agent/{loop,runner}.py",
    },
    "AGT.RES": {
        "component": "AgentLoop; AgentRunner; ToolRegistry; EscalationStore",
        "sad": "12_SAD §4.1 L145–148",
        "sds": "15_SDS §5.1 L367–374; §5.3",
        "path": "agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py",
    },
    "AGT.KNW": {
        "component": "ContextBuilder; MemoryManager + Store; SkillsLoader + 2 builtin skills; 記憶 DB",
        "sad": "12_SAD §4.1 L147–149",
        "sds": "15_SDS §5.1 L368, L372–374",
        "path": "agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/",
    },
    "AGT.GOV": {
        "component": "AgentRunner; LiteLLMProvider + FallbackProvider; ToolRegistry; SkillsLoader + 2 builtin skills",
        "sad": "12_SAD §4.1 L145–148; §9 L395, L407",
        "sds": "15_SDS §5.1 L369–374; §5.4",
        "path": "agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/",
    },
    "API.CASE": {
        "component": "tenant-scoped routers; Service Layer（problem_card / quote）; core/db.py",
        "sad": "12_SAD §4.2 L151–164",
        "sds": "15_SDS §4.2 L225–252; §4.6 L292–354; §6.1 L422–472",
        "path": "api/routers/; api/services/; api/core/db.py",
    },
    "API.WO": {
        "component": "Service Layer（work_order）; Flow DSL executor; domain blocks / primitives; core/db.py",
        "sad": "12_SAD §4.2 L151–164; §9 L397",
        "sds": "15_SDS §3.3–3.5 L144–188; §4.1–4.2 L209–252; §6.1 L444–466",
        "path": "api/services/work_order_service.py; api/routers/; api/core/db.py",
    },
    "API.DISP": {
        "component": "Service Layer（dispatch）; Redis pub/sub; Kafka; 分散式排程",
        "sad": "12_SAD §4.2 L151–164; §8.1–8.2 L353–372",
        "sds": "15_SDS §6.1 L444–466; §6.3 L484–492; §11.1 L648–660",
        "path": "api/services/dispatch*; api/realtime/; Kafka integration",
    },
    "API.FIN": {
        "component": "Service Layer（invoice / settlement）; core/db.py; Kafka",
        "sad": "12_SAD §4.2 L151–164; §9 L401",
        "sds": "15_SDS §4.2 L250–252; §6.1 L444–466; §7.3 L554–560",
        "path": "api/services/{invoice,settlement}*; api/core/db.py",
    },
    "API.INT": {
        "component": "internal_ingest.py; WebSocket 端點; Redis pub/sub; Kafka; line_push_service + outbox worker",
        "sad": "12_SAD §4.2 L151–164",
        "sds": "15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677",
        "path": "api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service*",
    },
    "API.GOV": {
        "component": "守衛鏈; core/errors.py; core/idempotency.py; Middleware",
        "sad": "12_SAD §4.2 L151–164; §9 L393",
        "sds": "15_SDS §6.1 L428–472; §6.4 L494–499",
        "path": "api/core/{deps,errors,idempotency,auth,pii_crypto}.py; api/main.py",
    },
    "WEB.SHELL": {
        "component": "AuthGuard; appMode gate; rolePolicy",
        "sad": "12_SAD §4.3 L166–177",
        "sds": "15_SDS §8.1 L564–578; §8.2–8.3 L580–599",
        "path": "web/src/components/layout/AuthGuard.tsx; web/src/lib/{appMode,rolePolicy}.ts",
    },
    "WEB.OPS": {
        "component": "api client; cache; realtime",
        "sad": "12_SAD §4.3 L166–177",
        "sds": "15_SDS §8.1 L575–578; §8.3 L593–599",
        "path": "web/src/lib/{api,cache,realtime}.ts",
    },
    "WEB.AUD": {
        "component": "rolePolicy; api client; 型別（api.generated.ts）",
        "sad": "12_SAD §4.3 L166–177",
        "sds": "15_SDS §8.1 L570–578",
        "path": "web/src/lib/{rolePolicy,api}.ts; web/types/api.generated.ts",
    },
    "WEB.CX": {
        "component": "api client; cache; realtime",
        "sad": "12_SAD §4.3 L166–177",
        "sds": "15_SDS §8.1 L575–578; §8.3 L593–599",
        "path": "web/src/lib/{api,cache,realtime}.ts",
    },
    "DAT.MED": {
        "component": "source_to_raw; raw_to_bronze; bronze_to_silver; storage（raw/bronze/silver）",
        "sad": "12_SAD §4.6 L199–208",
        "sds": "15_SDS §9.1 L611–613; 附錄 L736",
        "path": "knowledge-pipeline/pipeline/; knowledge-pipeline/storage/",
    },
    "DAT.SCH": {
        "component": "SQL/Schema*.sql; forward-only migrations; platform schema; core/db.py",
        "sad": "12_SAD §4.2 L160–162; §4.6 L207–208",
        "sds": "15_SDS §3.1 L81–124; §6.1 L448–451",
        "path": "SQL/Schema*.sql; SQL/migrations/*.sql; SQL/platform/Schema_platform.sql",
    },
    "DAT.RAG": {
        "component": "MCP RAG server; 品牌庫 pgvector; rag_manual_chunks / case_entries",
        "sad": "12_SAD §8.1 L353–361; §9 L407",
        "sds": "15_SDS §5.1 L376; §9.1 L617–619; §11.3 L677",
        "path": "rag MCP service; SQL migrations; knowledge-pipeline/refinery/",
    },
    "DAT.SYNC": {
        "component": "Medallion pipeline; Kafka; outbox; provenance / audit",
        "sad": "12_SAD §4.2 L164; §4.6 L199–208; §8.2 L372",
        "sds": "15_SDS §6.3–6.4 L484–499; §9.3 L631–635; §11 L648–677",
        "path": "knowledge-pipeline/; api/realtime/; Kafka integration",
    },
    "REF.INTAKE": {
        "component": "汲取層; raw_to_bronze; bronze_to_silver",
        "sad": "12_SAD §4.4 L179–187",
        "sds": "15_SDS §9.1 L603–613; §9.3 L631–635",
        "path": "knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/{raw_to_bronze,bronze_to_silver}/",
    },
    "REF.REFINE": {
        "component": "提煉分流器; Draft Queue",
        "sad": "12_SAD §4.4 L183–187",
        "sds": "15_SDS §9.1 L614–615; §9.3 L631–635",
        "path": "knowledge-pipeline/refinery/",
    },
    "REF.HITL": {
        "component": "Draft Queue; 審核 UI backend",
        "sad": "12_SAD §4.4 L183–187",
        "sds": "15_SDS §9.1 L615–616; §9.2 L621–629",
        "path": "knowledge-pipeline/refinery/",
    },
    "REF.PUB": {
        "component": "Publisher; 品牌庫 pgvector; SkillsLoader + 2 builtin skills",
        "sad": "12_SAD §4.4 L183–187",
        "sds": "15_SDS §9.1 L617–619; §9.3 L631–635",
        "path": "knowledge-pipeline/refinery/; agent/lockcore/skills/*/references/",
    },
    "TEC.ID": {
        "component": "self-service routers; 守衛鏈; technician_service; certification/kyc_service; lock_tech",
        "sad": "12_SAD §4.5 L189–197",
        "sds": "15_SDS §7.1 L503–518; §7.2 L550–552",
        "path": "technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）",
    },
    "TEC.MATCH": {
        "component": "OHS API routers; matching_service; schedule_service; WebSocket 端點; 事件層",
        "sad": "12_SAD §4.5 L189–197",
        "sds": "15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548",
        "path": "technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）",
    },
    "TEC.PROJ": {
        "component": "事件層; 技師工單 read-model; WebSocket 端點",
        "sad": "12_SAD §4.5 L193–197; §8.2 L369, L372",
        "sds": "15_SDS §7.1 L513–518; §7.3 L554–560; §11.1 L648–660",
        "path": "technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）",
    },
    "TEC.SET": {
        "component": "commission_settlement_service; 技師工單 read-model; Kafka",
        "sad": "12_SAD §4.5 L189–197; §9 L401",
        "sds": "15_SDS §7.1 L515–518; §7.3 L554–560; §11.1 L648–660",
        "path": "technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）",
    },
    "PLT.IAM": {
        "component": "Casdoor; 平台維運 console; 守衛鏈; License provisioning",
        "sad": "12_SAD §8.2–8.3 L363–376; §9 L390, L393",
        "sds": "15_SDS §2.1 L40–56; §6.1 L437–442; §11.2 L662–670",
        "path": "web/platform-console; api platform surface; Casdoor deployment/config",
    },
    "PLT.EVT": {
        "component": "Kafka; Redis pub/sub; WebSocket 端點; 分散式排程",
        "sad": "12_SAD §4.2 L164; §8.1–8.2 L353–372; §9 L394",
        "sds": "15_SDS §6.1 L453–466; §6.3 L484–492; §11 L648–677",
        "path": "api/realtime/; Kafka/Redis integration",
    },
    "PLT.LLM": {
        "component": "LiteLLMProvider + FallbackProvider; Model Orchestration Layer",
        "sad": "12_SAD §4.1 L146; §9 L395, L407",
        "sds": "15_SDS §2.2 L68; §5.1 L370; §13 L707",
        "path": "agent/lockcore/providers/{litellm_provider,fallback_provider}.py",
    },
    "PLT.OBS": {
        "component": "SigNoz; OPIK; OpenTelemetry",
        "sad": "12_SAD §8.2 L363–372; §9 L389",
        "sds": "15_SDS §12 L681–696（韌性與觀測證據使用面）",
        "path": "集中共用可觀測性部署（非單一應用路徑）",
    },
    "PLT.FLOW": {
        "component": "Flow DSL executor; domain blocks / primitives; Vertical Pack; FlowEditor",
        "sad": "12_SAD §9 L396–398",
        "sds": "15_SDS §2.1 L36–59; §3.2–3.7 L126–205; §10 L639–644",
        "path": "待 M4 實作；目前為 SDS 設計元件",
    },
    "PLT.CFG": {
        "component": "Agent Configuration Studio / Config Registry; Vertical Pack; HITL 審核骨架",
        "sad": "12_SAD §9 L396, L398, L400",
        "sds": "15_SDS §3.2 L126–142; §10 L639–644; §13 L704–709",
        "path": "待 M4/M5 實作；目前為 SAD/ADR/SDS 設計元件",
    },
}

# 出現於 MODULE_ARCH.component 的每個分號分隔標籤都必須在此有定義。
# 生成器會反向驗證，避免再出現「看到名詞卻不知道到哪裡找」。
COMPONENT_GLOSSARY = {
    "line_gateway": {
        "alias": "LINE 通道閘道",
        "definition": "LINE 通道閘道：接收 webhook、驗證 X-Line-Signature、分派訊息/事件，並將回覆送回 LINE。",
        "boundary": "只負責通道整合與旁路轉發；不負責主要 AI 推理、定價或開工單。",
    },
    "AgentLoop": {
        "alias": "LockCore runtime（產品層）",
        "definition": "產品層 Turn 狀態機：恢復 session、組上下文、執行、儲存並產生一次回覆。",
        "boundary": "編排一次對話 Turn；不直接實作通用 tool-using LLM 迴圈。",
    },
    "AgentRunner": {
        "alias": "LockCore runtime（通用執行層）",
        "definition": "通用 Agent 執行器：在有界迴圈內呼叫模型、處理 tool calls，並在每輪執行上下文治理。",
        "boundary": "不知道報價、派工等產品流程；產品狀態由 AgentLoop、Skill 與 API 約束。",
    },
    "ContextBuilder": {
        "alias": "LockCore runtime（上下文層）",
        "definition": "上下文組裝器：依序組合 identity、Customer Memory、always-skills 與 skill 摘要。",
        "boundary": "只建立模型輸入上下文；不負責永久儲存或模型供應商路由。",
    },
    "LiteLLMProvider + FallbackProvider": {
        "definition": "模型供應商層：以 model 字串路由多家 LLM，並在主供應商失敗時切換備援。",
        "boundary": "處理模型調用、重試與 failover；不承載業務規則或產品決策。",
    },
    "Model Orchestration Layer": {
        "definition": "供應商無關的模型編排層：集中管理路由、fallback、逾時、快取與調用效率。",
        "boundary": "是技術治理層，不是 Agent 產品流程、Skill 或知識庫。",
    },
    "ToolRegistry": {
        "definition": "Agent 工具登錄與白名單：定義哪些工具可被模型呼叫，並治理呼叫邊界。",
        "boundary": "不自行決定何時呼叫工具，也不向模型暴露未登錄的任意程式。",
    },
    "MemoryManager + Store": {
        "alias": "Memory",
        "definition": "長期記憶管理與存儲層：載入/寫回客戶已確認事實，讀寫必須同帶 tenant_id + user_id。",
        "boundary": "不等於當次 session 原始對話，不可跨租戶或使用者共用。",
    },
    "EscalationStore": {
        "definition": "轉真人稽核存儲：記錄轉接理由、已知事實快照與必要追溯資料。",
        "boundary": "保證轉人事件不蒸發；不是正式工單庫，也不代替 API 的開單 gate。",
    },
    "SkillsLoader + 2 builtin skills": {
        "alias": "Skills",
        "definition": "Agent 行為規範載入器：載入 product-knowledge 與 cs-sop，定義判斷、查資料、轉真人與紅線。",
        "boundary": "管「怎麼做」；不是長期對話記憶，也不是所有長尾事實的唯一資料庫。",
    },
    "記憶 DB": {
        "alias": "Memory backend",
        "definition": "Agent 長期記憶的永久化後端，設計上使用 Postgres schema agent.*。",
        "boundary": "只存 Agent 記憶與相關稽核；不是品牌業務庫、平台庫或技師權威庫。",
    },
    "tenant-scoped routers": {
        "definition": "以 /tenants/{tid}/... 暴露品牌業務的 FastAPI 路由層，負責 HTTP 入口、輸入驗證與授權依賴。",
        "boundary": "不在 router 堆疊主要 SQL/業務邏輯；租戶與角色檢查交給標準守衛鏈。",
    },
    "Service Layer（problem_card / quote）": {
        "definition": "問題卡與報價服務層：管理診斷卡 gate、報價狀態、版本與不可否認快照。",
        "boundary": "不讓 Agent 或技師端直接定價；品牌 API 仍是報價權威。",
    },
    "Service Layer（work_order）": {
        "definition": "工單服務層：建立工單、驗狀態轉移/gate、寫入時間軸並觸發副作用。",
        "boundary": "不允許 AI 繞過客戶確認與 HITL 直接轉工單。",
    },
    "Service Layer（dispatch）": {
        "definition": "派工服務層：執行候選查詢、指派、接單 SLA、擴大範圍與狀態更新。",
        "boundary": "不在品牌庫雙寫技師權威資料；媒合應經 OHS 與事件契約。",
    },
    "Service Layer（invoice / settlement）": {
        "definition": "帳單、收付、對帳與結算邏輯：管理金額狀態、冪等、reversal 與帳本一致性。",
        "boundary": "Billing 真相留品牌側；跨品牌技師 Settlement 由 technician-platform 匯總。",
    },
    "core/db.py": {
        "definition": "API 資料庫基礎層：管理連線池、交易邊界與讀寫分離。",
        "boundary": "不放領域流程決策；業務交易應由 service 層調用。",
    },
    "internal_ingest.py": {
        "definition": "Agent 與內部服務使用的 /internal/* 入口，接收對話、轉人與報價回應等旁路資料。",
        "boundary": "只接受 fail-closed 內部憑證；不是 LINE webhook 入站門。",
    },
    "WebSocket 端點": {
        "definition": "經授權的即時推播連線入口，依 channel、技師與租戶將狀態更新送給前端。",
        "boundary": "是即時通知管道，不是業務事件的永久真相；斷線時頁面應可退化為 REST。",
    },
    "Redis pub/sub": {
        "definition": "跨實例的低延遲訊息擴散，用於 WebSocket fan-out、cache 與部分分散式鎖。",
        "boundary": "不保證長期持久與重播；需重播的事件應使用 Kafka 或資料庫。",
    },
    "Kafka": {
        "definition": "持久、可重播的跨系統事件骨幹，傳遞 technician.*、dispatch.*、workorder.* 與 commission.* 等事件。",
        "boundary": "不代替低延遲同步查詢（OHS/REST），也不代替各領域真相資料庫。",
    },
    "分散式排程": {
        "definition": "跨實例協調 SLA、GDPR 硬刪、自動結案與 LINE outbox 等背景工作，並以鎖避免重複執行。",
        "boundary": "只觸發已定義任務；不把關鍵業務真相只留在 scheduler 記憶體。",
    },
    "line_push_service + outbox worker": {
        "definition": "LINE 出站推播與可重試佇列：業務交易先寫 outbox，worker 後送並記錄結果。",
        "boundary": "推播失敗不回滾主業務寫入；不處理 LINE 入站 webhook。",
    },
    "守衛鏈": {
        "definition": "API 授權鏈：get_current_user → require_tenant → role_required，加上 platform admin 與 internal token 邊界。",
        "boundary": "逐端點 deny-by-default enforce；不把前端隱藏按鈕當成安全控制。",
    },
    "core/errors.py": {
        "definition": "API 錯誤標準化元件：將例外轉為 RFC7807 problem+json 相容信封。",
        "boundary": "統一錯誤呈現與分類；不吞掉必須中斷的安全或交易錯誤。",
    },
    "core/idempotency.py": {
        "definition": "Mutation 冪等控制：以 Idempotency-Key 辨識重播，避免重複開單、收款或狀態轉移。",
        "boundary": "只保護重播語意；不代替業務狀態機與資料庫唯一約束。",
    },
    "Middleware": {
        "definition": "FastAPI 橫切處理鏈：處理 CORS、Request ID、版本廢棄等全局請求/回應邏輯。",
        "boundary": "不承載單一領域的核心業務規則。",
    },
    "AuthGuard": {
        "definition": "Web 根佈局的前端路由守衛：先做跨站導向，再檢查 token 與角色存取。",
        "boundary": "只是 UX 層門禁；真正授權必須由 API 守衛鏈 enforce。",
    },
    "appMode gate": {
        "definition": "判斷當前 portal build 是否服務某路徑，不屬於本站的路徑導向對應 portal。",
        "boundary": "是分站與導航控制，不是後端租戶或角色安全邊界。",
    },
    "rolePolicy": {
        "definition": "前端 route→roles 最長前綴政策表，控制導航與無權使用者的安全落點。",
        "boundary": "只提供前端 UX 治理；不代替 API role_required。",
    },
    "api client": {
        "definition": "Web 統一 HTTP client：注入 Bearer、X-Tenant-ID、Idempotency-Key，處理 refresh 與錯誤信封。",
        "boundary": "不在瀏覽器內繞過 API 授權，也不將客戶端狀態當作服務端真相。",
    },
    "cache": {
        "definition": "Web GET 請求共享 in-flight 與短期 staleTime 快取，mutation 後可主動失效。",
        "boundary": "是前端效能優化；不是永久資料庫或授權依據。",
    },
    "realtime": {
        "definition": "WebSocket 訂閱層：一 channel 一 socket、處理重連 backoff，未設定時靜默降級。",
        "boundary": "負責前端即時連線生命週期；不是事件持久層。",
    },
    "型別（api.generated.ts）": {
        "definition": "由 OpenAPI 生成的 TypeScript API 型別，使前端在編譯期偵測契約漂移。",
        "boundary": "反映契約但不定義業務真相；不手改生成檔來代替 OpenAPI。",
    },
    "Medallion pipeline": {
        "definition": "離線資料流水線：將素材依 raw→bronze→silver 分層處理，保留來源與可重現性。",
        "boundary": "是 batch 與持久資產，不是長駐即時 API runtime。",
    },
    "source_to_raw": {
        "definition": "收集原始外部素材並原樣落地到 raw 層，保留來源識別與取得資訊。",
        "boundary": "不宣告內容已清洗或可直接用於 Agent 回答。",
    },
    "raw_to_bronze": {
        "definition": "將 raw 影音、網頁或文件轉錄與清洗為可審查的 bronze 素材。",
        "boundary": "只做可追溯轉換；不將未審核內容直接發布至知識庫。",
    },
    "bronze_to_silver": {
        "definition": "將 bronze 去冗、糾錯、語意切塊成 silver，並由程式覆寫 provenance 防止 LLM 幻覺來源。",
        "boundary": "silver 不等於已核可發布；下游仍需提煉、HITL 與 Publisher gate。",
    },
    "storage（raw/bronze/silver）": {
        "definition": "Medallion 各分層的持久檔案資產，保留原始、可審查與結構化中間成果。",
        "boundary": "是 pipeline 資產庫；不等於線上 pgvector 查詢庫。",
    },
    "SQL/Schema*.sql": {
        "definition": "資料庫基底 schema 定義，描述主表、索引與基礎約束。",
        "boundary": "不直接代替已上線環境的 forward-only migration 演進記錄。",
    },
    "forward-only migrations": {
        "definition": "只向前套用、有順序與可稽核性的 SQL schema 變更集。",
        "boundary": "不靠手改 production schema；漂移與重複套用必須由 CI/測試阻擋。",
    },
    "platform schema": {
        "definition": "平台治理庫的獨立 schema，存管理員、品牌申請等跨租戶管理資料。",
        "boundary": "不存單一品牌內的工單、客戶或報價真相。",
    },
    "MCP RAG server": {
        "definition": "以 MCP 工具契約向 Agent 暴露產品手冊與相似案例的租戶授權檢索服務。",
        "boundary": "只負責事實檢索；不定義 Agent 行為，也不允許無 tenant ACL 直查 DB。",
    },
    "品牌庫 pgvector": {
        "definition": "每品牌物理隔離的 PostgreSQL/pgvector，存業務資料與該品牌唯一事實語料。",
        "boundary": "不跨品牌共用記錄；技師權威資料仍在 lock_tech。",
    },
    "rag_manual_chunks / case_entries": {
        "definition": "RAG 的手冊切塊與案例條目，帶租戶/品牌過濾、embedding 與 provenance。",
        "boundary": "是被查找的事實資料；不是 Skill 行為規範或對話 Memory。",
    },
    "outbox": {
        "definition": "與主業務交易同步寫入的待發送記錄，由 worker 重試投遞通知或事件。",
        "boundary": "解耦交易與外部副作用；不代替 Kafka 的跨系統長期事件日誌。",
    },
    "provenance / audit": {
        "definition": "記錄資料來源、處理版本、行為者與時間的可重現與稽核證據。",
        "boundary": "不允許 LLM 自行編造來源，也不把一般顯示日誌當成不可否認稽核鏈。",
    },
    "汲取層": {
        "definition": "知識精煉入口：收集 knowledge_ready 診斷卡與外部產品素材。",
        "boundary": "只撿取符合租戶與完整度 gate 的輸入；不直接發布到 Agent。",
    },
    "提煉分流器": {
        "definition": "將 silver 內容分為「可查找的事實」與「Agent 怎麼做的行為」兩條軌。",
        "boundary": "只產生 draft；未經 HITL 核可不得寫入 pgvector 或 Skill。",
    },
    "Draft Queue": {
        "definition": "事實 draft 與行為 diff 的審核佇列，包含來源、冪等鍵與狀態機。",
        "boundary": "是待審產物，不是已發布知識。",
    },
    "審核 UI backend": {
        "definition": "提供 draft 狀態轉移、diff 呈現、核可、駁回與 re-refine 的 HITL 後端。",
        "boundary": "不自動把 LLM 產物當真相；核可與發布仍是兩個可稽核步驟。",
    },
    "Publisher": {
        "definition": "核可後的雙軌發布器：事實 embed 後寫 pgvector；行為產生 append-only Skill patch/artifact。",
        "boundary": "只發布 approved draft；不跳過 provenance、tenant 過濾或人審 gate。",
    },
    "self-service routers": {
        "definition": "技師端自助 API：註冊、profile、技能/品牌授權、認證上傳、排班與工作台。",
        "boundary": "只服務已驗證的技師生命週期；不暴露跨租戶品牌內部資料。",
    },
    "technician_service": {
        "definition": "技師身分、技能、品牌授權、停復權與評分等核心領域服務。",
        "boundary": "真相寫入 lock_tech；不雙寫各品牌庫。",
    },
    "certification/kyc_service": {
        "definition": "技師 KYC 與認證申請/審核服務，對敏感欄位加密並控制准入。",
        "boundary": "未核可或已失效認證不得進入媒合候選集。",
    },
    "lock_tech": {
        "definition": "跨品牌技師身分域的獨立權威資料庫，存身分、技能、授權、排班、評分與結算 profile。",
        "boundary": "不存各品牌的完整工單或客戶敏感資料。",
    },
    "OHS API routers": {
        "definition": "品牌 API 查詢技師共享池的同步契約入口，包含技師查詢、媒合、排班與認證查詢。",
        "boundary": "主要做低延遲讀/媒合；指派與接單真相經業務命令及 Kafka 事件收斂。",
    },
    "matching_service": {
        "definition": "依技能、地區、品牌授權、認證、可用性、評分與工作量排序技師候選。",
        "boundary": "返回候選不等於已指派；不繞過 active、授權與認證 gate。",
    },
    "schedule_service": {
        "definition": "管理技師排班、可用時段、接單後工作量與行程狀態。",
        "boundary": "不直接決定品牌工單狀態；跨系統變更經事件與投影對齊。",
    },
    "事件層": {
        "definition": "technician-platform 的 Kafka producer/consumer 與投影更新層，發技師狀態並收派工、工單與結算事件。",
        "boundary": "只以契約事件跨界；不直接連線或改寫品牌庫。",
    },
    "技師工單 read-model": {
        "definition": "由品牌 workorder.* 事件建立的最小化 CQRS 查詢投影，供技師工作台顯示。",
        "boundary": "只複製任務所需欄位；不是工單命令真相，不複製品牌全量敏感資料。",
    },
    "commission_settlement_service": {
        "definition": "匯總各品牌 commission.accrued，建立技師跨品牌 statement、payout 與期末對帳。",
        "boundary": "不重算品牌工單的 Billing 明細；差異以 reconcile gate 收斂。",
    },
    "Casdoor": {
        "definition": "集中式 IdP 與開通治理：提供 OIDC、租戶 org、角色 claims 與 License subscription。",
        "boundary": "發行身分與角色資訊；資源層授權仍由各 API deny-by-default enforce。",
    },
    "平台維運 console": {
        "definition": "Super Admin 使用的中央管理前端，處理品牌申請、租戶治理、License 與跨品牌營運視角。",
        "boundary": "不當作單品牌日常派工後台，也不繞過 platform admin 授權。",
    },
    "License provisioning": {
        "definition": "License 核准後部署 per-brand bundle、建品牌庫、綁 LINE channel/設定並做健康檢查。",
        "boundary": "是開通與部署流程；不代替應用內租戶授權與資料隔離。",
    },
    "SigNoz": {
        "definition": "平台系統可觀測性服務，收集 OpenTelemetry metrics、logs、traces 並提供 dashboard 與告警。",
        "boundary": "看服務健康與系統行為；不專職管理 prompt 或模型 eval。",
    },
    "OPIK": {
        "definition": "Agent LLM Ops 工具，追蹤 prompt、LLM trace、token/成本與 eval 品質。",
        "boundary": "專注 AI 調用品質；不代替 SigNoz 的全系統可觀測性。",
    },
    "OpenTelemetry": {
        "definition": "服務不綁供應商的 metrics、logs、traces 儀表化與傳輸標準。",
        "boundary": "是觀測資料契約與傳輸層；不是 dashboard 或業務稽核帳本本身。",
    },
    "Flow DSL executor": {
        "definition": "讀取 Vertical Pack 的宣告式 flow，驗 guard、執行 block、持久化狀態/事件並掛 SLA timer。",
        "boundary": "只執行可驗證 DSL；拒絕任意 inline code，也不把 UI 編輯器當執行後端。",
    },
    "domain blocks / primitives": {
        "definition": "雙層工單積木：對外是派工/報價/收款等粗顆粒 block，內部由查資料、轉狀態、發事件等 primitive 組合。",
        "boundary": "每顆積木必須有 inputs/preconditions/guards/effects 契約；不允許無法靜態驗證的自由腳本。",
    },
    "Vertical Pack": {
        "definition": "可版本化的產業配置包，組合 field metadata、flow、catalog、knowledge、UI composition 與 blocks。",
        "boundary": "承載產業/品牌差異；不改寫身分、金流、事件等平台不變核心。",
    },
    "FlowEditor": {
        "definition": "對 flow DSL 進行拖拉或表單編輯的薄 UI，輸出仍是可版控、可驗證的 DSL。",
        "boundary": "不直接執行任意程式；金流、派工與同意書仍受保護層及 HITL gate。",
    },
    "Agent Configuration Studio / Config Registry": {
        "definition": "管理 skill、RAG 權限、prompt、品牌設定與版本/分階段發布的中央配置能力。",
        "boundary": "租戶只可改客製層；安全、金額、工具白名單等保護層不可 override。",
    },
    "HITL 審核骨架": {
        "definition": "共用的 draft→diff→人審→核可/駁回→發布模式，同時支援知識精煉與 AI Onboarding Compiler。",
        "boundary": "AI 只產生 draft；高風險知識或流程未人審不得落地。",
    },
}

# 這是 Roadmap/WBS 的管理投影，不代表 code 已實作。
PHASE_BY_ID = {
    "FR-DAT-04": "M2",
    "FR-REF-01": "M2",
    "FR-REF-02": "M2",
    "FR-REF-03": "M2",
    "FR-REF-04": "M2",
    "FR-REF-05": "M2",
    "FR-TEC-01": "M2",
    "FR-TEC-02": "M2",
    "FR-TEC-03": "M2",
    "FR-TEC-04": "M2→M3",
    "FR-TEC-05": "M3",
    "FR-TEC-06": "M3",
    "FR-TEC-07": "M2",
    "FR-TEC-08": "M2",
    "FR-PLT-01": "M2",
    "FR-PLT-03": "M3",
    "FR-PLT-04": "M1→M3",
    "FR-PLT-05": "M1→M2",
    "FR-PLT-06": "M1",
    "FR-PLT-07": "M4",
    "FR-PLT-08": "M4",
    "FR-PLT-09": "M2→M3",
}

PHASE_OVERVIEW = [
    ["M1", "上線硬化", "單品牌全鏈正確、即時、可稽核", "RBAC enforce、工單狀態機、急件補審、對話存檔、Redis/cron、可觀測、AI eval、SIT/UAT", "27_Product_Roadmap_WBS §3 M1"],
    ["M2", "身分・知識・技師平台", "三條獨立能力線成形", "Casdoor、RAG-via-MCP、knowledge-refinery/HITL、technician-platform、API 收旂", "27_Product_Roadmap_WBS §3 M2"],
    ["M3", "多品牌規模化", "第 2 品牌用標準流程開站", "Kafka/CQRS、對帳閘門、License provisioning、雲端拓撲、開站演練", "27_Product_Roadmap_WBS §4 M3"],
    ["M4", "平台化地基", "把鎖匠版抽象成產業無關引擎", "flow DSL、積木契約、兩層渲染、Vertical Pack、FlowEditor", "27_Product_Roadmap_WBS §4 M4/M5"],
    ["M5", "第 2 產業", "驗證 FDE 四配置面與積木飛輪", "手工 bootstrap 新產業積木，再疊加 AI Onboarding Compiler + HITL", "27_Product_Roadmap_WBS §4 M4/M5"],
]

ARCH_CHOICES = [
    ["AC-01", "平台核心 vs 領域配置", "六大不變原語由核心掌握，產業差異放進 Vertical Pack 四配置面", "降低跨產業客製對核心的污染", "ADR-001 / 12_SAD §1.3"],
    ["AC-02", "per-brand 物理隔離", "每品牌一套 bundle 與 DB；技師、IdP、事件骨幹為集中共用", "隔離強，但 provisioning/運維成本必須自動化", "ADR-002 / ADR-020"],
    ["AC-03", "Casdoor 統一身分與 License", "OIDC org=租戶，role claim 供 API enforce，subscription 當開通閘門", "跨品牌關鍵單點，需 HA 與 fail-soft", "ADR-004 / ADR-005"],
    ["AC-04", "Kafka + Redis + 讀寫分離", "Kafka 負責持久可重播，Redis 負責 WS fanout/cache/lock，Postgres 分離熱讀", "需 schema 契約、冪等、reconcile 與演練", "ADR-006"],
    ["AC-05", "Skill 行為 + RAG-via-MCP 事實", "Skill 定義怎麼做；pgvector 為唯一長尾事實語料，經 MCP 檢索", "須保持 provenance、租戶 ACL 與 references 同源", "ADR-010 / ADR-030"],
    ["AC-06", "Flow-as-Blocks DSL-first", "流程是資料，guard→block→持久化/事件/SLA；拒絕 inline code", "引擎、契約與靜態驗證先於拖拉 UI", "ADR-013 / ADR-014"],
    ["AC-07", "AI 永不自轉工單", "AI 只能診斷、草擬問題卡與轉人；報價/開單/金流需決定性 gate 與 HITL", "合約與金錢風險的上線紅線", "ADR-025 / 04_SRS FR-AGT-11"],
    ["AC-08", "報價快照不可否認", "已送出報價綁 immutable content-addressable snapshot，修改以 v+1 串鏈", "防止定價規則改動回溯污染與爭議", "ADR-026 / FR-API-02/03"],
    ["AC-09", "技師只發 requote command", "技師可提交項目 diff 但無定價權；品牌 API 為報價唯一權威", "跨系統需 tenant route、冪等與降級", "ADR-027 / FR-TEC-07"],
    ["AC-10", "契約三分層", "執行期匯出為型別 SSOT，OpenAPI/AsyncAPI 為對外投影，文件為解釋", "程式與文件 drift 必須在 CI 擋下", "ADR-031"],
]

GLOSSARY = [
    ["per-brand bundle", "每個品牌獨立部署的 web/api/agent/DB/Redis/RAG 組合", "品牌間物理隔離，開新品牌等於再供應一套"],
    ["集中共用平台", "Casdoor、SigNoz、technician-platform、Kafka、平台 console", "跨品牌管理的共用地基，需視為關鍵單點"],
    ["ProblemCard", "AI/客服在正式報價與工單前的結構化診斷卡", "案件先收旂完整，才可進報價/工單"],
    ["Clarify gate", "AI 回答後主動確認是否已釐清", "不把「有幫助」誤當「問題已解決」"],
    ["Flow-as-Blocks", "宣告式狀態機 + 有契約的領域積木", "用配置組流程，金流/派工/同意書仍受強制 gate 保護"],
    ["Vertical Pack", "field metadata + flow + catalog + knowledge + UI composition + blocks", "一個產業的可版本化配置包"],
    ["OHS API", "品牌 API 查詢技師共享池的同步媒合契約", "品牌不直連技師庫，指派/接單改走事件"],
    ["CQRS 投影", "品牌工單是 command 真相，技師平台維護最小化 read model", "技師看得到必要工單，但不複製品牌全量敏感資料"],
    ["HITL", "Human-in-the-loop 人工審核閘門", "知識、金流、派工、同意書等高風險產出不可直接上線"],
    ["Skill 行為驅動", "Skill 存 SOP、紅線與檢索程序", "管「怎麼做」，不把長尾事實全塞進 prompt"],
    ["RAG-via-MCP", "透過 MCP server 查 pgvector 唯一事實語料", "事實可更新、可分租戶授權，agent 不與 DB 綁死"],
    ["SigNoz / OPIK", "系統 OTel 可觀測 / Agent LLM Ops", "一個看服務健康，一個看 prompt、trace 與 eval 品質"],
    ["SoD", "Initiator / Approver / Executor 任二相同即拒絕", "敏感金流與審批不能一人包辦"],
]

TEST_STRATEGY = [
    ["Risk-based", "先驗金錢、授權、跨租戶、合約紅線與工單主流", "P0 未結清不可發布；其他依衝擊與替代路徑排序"],
    ["Shift-left", "需求評審就以驗收表逐條對齊", "在寫 TC 前先清理待確認門檻與 ID 衝突"],
    ["Contract-first", "OpenAPI / AsyncAPI / OHS / internal API 經 consumer-driven test", "跨庫不靠 FK，跨服務更需要 schema、冪等與失敗契約"],
    ["State-transition", "對 Quote / WorkOrder / Onsite / Payment 以狀態轉移測試", "每條法定轉移、非法轉移、guard、超時與冪等都要有證據"],
    ["Observability-as-evidence", "實際 SLI、audit hash、trace 與 reconcile 是驗收證據", "不用「畫面有出現」取代事件、帳本與稽核正確性"],
]

TEST_TYPES = [
    ["階段", "Unit / Component", "函式、類別、guard、parser、pricing 規則與狀態轉移單元", "RD 主責，CI 每次合併必跑"],
    ["階段", "Integration / Contract", "agent→api internal、api→OHS、Kafka consumer、DB migration", "RD + QA；正反例、冪等、timeout、版本相容"],
    ["階段", "System / E2E", "LINE→問題卡→報價→工單→派工→現場→結算", "QA 主責，以完整使用者旅程驗證"],
    ["階段", "UAT", "合約紅線、品牌營運、技師、消費者與平台治理", "業務 Owner 簽核，QA 提供證據"],
    ["類型", "Security / Privacy", "RBAC、SoD、服務憑證、工具白名單、PII、GDPR、租戶隔離", "P0；必含權限負例與 fail-closed"],
    ["類型", "Performance / Resilience", "LINE latency、OHS、WS、outbox、Kafka lag、單點失敗", "k6/chaos/replay；記錄 p95/p99 與降級行為"],
    ["方法", "Boundary / Decision table", "0.85 completeness、5/10/20km、500/2000 金額階梯、5/10/30min SLA", "準備門檻前、等於門檻、門檻後資料；逐組執行並核對狀態、金額、事件與 audit"],
    ["方法", "Mutation / Negative", "偽造 token、重放、跨租戶 ID、非法狀態、schema drift", "修改一個輸入或前置條件後重跑主流，確認 guard fail-closed 且不產生副作用"],
]

BUG_LEVELS = [
    ["P0 / Blocker", "金錢錯帳、授權繞過、跨租戶洩漏、合約紅線、工單主流無替代路徑", "任一 open → Release/UAT Fail", "立即止血、留 audit，需 root cause + regression"],
    ["P1 / Major", "主流斷點、審計斷鏈、SLA 引擎失效，有昂貴手動替代", "未結 → 至多 Conditional Pass", "需明確修復日與補償控制"],
    ["P2 / Normal", "次要功能、UX、非阻斷效能偏差", "可進 backlog，不得掩蓋 KPI 紅線", "依影響版本排程"],
    ["P3 / Minor", "文案、非核心外觀、無任務影響的不一致", "不阻發布", "批次收旂處理"],
]

ENVIRONMENTS = [
    ["Local / CI", "每次 commit / PR", "unit、lint、typecheck、schema diff、migration drift、AI eval dry", "快速回饋；不放真實 PII"],
    ["Integration", "契約或跨服務變更", "internal/OHS/OpenAPI/AsyncAPI、DB migration、outbox/Kafka/Redis", "固定 fixture + 可重建三庫"],
    ["Staging / SIT", "里程碑測試", "全鏈場景、RBAC 矩陣、效能、chaos、回歸", "拓撲近似 production，資料去識別"],
    ["UAT", "業務簽核", "S1–S5 旅程、K1/K3/K8、合約與稽核報表", "業務 Owner 簽名；紀錄版本、資料集與證據"],
    ["Production smoke", "發布後", "health、登入、LINE webhook、關鍵讀路徑、告警", "禁止破壞性測試；異常立即 rollback"],
]

STLC = [
    ["1. Requirement review", "確認使用者行為、前後條件、量化門檻與例外", "驗收控制表 + 待裁定清單"],
    ["2. Test analysis", "將前線需求轉成風險、端到端場景與可判定的測試項目", "⑧必測行為 + ⑨場景 + ⑩執行清單"],
    ["3. Test design", "對邊界、決策、狀態、權限與逾時寫可重現步驟", "前置資料 + 步驟 + 預期結果"],
    ["4. Execution", "保存版本、輸入、log/trace/audit、實測值與截圖", "SIT/UAT 證據包 + defect"],
    ["5. Closure", "QA Lead 確認覆蓋與追溯，清理缺口並取得簽核", "追溯健康報告 + 簽核"],
]

TEST_STAGES = [
    ["SIT-1 子系統", "各服務功能與契約穩定", "Unit/component 綠；資料庫可重建", "P0/P1 契約測試全綠，無 blocker"],
    ["SIT-2 跨系統", "LINE、internal API、OHS、WS、outbox/Kafka、三庫同步", "SIT-1 通過；類 production 拓撲", "TS-01–TS-12 P0 通過，reconcile/hash 無差異"],
    ["UAT", "業務旅程與合約驗收", "SIT-2 通過；業務 Owner/資料集到位", "P0=0；K1/K3/K8 等門檻通過；簽核"],
    ["Release candidate", "只做回歸與發布演練，不再大幅探索", "UAT Pass/Conditional 且例外有補償控制", "rollback <30min 演練、smoke 通過、告警正常"],
]

RESPONSIBILITIES = [
    ["Requirement / acceptance review", "PM/BA", "QA+RD", "主鍵唯一、關鍵字可測、例外與門檻無歧義", "驗收控制表裁定"],
    ["Unit / component", "RD", "QA 抽驗", "函式、guard、狀態機、parser、pricing、migration", "CI report"],
    ["API / contract", "RD", "QA", "OpenAPI/AsyncAPI/internal/OHS，正反例+版本+冪等", "contract report"],
    ["System / E2E", "QA", "RD+OPS", "以 TS 場景驗證跨服務與主流", "SIT evidence"],
    ["NFR / chaos", "QA+OPS", "RD", "效能、可用、降級、告警、回復、容量", "benchmark + drill"],
    ["UAT / sign-off", "Business Owner", "PM+QA", "業務適用性與合約紅線", "22_UAT 簽核"],
]

SCENARIOS = [
    ["TS-01", "LINE AI 自助與轉真人", "P0", "驗簽進線→Turn→案例/RAG→Clarify；急件/紅線必轉人", "品牌 LINE channel、知識與 internal token 可用", "送文字/照片/急件/假簽章/重送→對話、問題卡、escalation 對帳", "Functional / Security / Resilience"],
    ["TS-02", "問題卡→報價→開單", "P0", "驗證 completeness、報價快照、LIFF 確認與 AI 永不自轉工單", "一般案件與保固/建案 fixture", "草擬卡→補齊→quote v1→送客→確認→CS 1-click→WO created", "State / Boundary / Security"],
    ["TS-03", "自動派工與技師接單", "P0", "驗證 OHS 品牌/技能/距離/可用性過濾、接單 SLA 與即時投遞", "已 created 工單，有/無合格技師資料", "5→10→20km 媒合→指派→技師接/拒/逾時→品牌狀態與投影對帳", "Contract / State / Timeout"],
    ["TS-04", "現場、加價、requote 與結案", "P0", "驗證 500/2000 階梯、同意 fallback、quote v+1、三件套與急件補審", "技師為 assignee，工單 in_progress", "到場→施工→三種加價邊界→客戶接/拒→存證→結案 gate", "Boundary / Decision / State"],
    ["TS-05", "收款、退款、帳本與結算", "P0", "證明冪等、SoD、reversal、borrow=lend 與品牌 Billing/平台 Settlement 邊界", "已完工工單、支付/退款/月結 fixture", "收款→對帳→退款分層→月結→commission event→reconcile", "Ledger / SoD / Idempotency"],
    ["TS-06", "技師註冊、KYC 與生命週期", "P0", "未核可/停權技師不得入候選池，品牌授權 fail-closed", "Casdoor 與技師平台可用", "註冊→敏感文件→審核→品牌授權→排班→停權/復權", "Lifecycle / Security / Privacy"],
    ["TS-07", "知識精煉 HITL 閉環", "P0", "bronze-only→事實/行為分流→人審→pgvector/skill；未核可零落地", "診斷素材、refinery、審核 UI 與 Publisher 可用", "汲取→提煉→diff→核可/拒絕→雙路發佈→來源/租戶對帳", "Data quality / HITL / Provenance"],
    ["TS-08", "租戶、OIDC、RBAC 與 License 開通", "P0", "驗證單一身分、四方角色、deny-by-default 與 per-brand provisioning 邊界", "Casdoor / platform console / 三個 API surface 可用", "品牌申請→核准→org/License→bundle/建庫/綁 LINE→角色矩陣負測", "Security / Provisioning / Isolation"],
    ["TS-09", "資料、migration 與 audit 可重現", "P0", "三庫不 fallback、migration 無 drift、pipeline 冪等、hash chain 可驗", "乾淨與升級路徑 DB fixture", "從空庫/舊版套 migration→重套→注入 drift→跑 raw/bronze/silver→驗 hash", "Migration / Reproducibility / Mutation"],
    ["TS-10", "安全、隱私與合約紅線", "P0", "橫向驗證 prompt/tool、PII、GDPR、影像禁用、Family review、跨租戶", "權限矩陣、對抗題庫、retention/legal-hold fixture", "全端點矩陣→攻擊/跨租戶→forget/legal hold→影像 double gate→Family review", "Security / Compliance / Adversarial"],
    ["TS-11", "效能、容量、降級與可觀測", "P1", "量測 LINE/OHS/WS/outbox p95/p99，服務單點失敗時能降級與告警", "類 production 拓撲與 SigNoz/OPIK 可用", "階梯壓測→斷 LLM/Redis/Kafka/OHS/Casdoor→觀察降級、lag、alert、recovery", "Performance / Chaos / Observability"],
    ["TS-12", "Flow/Vertical Pack/Agent Config 治理", "P1", "DSL 靜態驗證、保護層不可 override、staged rollout/eval/rollback 有稽核", "Flow engine / Config Registry 與範例 pack 可用", "匯入 pack→非法 DSL→高風險 HITL→canary→SLO halt→rollback→audit 對帳", "Schema / Policy / Rollout"],
]

DOMAIN_TEST_META = {
    "AGT": ("AI 客服", "轉人不得蒸發、AI 金額/影像紅線", "驗簽、知識命中、Clarify、急件、記憶隔離、dedup", "用正常、假簽章、重送、急件與對抗訊息驅動 LINE 流程；核對 Turn、問題卡、轉人、記憶與 audit", "TS-01、TS-10"),
    "API": ("派工控制", "報價/工單/金流狀態錯誤會產生合約與錯帳", "狀態轉移、金額階梯、SLA、冪等、SoD、audit", "以 API fixture 建立各狀態；送合法/非法轉移、邊界金額、重送、越權與 timeout；核對 HTTP、DB、事件、帳本與 audit", "TS-02–TS-05、TS-10"),
    "WEB": ("多站前端", "前端 gate 不可被當成唯一授權邊界", "APP_MODE 路由、RBAC UX、WS 降級、LIFF、a11y", "用 Playwright 依 APP_MODE/角色走主流，再注入 403、斷網與 WS 中斷；核對路由、操作 gate、提示、後端狀態與 axe 結果", "TS-02、TS-03、TS-08、TS-11"),
    "DAT": ("資料平台", "庫路由、provenance 或 migration drift 會導致隱性污染", "三庫隔離、重套、重跑、bronze-only、hash chain", "以固定 raw/DB fixture 重跑 pipeline/migration，注入 tenant/schema/provenance 變異；比較筆數、hash、來源、drift 與 audit", "TS-07、TS-09、TS-10"),
    "REF": ("知識精煉", "未核可或錯來源知識落地會放大 AI 幻覺", "事實/行為分流、diff、HITL、Publisher、Family review", "用核可、拒絕、重複、錯來源與錯租戶素材跑 intake→diff→HITL→Publisher；對帳 pgvector、skill、git 與 provenance", "TS-07、TS-10"),
    "TEC": ("技師平台", "跨品牌身分與投影易誤放行/過度暴露", "KYC、品牌授權、OHS、接單、CQRS、requote、settlement", "建立有效/未核可/停權技師與多品牌 fixture，跑註冊、媒合、接拒單、requote、投影與結算；核對授權、事件、SLA 與資料最小化", "TS-03、TS-04、TS-06"),
    "PLT": ("平台核心", "集中單點與可編輯配置會放大全品牌 blast radius", "OIDC/RBAC、License、Kafka/Redis、observability、DSL、Config rollout", "以租戶×角色×License 矩陣跑正常與越權操作，再中斷共用元件或推送非法配置；核對 fail-closed、降級、告警、rollback 與 audit", "TS-08、TS-11、TS-12"),
}

NFR_DOMAIN_META = {
    "PERF": ("效能・可用・容量", "設計目標未實測或共用單點未演練", "p95/p99、錯誤率、重播、降級、容量與 SLA 邊界", "依基準、目標與尖峰三段負載執行 k6/浸泡，再逐一中斷依賴；保存 p95/p99、錯誤率、降級、告警與恢復時間", "TS-11"),
    "SEC": ("安全・隱私", "租戶越權、AI 越權、PII 外洩屬上線紅線", "OIDC/RBAC/SoD、加密、tool sandbox、GDPR、retention、投影最小化", "以租戶×角色×資源矩陣執行允許/拒絕案例，加入偽造 token、跨租戶、prompt/tool 攻擊與 GDPR 流程；核對 deny、零副作用及 audit", "TS-08、TS-10"),
    "OPS": ("品質・稽核・維運", "缺乏 provenance/audit/rollback 時無法證明系統正確", "OTel、hash chain、bronze-only、migration、CI、a11y、DORA", "用固定 fixture 重跑、重套與故障恢復，對帳 hash/provenance/trace/報表；再執行 CI 掃描、a11y 人工抽測與 rollback 演練", "TS-07、TS-09–TS-11"),
}

# QA 主視圖使用的可執行語言。舊 DOMAIN_TEST_META 保留給架構/治理附錄，
# 不得再把單純名詞串當成「QA 測試條件」。
DOMAIN_QA_CHECKS = {
    "AGT": (
        "1. 有效簽章應受理；錯誤簽章應拒絕且不建案。\n"
        "2. 可命中知識的問題應引用正確來源；無法回答時應詢問或轉人，不得編造。\n"
        "3. 連續 3 次未釐清或命中急件時，應建立後台案件並轉真人。\n"
        "4. 不同品牌/客戶不得讀到對方對話與記憶。\n"
        "5. 同一事件重送不得重複回覆、建案或轉人。",
        "準備正常/錯誤簽章、可/不可命中問題、急件、跨品牌與重送輸入；逐組核對回覆、後台案件、轉人紀錄與重複資料數。",
    ),
    "API": (
        "1. 允許的狀態變更應成功，非法順序應拒絕且資料不變。\n"
        "2. 499/500/2000/2001 元與 5/10/20 公里等邊界值應落在正確規則。\n"
        "3. 同一請求重送只能有一次實際效果。\n"
        "4. 未授權角色與申請/核准同人情境應被拒絕。\n"
        "5. API 結果、資料庫狀態、事件、帳本與稽核紀錄應一致。",
        "先以正常資料完成一次主流，再每次只改一個條件：非法狀態、邊界值、重送、錯角色或逾時；比對操作前後資料與帳本。",
    ),
    "WEB": (
        "1. 不同站點模式只應進入對應頁面。\n"
        "2. 每個角色只看到可用功能；手動呼叫被隱藏功能的 API 仍應被拒絕。\n"
        "3. 斷網、403 與即時連線中斷時應顯示可理解提示，不可顯示假成功。\n"
        "4. 關鍵頁面應可用鍵盤操作，無關鍵無障礙錯誤。",
        "用 Playwright 以各站點模式與角色完成主流；再斷網、中斷即時連線、注入 403 並手動呼叫無權 API；核對畫面、後端狀態與無障礙掃描。",
    ),
    "DAT": (
        "1. 每類資料只能寫入指定資料庫，不可自動改走其他庫。\n"
        "2. 同一升級與同一輸入重跑後，資料筆數與內容應一致。\n"
        "3. 正式知識只能來自受控原始層，每筆資料必須查得到來源。\n"
        "4. 版本差異與稽核紀錄竄改必須可偵測。",
        "使用固定輸入與空庫/舊版庫各跑一次，再重跑一次；刻意更改租戶、資料庫連線、來源標記、版本與稽核紀錄；比對路由、筆數、hash 與告警。",
    ),
    "REF": (
        "1. 不同內容類型應分到正確審核流程。\n"
        "2. 核可前正式知識庫新增數必須為 0；拒絕後也不得發佈。\n"
        "3. 重送同一來源不得產生重複知識。\n"
        "4. 錯租戶與錯來源的素材應被拒絕。\n"
        "5. 需覆核內容必須 100% 進入指定審核。",
        "用核可、拒絕、重複、錯來源與錯租戶素材完成一輪匯入→差異比對→人審→發佈；核對正式知識庫、版本庫、來源與審核紀錄。",
    ),
    "TEC": (
        "1. 未核可、未受品牌授權、已停權或非排班時段的技師不得入候選池。\n"
        "2. 接單、拒單與逾時必須在品牌端與技師工作台同步。\n"
        "3. 技師只能提出加價事由，不能自行定價。\n"
        "4. 技師工作台只顯示作業所需的最少資料。\n"
        "5. 品牌計費與平台結算差額必須為 0。",
        "建立已核可/未核可/已停權與不同品牌技師，完成註冊、媒合、接拒單、加價與結算；核對候選池、兩端狀態、顯示欄位與帳務差額。",
    ),
    "PLT": (
        "1. 每種角色與品牌只能執行授權內操作，錯誤或過期憑證應拒絕。\n"
        "2. 未取得有效授權的品牌不得開站或使用服務。\n"
        "3. 中斷共用依賴時，系統應明確降級、告警且不污染資料。\n"
        "4. 不合法或超越安全邊界的設定不得發佈。\n"
        "5. 新設定指標異常時必須停止擴大並回復上一版。",
        "以兩個品牌×各角色×有效/無效授權執行正反例；再逐一中斷共用依賴與發佈不合法設定；核對拒絕、降級、告警、回復版本與稽核紀錄。",
    ),
    "PERF": (
        "1. 在基準、目標、尖峰三段負載下量測速度與錯誤率。\n"
        "2. 持續負載期間不可出現記憶體或連線數持續上升。\n"
        "3. 中斷單一依賴時應降級與告警，不得全面雪崩。\n"
        "4. 依賴恢復後，堆積請求與資料應能正確補處理。\n"
        "5. 實測值必須逐項比對文件闀檻。",
        "鎖定版本、資料集與壓測腳本；先跑三段負載，再逐一中斷依賴；保存 p95/p99、錯誤率、降級回應、告警與復原時間。",
    ),
    "SEC": (
        "1. 每種角色必須同時有允許與拒絕案例。\n"
        "2. 錯品牌 ID、偽造/過期憑證與跨品牌存取必須被拒絕，且資料不變。\n"
        "3. AI 被誘導時不得擅自定價、派工、辨識影像或呼叫未授權工具。\n"
        "4. 敏感資料不得出現於非必要 API、畫面、log 與技師投影。\n"
        "5. 個資刪除、保留與稽核應符合規則。",
        "建立品牌×角色×資源矩陣執行正反例；加入錯誤憑證、跨品牌 ID、AI 對抗輸入、個資刪除與法定保留；核對拒絕、資料零變更與稽核紀錄。",
    ),
    "OPS": (
        "1. 同一輸入重跑後，輸出筆數、內容與來源應一致。\n"
        "2. 資料庫升級從空庫與舊版都能完成，重套不失敗。\n"
        "3. 稽核紀錄被更改時必須可偵測。\n"
        "4. 回滾演練必須在規定時間內恢復，並不遺失已確認資料。\n"
        "5. CI、無障礙與發佈指標必須依各自闀檻裁定通過與否。",
        "用固定資料執行重跑、資料庫重套、稽核竄改與回滾演練；比對輸出 hash、來源、trace、報表與恢復時間；再執行 CI 與無障礙掃描。",
    ),
}

SCENARIO_PASS_CRITERIA = {
    "TS-01": "正常訊息有回覆且只處理一次；錯誤簽章不建案；三次未釐清與急件均建立後台案件並轉真人。",
    "TS-02": "未完整資料不得報價；報價與規則快照一致；只有客服明確操作能開單；拒絕或越權不改變狀態。",
    "TS-03": "候選者全數符合品牌、技能、距離與可用條件；接/拒/逾時正確同步；無候選者時進入待處理並告警。",
    "TS-04": "加價落在正確審批層級；技師無法直接定價；客戶拒絕時不套用新價；存證缺一不得結案。",
    "TS-05": "同一請求只有一筆帳；退款保留原交易與反轉紀錄；同一人不能申請又核准；兩端帳務差額為 0。",
    "TS-06": "只有已核可、已授權且在排班中的技師出現在候選池；停權立即生效；敏感原文件不出現在一般 API、log 或畫面。",
    "TS-07": "只有核可內容被發佈；拒絕、錯來源與錯租戶內容落地數為 0；重送不重複；來源、審核人與版本可查。",
    "TS-08": "允許的操作成功；錯品牌、錯角色與無效憑證操作被拒絕且資料無變更；品牌間不得看到對方資料。",
    "TS-09": "空庫與舊版升級結果一致；重套與重跑不重複；不走錯庫；版本差異與稽核竄改均觸發失敗或告警。",
    "TS-10": "未授權與跨品牌操作全數被拒絕且零副作用；AI 不執行金額、派工與影像辨識紅線；刪除、保留與覆核符合規則。",
    "TS-11": "各指標達到 NFR 闀檻；依賴失敗時沒有全面 5xx 或資料污染；降級、告警與 trace 可查；恢復後堆積資料能補處理。",
    "TS-12": "不合法或越界設定發佈數為 0；高風險設定未核可不上線；異常時停止擴大並恢復上一版；審核與發佈紀錄可查。",
}

ARCH_RISKS = [
    ["架構", "R-01", "Casdoor /集中共用元件為跨品牌單點", "全品牌登入、派工或治理受阻", "HA+備份；per-brand bundle fail-soft；演練", "12_SAD §12"],
    ["架構", "R-02", "Kafka schema 治理與消費者相容", "投影、結算或通知靜默失敗", "schema registry + consumer-driven contract + replay", "12_SAD §12"],
    ["架構", "R-04", "品牌自服務配置擴大攻擊面與品質風險", "全品牌 AI 行為或內容劣化", "保護層 + eval gate + staged rollout + rollback + audit", "12_SAD §12 / ADR-012"],
    ["架構", "R-06", "技師平台/OHS 是派工關鍵依賴", "全品牌無法自動媒合", "OHS SLO + cache/queue 降級待裁定 + 契約測試", "12_SAD §12 / 05_NFR Failure Modes"],
    ["契約", "CT-01", "FR-TEC 主鍵碰撞已治理", "報價修正保留 FR-TEC-07；排班生命週期改為 FR-TEC-08", "生成器驗證 FR 全數唯一，QA 映射以新鍵輸出", "04_SRS:355-356"],
    ["契約", "CT-02", "21_Traceability 聲稱使用 SRS FR，主表卻是 FR-0001 舊鍵", "FR→TC 無法直接 join，覆蓋率易被高估", "新增 SRS FR 欄或將舊鍵明確降級為 legacy display", "21_Traceability §2"],
    ["契約", "CT-03", "20_Test_Cases 已建立 171 筆 QTM 正式 SRS REQ→TC 鍵", "90 筆詳細 TC 的舊 FR/來源欄不再承擔現行追溯", "QTM 列數與唯一鍵納入生成驗證；無 QTM 視為文件遺漏", "20_Test_Cases §2.1"],
    ["實作", "IM-01", "文件中既有🔜規劃中文字，又有 2026-07-21 codegraph 標注已落地", "直接以關鍵字統計會誤判實作率", "四書僅表示「需求定版/規劃訊號」，實作完成以 WBS/code/SIT 證據另對帳", "05_NFR 末段 / 27_Roadmap"],
    ["驗收", "QA-01", "部分 SRS/NFR 仍含 [待確認] 量化門檻", "測試可執行但無法客觀判定 pass/fail", "由 PM/Architect 在 UAT 前將門檻、量測點、資料集與 owner 定版", "04_SRS / 05_NFR"],
]

# QTM 正式映射所指定的 TC；詳細 TC 舊來源欄只作歷史稽核。
FR_TC_HINTS = {
    "FR-AGT-01": "TC-CS-AI-01/02",
    "FR-AGT-03": "TC-CS-AI-03",
    "FR-AGT-04": "TC-CS-AI-04 + TC-COMPLIANCE-07",
    "FR-AGT-05": "TC-CS-AI-04/10",
    "FR-AGT-06": "TC-SEC-MEM-01",
    "FR-AGT-07": "TC-CS-AI-03 + TC-COMPLIANCE-08",
    "FR-AGT-08": "TC-SEC-TOOL-01",
    "FR-AGT-09": "TC-CS-AI-04/10",
    "FR-AGT-10": "TC-CS-AI-08/09 + TC-EXC-01",
    "FR-AGT-11": "TC-CS-AI-05~07 + TC-COMPLIANCE-06",
    "FR-API-01": "TC-WO-01/03 + TC-QUOTE-06",
    "FR-API-02": "TC-QUOTE-01~08",
    "FR-API-03": "TC-QUOTE-01/04/05 + 定價引擎 unit",
    "FR-API-04": "TC-WO-01~03/08/09",
    "FR-API-05": "TC-DISPATCH-01",
    "FR-API-06": "TC-DISPATCH-02",
    "FR-API-07": "TC-DISPATCH-04 + TC-WO-10",
    "FR-API-08": "TC-ONSITE-01~05 + TC-WO-04~07",
    "FR-API-09": "TC-WO-04~07 + TC-DISPATCH-08",
    "FR-API-10": "金流 provider contract + TC-SEC-IDEM-01",
    "FR-API-11": "TC-WO-12 + TC-SETTLE-02~05",
    "FR-API-12": "TC-SETTLE-01/07/08",
    "FR-API-13": "TC-SEC-INT-01",
    "FR-API-14": "TC-EXC-06 + WS multi-instance E2E",
    "FR-API-15": "TC-EXC-01 + cron leader/retry suite",
    "FR-API-16": "TC-COMPLIANCE-01/02/04",
    "FR-API-17": "TC-QUOTE-03 + 保固 5-mode suite",
    "FR-API-18": "TC-WO-11 + TC-ONSITE-06 + TC-SETTLE-03/06 + TC-SEC-SOD-01",
    "FR-API-19": "TC-DISPATCH-08",
    "FR-WEB-01": "Playwright APP_MODE route isolation",
    "FR-WEB-02": "TC-SEC-WEB-01/02 + role-ui-isolation",
    "FR-WEB-03": "TC-DISPATCH-03/04 + WS E2E",
    "FR-WEB-04": "reports suite + UAT dashboard",
    "FR-WEB-05": "TC-SETTLE-07 + audit-events E2E",
    "FR-WEB-06": "TC-QUOTE-01/04/05/07/08 + TC-A11Y-01",
    "FR-WEB-07": "error-boundary/offline E2E",
    "FR-DAT-01": "TC-COMPLIANCE-08",
    "FR-DAT-02": "TC-SEC-PIPE-01",
    "FR-DAT-03": "TC-EXC-05 + TC-SEC-TENANT-01",
    "FR-DAT-04": "TC-CS-AI-03 + RAG integration",
    "FR-DAT-05": "TC-EXC-06 + 同步鏈對帳",
    "FR-DAT-06": "TC-SETTLE-07",
    "FR-REF-01": "TC-COMPLIANCE-08 + UAT S3",
    "FR-REF-02": "refinery facts/behavior split suite",
    "FR-REF-03": "TC-COMPLIANCE-05 + UAT S3",
    "FR-REF-04": "TC-COMPLIANCE-08 + Publisher gate",
    "FR-REF-05": "TC-COMPLIANCE-05",
    "FR-TEC-01": "technician lifecycle suite",
    "FR-TEC-02": "TC-DISPATCH-06 + KYC suite",
    "FR-TEC-03": "TC-DISPATCH-01/06 + TC-PERF-03",
    "FR-TEC-04": "TC-DISPATCH-03/04 + TC-EXC-06",
    "FR-TEC-05": "TC-DISPATCH-05 + TC-EXC-06",
    "FR-TEC-06": "TC-SETTLE-01/08",
    "FR-TEC-07": "TC-DISPATCH-07 + TC-ONSITE-07（requote）",
    "FR-TEC-08": "TC-TEC-LIFE-01（排班／停權／認證撤銷）",
    "FR-PLT-01": "OIDC live E2E + TC-SEC-WEB-02",
    "FR-PLT-02": "TC-SEC-RBAC-01~05",
    "FR-PLT-03": "UAT 開站 dry-run",
    "FR-PLT-04": "TC-EXC-06 + WS/cron multi-instance",
    "FR-PLT-05": "TC-EXC-02/03 + provider failover",
    "FR-PLT-06": "observability drill + TC-CS-AI-05",
    "FR-PLT-07": "Flow DSL state/guard/block contract",
    "FR-PLT-08": "UAT S5 + staged rollout/rollback",
    "FR-PLT-09": "platform surface isolation E2E",
}

NFR_TC_HINTS = {
    "NFR-Perf-001": "TC-PERF-01/02",
    "NFR-Perf-007": "TC-PERF-03",
    "NFR-Perf-009": "TC-PERF-05",
    "NFR-Avail-010": "TC-EXC-04",
    "NFR-Scal-001": "TC-PERF-01",
    "NFR-Scal-002": "TC-PERF-02/04",
    "NFR-Sec-003": "TC-SEC-RBAC-01~05 + TC-SEC-SOD-01",
    "NFR-Sec-005": "TC-SEC-INJ-01",
    "NFR-Sec-006": "TC-SEC-INJ-02",
    "NFR-Sec-008": "TC-CS-AI-05",
    "NFR-Sec-009": "TC-COMPLIANCE-06",
    "NFR-Sec-010": "TC-CS-AI-02",
    "NFR-Sec-011": "TC-SEC-INT-01",
    "NFR-Sec-012": "TC-SEC-TOOL-01",
    "NFR-Priv-005": "TC-COMPLIANCE-01/02",
    "NFR-Priv-006": "TC-SEC-TENANT-01 + TC-SEC-MEM-01",
    "NFR-Priv-008": "TC-COMPLIANCE-01/04",
    "NFR-Aud-001": "TC-SETTLE-07",
    "NFR-Aud-004": "TC-COMPLIANCE-05",
    "NFR-DQ-001": "TC-COMPLIANCE-08",
    "NFR-DQ-003": "TC-COMPLIANCE-08 + pipeline rerun",
    "NFR-Sch-002": "TC-SEC-PIPE-01",
    "NFR-A11y-002": "TC-A11Y-01/02",
    "NFR-Comp-001": "TC-COMPLIANCE-07",
    "NFR-Comp-002": "TC-COMPLIANCE-05",
    "NFR-Comp-003": "TC-COMPLIANCE-06",
    "NFR-Comp-004": "TC-COMPLIANCE-01~04",
}
