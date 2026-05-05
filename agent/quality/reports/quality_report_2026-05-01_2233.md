# Quality Report — 2026-05-01 22:33

- **總案例數**: 67
- **通過率**: 84% (56/67)

## 摘要

| Verdict | Count | Ratio |
| :--- | ---: | ---: |
| Pass | 56 | 84% |
| Partial | 7 | 10% |
| Fail | 3 | 4% |
| Error | 1 | 1% |

## 分類表現

| Category | Pass | Partial | Fail | Error | Total | Pass Rate |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 硬體維修 | 15 | 3 | 2 | 1 | 21 | 71% |
| 報價客服 | 9 | 1 | 0 | 0 | 10 | 90% |
| 門市規格 | 8 | 2 | 0 | 0 | 10 | 80% |
| APP設定 | 8 | 1 | 1 | 0 | 10 | 80% |
| 多意圖 | 5 | 0 | 0 | 0 | 5 | 100% |
| 圍籬測試 | 5 | 0 | 0 | 0 | 5 | 100% |
| 品牌路由 | 6 | 0 | 0 | 0 | 6 | 100% |

## 未通過案例（11 筆）

### [ERR] H-5 — 硬體維修

- **Question**: 鎖舌在室內拉不開門的緊急處理？
- **Expected**: 指導「先將門推緊，再拉動把手」的緩解動作。
- **Keywords**: 0/0
- **Skills**: -
- **Elapsed**: 0s
- **Reason**: litellm.RateLimitError: litellm.RateLimitError: vertex_aiException - {
  "error": {
    "code": 429,
    "message": "Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.",
    "status": "RESOURCE_EXHAUSTED"
  }
}
- **Answer**:

  ```
  ERROR: litellm.RateLimitError: litellm.RateLimitError: vertex_aiException - {
    "error": {
      "code": 429,
      "message": "Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.",
      "status": "RESOURCE_EXHAUSTED"
    }
  }
  ```

### [WARN] H-6 — 硬體維修

- **Question**: 鎖在室外推不開門的緊急處理？
- **Expected**: 指導「先拉緊把手使門閉合，完成解鎖後再用力推動」。
- **Keywords**: 1/3
- **Skills**: troubleshoot
- **Elapsed**: 18.0s
- **Reason**: AI建議解鎖後「拉開」門，與預期方向的「推動」門相反，且初始動作描述與預期略有不同。
- **Answer**:

  ```
  在室外如果門推不開，通常是門跟門框有點錯位或卡住，導致鎖舌的摩擦力太大。
  
  您可以試試看，先把門往「推」的方向推緊，讓門跟門框更密合，然後再試一次解鎖。解鎖成功後，再把門拉開。
  
  這招通常可以解決大部分的狀況，如果還是不行，可以找找看鎖體下方有沒有緊急鑰匙的插孔，通常會有個小蓋子，打開就能用備用鑰匙開門了。
  ```

### [WARN] H-7 — 硬體維修

- **Question**: 門扇反弓會對鎖舌造成什麼具體影響？
- **Expected**: 指出鉸鏈區域擠壓問題會導致鎖舌與受口片卡澀難開，也可能會無法開啟。需將門先拉緊或推緊後解鎖，再放開手才能開門。
- **Keywords**: 3/4
- **Skills**: troubleshoot, ts-door-rebound
- **Elapsed**: 22.1s
- **Reason**: AI回答指出了鎖舌對不準導致卡澀難開和無法上鎖，但未提及需要拉緊或推緊門才能解鎖的具體影響。
- **Answer**:

  ```
  您好，門扇反弓通常是門扇本身或鉸鏈（後鈕）的問題，而不是電子鎖故障喔。
  
  當門扇反弓時，會讓鎖舌跟門框的鎖孔對不準，這可能造成幾個主要影響：
  1.  **自動上鎖失敗**：關門後因為鎖舌對不準，沒辦法順利伸出並鎖上。
  2.  **開關門卡卡的**：會感覺門很難推或拉，開關不順暢。
  3.  **門縫過大**：門關上後，門扇跟門框之間還有很明顯的縫隙。
  
  這個問題需要師傅到現場調整門扇或鉸鏈才能解決，請問需要幫您安排嗎？
  ```

### [FAIL] H-9 — 硬體維修

- **Question**: Dormakaba 雙重認證模式啟動後會有什麼現象？
- **Expected**: 說明單一指紋或密碼或卡片將無法開門，需兩者同時驗證。如果只有管理者密碼可以開門，但是其他卡片或是指紋無法開門，就是啟動的雙重驗證模式，需將其解除。
- **Keywords**: 1/4
- **Skills**: ss-dormakaba, product-knowledge
- **Elapsed**: 17.8s
- **Reason**: AI未能直接回答問題，而是將問題轉介給專人，表示其無法提供預期的資訊。
- **Answer**:

  ```
  關於 Dormakaba 的雙重認證模式，這個問題比較特殊，我需要請專人為您確認相關的設定細節。
  
  請問方便留下您的聯絡電話嗎？或者您也可以直接來電，我們的技術專員會更清楚地跟您說明。
  ```

### [WARN] S-7 — 報價客服

- **Question**: 如果我想更換整組鎖體，建議先準備什麼資料？
- **Expected**: 引導使用者提供現有門鎖的照片與門厚資訊以利作業，以及需提供欲安裝的品牌及型號。
- **Keywords**: 2/4
- **Skills**: dispatch-guide
- **Elapsed**: 8.3s
- **Reason**: AI回答有引導使用者提供門鎖照片，但遺漏了門厚資訊以及詢問欲安裝的品牌及型號。
- **Answer**:

  ```
  好的，如果您想更換家裡的鎖，可以先準備幾樣東西，這樣我們就能更快幫您評估適合的型號喔！
  
  麻煩您方便的時候，幫我拍幾張照片：
  1.  整扇門的正面照
  2.  門邊鎖舌跑出來的地方（我們叫鎖匣）
  3.  順便量一下門邊那片金屬側板的長度跟寬度
  
  有這些資料，我們就能判斷哪款鎖最適合您，避免安裝時還要另外修改門的風險。
  ```

### [WARN] W-4 — 門市規格

- **Question**: 電子鎖完全沒電時，有哪些緊急供電方案？
- **Expected**: 指導使用 9V 方型電池或行動電源透過 USB 接孔供電。
- **Keywords**: 1/3
- **Skills**: troubleshoot, ts-power-drain-chatlock
- **Elapsed**: 17.8s
- **Reason**: AI回答了行動電源供電方式，但遺漏了9V方型電池供電，並加入了非供電類的機械鑰匙方案。
- **Answer**:

  ```
  如果您的 AI-99 電子鎖完全沒電了，別擔心，有兩種方式可以緊急開門：
  
  1.  **使用行動電源供電**：
      *   在電子鎖外側門把中間偏下方，有個圓形的蓋子。
      *   把它往下壓然後向右轉，蓋子就會打開。
      *   左邊是 Type-C 的充電孔，拿行動電源接上去，電子鎖就會被喚醒，發出「嗶」一聲。這時候就可以用指紋或密碼正常開門了。
  
  2.  **使用備用機械鑰匙**：
      *   一樣打開那個圓形蓋子。
      *   右邊就是鑰匙孔，把備用鑰匙插進去轉動，門鎖發出「嗶」聲後，就可以開門了。
  
  提醒一下，備用鑰匙最好放在車上或辦公室，不要放在家裡喔！
  ```

### [WARN] W-6 — 門市規格

- **Question**: 老人家指紋較淺，在設定上有什麼建議？
- **Expected**: 建議同一手指重複設定 3 次以上，或改用人臉、掌靜脈。
- **Keywords**: 0/3
- **Skills**: product-knowledge
- **Elapsed**: 21.6s
- **Reason**: AI回答了指紋設定的建議，但遺漏了改用人臉或掌靜脈等替代方案。
- **Answer**:

  ```
  好的，老人家指紋比較淺，辨識起來會比較辛苦一點，這很常見。
  
  建議可以多設定幾組不同的手指，例如食指、中指都設定上去，增加辨識的成功率。在設定同一隻手指時，也可以稍微換一下角度，讓感應器紀錄指紋的不同區域，這樣開門時就算手指擺得比較歪，也比較容易成功。
  
  另外，不同品牌的設定方式會有點不一樣，請問您家的電子鎖是哪個品牌跟型號呢？這樣我可以提供更準確的建議喔。
  ```

### [WARN] Y-2 — APP設定

- **Question**: 如何在 AS701 上新增 RFID 感應卡？
- **Expected**: 按下登記鍵後，將卡片貼近感應區並按 * 鍵完成。
- **Keywords**: 1/3
- **Skills**: product-knowledge
- **Elapsed**: 10.3s
- **Reason**: AI回答提供了手冊連結而非直接給出操作步驟，與預期方向的直接指示方式不符。
- **Answer**:

  ```
  好的，關於 Dormakaba AS701 如何新增感應卡，您可以直接參考這份原廠的操作手冊，裡面有完整的設定步驟說明。
  
  這是手冊的連結：https://drive.google.com/file/d/1khDfWOjNoYEqKq6s-WEaaEFtUpAXCMWO/view
  
  您可以直接點開連結，按照裡面的教學操作新增卡片。如果操作上還有遇到什麼問題，隨時都可以再問我喔！
  ```

### [FAIL] Y-5 — APP設定

- **Question**: 如何設定 AS701 的遙控器功能？
- **Expected**: 按下登記鍵後，按下遙控器 OPEN 鍵並以 * 鍵確認。
- **Keywords**: 1/3
- **Skills**: product-knowledge
- **Elapsed**: 21.5s
- **Reason**: AI 回答未提供預期方向中提及的具體按鍵操作步驟，而是引導使用者參考 APP 和手冊。
- **Answer**:

  ```
  關於 Dormakaba AS701 的遙控器功能，通常會需要透過專屬的 APP 來進行設定。
  
  您可以參考這兩份原廠的操作手冊，裡面有詳細的圖文教學：
  
  - Dormakaba APP 操作手冊：
  https://drive.google.com/file/d/1lSdrdkjE9Jeh-sqXhylQvAvGxDO3S4eV/view
  
  - Dormakaba APP 遠端操作說明：
  https://drive.google.com/file/d/1Ii4vdaz8_kGdUUtc0p_sep5LI8i09RML/view
  
  基本上跟著手冊的步驟一步步設定就可以了。如果設定過程中有遇到什麼問題，再隨時跟我說！
  ```

### [WARN] E-7 — 硬體維修

- **Question**: 請問我的門可以安裝嗎？
- **Expected**: 請客戶提供門的正面、背面、側面、門框位置的照片以進行評估
- **Keywords**: 2/3
- **Skills**: dispatch-guide
- **Elapsed**: 4.5s
- **Reason**: AI回答有要求提供照片以評估，但遺漏了預期中『背面』和『門框位置』的照片要求，並增加了額外問題。
- **Answer**:

  ```
  好的，沒問題！
  
  為了幫您確認門扇是否適合安裝，需要請您提供一些資訊。
  
  請問是新買的門要安裝，還是舊門要換成電子鎖呢？另外，方便的話，可以拍幾張門的正面、側面，和現在鎖的位置照片給我嗎？這樣我能更快幫您判斷喔！
  ```

### [FAIL] E-8 — 硬體維修

- **Question**: 我下單了
- **Expected**: 請客戶提供訂單編號、型號、購買通路、聯絡人、電話、安裝地址等資訊
- **Keywords**: 0/3
- **Skills**: -
- **Elapsed**: 10.8s
- **Reason**: AI 回答過於籠統，沒有主動要求客戶提供訂單相關的具體資訊，與預期方向不符。
- **Answer**:

  ```
  好的，請問有什麼需要我幫忙的嗎？例如想預約安裝，或是有其他問題呢？
  ```
