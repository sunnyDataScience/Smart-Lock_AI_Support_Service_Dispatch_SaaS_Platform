-- 040-quote-catalog.sql
--
-- WHY（CR-0034 S4 / 2026-06-17 會議決議 5 + esales 報價資料庫）：
--   報價基礎主檔（服務/材料/加價規則）在 code 完全缺，是報價引擎(CR-0032)與金流(CR-0035)的上游。
--   會議決議 5 明示「Irene 報價數字當 mock data 灌進系統，實際運營可動態調整」→ 本 migration 依此
--   把 esales xlsx 的服務/材料/加價規則結構 + 草稿值灌為 **mock（is_mock=TRUE）**。
--
-- WHAT：
--   service_catalog(28 服務) / material_catalog(20 材料) / surcharge_rule(12 規則) 三表 + seed。
--   數值來源：AI_Blue_鎖匠ERP_報價資料庫_PhaseI_MarketLaunchCore_v1（人工轉寫，非自動 copy）。
--   **全部 is_mock=TRUE、decision_status 保留原「待填價/待決策/已知規格」** —— 區域/取消費屬「已知規格」
--   (ADR-0102)；急件/夜間/假日/S5 取消費屬「待決策」(esales sheet 13 Q-03~Q-06/Q-08)。
--   正式價/規則待業主回 esales Q-01~Q-12 後從 mock 轉正式（另 workflow，不在本 migration）。
--
-- 影響：純新增表 + seed（ON CONFLICT DO NOTHING idempotent）。tenant_id 預留（CR-0031）。

CREATE TABLE IF NOT EXISTS service_catalog (
    service_code            VARCHAR(40) PRIMARY KEY,
    category                VARCHAR(60),
    service_name            VARCHAR(120) NOT NULL,
    service_type            VARCHAR(30),                 -- inspection/emergency/replacement/repair
    material_class          VARCHAR(40),
    unit                    VARCHAR(20),
    needs_dispatch          VARCHAR(10),                 -- 是/否/可選
    cross_zone              VARCHAR(10),
    internal_note           TEXT,
    internal_base_cost      NUMERIC(12,2),               -- 內部基礎成本（mock）
    suggested_customer_price NUMERIC(12,2),              -- 建議客戶基礎價（mock）
    decision_status         VARCHAR(30) DEFAULT '待填價',
    is_mock                 BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id               UUID,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS material_catalog (
    material_code           VARCHAR(40) PRIMARY KEY,
    category                VARCHAR(60),
    material_name           VARCHAR(120) NOT NULL,
    material_class          VARCHAR(40),
    unit                    VARCHAR(20),
    spec_note               TEXT,
    needs_evidence          BOOLEAN,
    internal_cost           NUMERIC(12,2),
    suggested_price         NUMERIC(12,2),
    decision_status         VARCHAR(40) DEFAULT '待填價｜待採購覆核',
    is_mock                 BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id               UUID,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS surcharge_rule (
    rule_code               VARCHAR(40) PRIMARY KEY,
    rule_type               VARCHAR(30),                 -- 區域/急件/夜間/假日/取消費/有效期
    rule_name               VARCHAR(120),
    condition_note          TEXT,
    unit                    VARCHAR(20),
    amount                  NUMERIC(12,2),               -- 數值型規則（區域/取消費）；規則型存 value_text
    value_text              TEXT,                        -- 非純數值規則（如「50% from final quote」「待定固定額/百分比」）
    decision_status         VARCHAR(30),                 -- 已知規格 / 待決策
    note                    TEXT,
    is_mock                 BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id               UUID,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_service_catalog_type ON service_catalog (service_type);
CREATE INDEX IF NOT EXISTS idx_material_catalog_class ON material_catalog (material_class);

-- ── seed（mock；人工轉寫自 esales MarketLaunchCore v1，決議 5）──────────────
INSERT INTO service_catalog (service_code, category, service_name, service_type, material_class, unit, needs_dispatch, cross_zone, internal_note, internal_base_cost, suggested_customer_price, decision_status) VALUES
('SVC-RES-001','住宅/商業鎖匠','到府檢測','inspection','一般','次','是','否','現場狀況需由真人確認',100,800,'待填價'),
('SVC-RES-002','住宅/商業鎖匠','住宅開鎖一般鎖','emergency','一般','次','是','否','涉及合法授權與現場狀況',300,750,'待填價'),
('SVC-RES-003','住宅/商業鎖匠','住宅開鎖多段鎖','emergency','一般','次','是','否','涉及合法授權與現場狀況',500,1500,'待填價'),
('SVC-RES-004','住宅/商業鎖匠','商業空間開鎖','emergency','一般','次','是','否','涉及合法授權與現場狀況',500,3500,'待填價'),
('SVC-RES-005','住宅/商業鎖匠','機械鎖更換','replacement','一般','次','是','否','材料另計',500,1500,'待填價'),
('SVC-RES-006','住宅/商業鎖匠','加裝副鎖','replacement','一般','次','是','否','材料另計',300,700,'待填價'),
('SVC-ELK-001','電子鎖','電子鎖安裝（本店購買）','replacement','電子鎖','次','是','否','需門片正背面、側面、門框照片',500,2000,'待填價'),
('SVC-ELK-002','電子鎖','電子鎖代工安裝（客戶自備鎖）','replacement','電子鎖','次','是','否','僅涵蓋安裝品質，產品故障不屬本店保固',500,3500,'待填價'),
('SVC-ELK-003','電子鎖','電子鎖故障檢測','inspection','電子鎖','次','是','否','品牌、型號、症狀必填',300,1000,'待填價'),
('SVC-ELK-004','電子鎖','電子鎖維修工資','repair','電子鎖','次','是','否','材料另計',300,1500,'待填價'),
('SVC-ELK-005','電子鎖','面板/觸控無反應檢測','inspection','電子鎖','次','是','否','電池正常仍無反應需派工',300,1000,'待填價'),
('SVC-ELK-006','電子鎖','異常耗電檢測','inspection','電子鎖','次','是','否','換正確電池仍復發需派工',300,1000,'待填價'),
('SVC-ELK-007','電子鎖','馬達異常檢測','inspection','電子鎖','次','是','否','例如紅燈閃 4 次，仍依品牌 SOP 確認',300,1000,'待填價'),
('SVC-ELK-008','電子鎖','管理者權限初始化','repair','電子鎖','次','是','否','恢復原廠設定皆需技師到場',300,1000,'待填價'),
('SVC-ELK-009','電子鎖','App 綁定 / Wi-Fi 設定到府協助','repair','電子鎖','次','是','否','遠端排查失敗才派工',300,1000,'待填價'),
('SVC-DOOR-001','門片結構','門片反弓調整','repair','門片','次','是','否','電話無法排除，需到場',300,800,'待填價'),
('SVC-DOOR-002','門片結構','鉸鏈歪斜 / 門下沉調整','repair','門片','次','是','否','需到場',300,800,'待填價'),
('SVC-DOOR-003','門片結構','受口片 / 門框調整','repair','門片','次','是','否','需到場',300,800,'待填價'),
('SVC-DOOR-004','門片結構','鎖體位移 / 機械損傷處理','repair','門片','次','是','否','需到場',300,800,'待填價'),
('SVC-KEY-001','鑰匙與門禁','一般鑰匙複製','replacement','鑰匙','支','否','可選','視種類',50,150,'待填價'),
('SVC-KEY-002','鑰匙與門禁','特殊鑰匙複製','replacement','鑰匙','支','否','否','視種類',30,150,'待填價'),
('SVC-ACS-001','鑰匙與門禁','門禁卡 / 磁扣拷貝','replacement','門禁','個','否','否','需先確認規格',50,200,'待填價'),
('SVC-ACS-002','鑰匙與門禁','遙控器拷貝','replacement','門禁','個','否','否','需先確認規格',1000,2500,'待填價'),
('SVC-CAR-001','汽機車','汽車開鎖','emergency','車用','次','是','否','需確認車種與合法授權',1000,1500,'待填價'),
('SVC-CAR-002','汽機車','機車開鎖','emergency','車用','次','是','否','需確認車種與合法授權',1000,1500,'待填價'),
('SVC-CAR-003','汽機車','汽車晶片鑰匙評估','inspection','車用','次','可選','否','型號與現場評估',1000,3500,'待填價'),
('SVC-CAR-004','汽機車','汽車遙控器評估','inspection','車用','次','可選','否','型號與現場評估',1000,1000,'待填價'),
('SVC-STORE-001','門市其他','刻印 / 印章代工','replacement','門市','件','否','否','可郵寄',50,800,'待填價'),
('SVC-STORE-002','門市其他','名片代印 / 貼紙','replacement','門市','件','否','否','可郵寄',50,350,'待填價')
ON CONFLICT (service_code) DO NOTHING;

INSERT INTO material_catalog (material_code, category, material_name, material_class, unit, spec_note, needs_evidence, internal_cost, suggested_price, decision_status) VALUES
('MAT-LOCK-001','鎖具','機械主鎖','主鎖','個','依實際 SKU 建立',TRUE,100,500,'待填價｜待採購覆核'),
('MAT-LOCK-002','鎖具','副鎖','副鎖','個','依實際 SKU 建立',TRUE,160,800,'待填價｜待採購覆核'),
('MAT-LOCK-003','鎖具','鎖芯','鎖芯','個','依尺寸 / 規格建立',TRUE,70,350,'待填價｜待採購覆核'),
('MAT-LOCK-004','鎖具','電子鎖整鎖','主鎖','台','依品牌 / 型號建立 SKU',TRUE,3000,15000,'待填價｜待採購覆核'),
('MAT-DOOR-001','門片配件','受口片','配件','個','依門框規格',TRUE,60,300,'待填價｜待採購覆核'),
('MAT-DOOR-002','門片配件','側板','配件','個','依鎖體位置與規格',TRUE,60,300,'待填價｜待採購覆核'),
('MAT-DOOR-003','門片配件','鉸鏈','配件','組','依門片規格',TRUE,100,500,'待填價｜待採購覆核'),
('MAT-ELK-001','電子鎖零件','面板','配件','個','依品牌 / 型號',TRUE,160,800,'待填價｜待採購覆核'),
('MAT-ELK-002','電子鎖零件','馬達模組','配件','個','依品牌 / 型號',TRUE,160,800,'待填價｜待採購覆核'),
('MAT-ELK-003','電子鎖零件','IC 板','配件','個','依品牌 / 型號',TRUE,200,1000,'待填價｜待採購覆核'),
('MAT-ELK-004','電子鎖零件','Wi-Fi 模組','配件','個','依品牌 / 型號',TRUE,40,200,'待填價｜待採購覆核'),
('MAT-PWR-001','耗材','鹼性電池','耗材','組','註明顆數與品牌',FALSE,60,300,'待填價｜待採購覆核'),
('MAT-PWR-002','耗材','9V 緊急供電電池','耗材','顆','緊急處理使用',FALSE,30,150,'待填價｜待採購覆核'),
('MAT-ACS-001','門禁','門禁卡','配件','張','依頻率 / 規格',FALSE,20,100,'待填價｜待採購覆核'),
('MAT-ACS-002','門禁','磁扣','配件','個','依頻率 / 規格',FALSE,20,100,'待填價｜待採購覆核'),
('MAT-ACS-003','門禁','遙控器','配件','個','依頻率 / 規格',FALSE,30,150,'待填價｜待採購覆核'),
('MAT-KEY-001','鑰匙','一般鑰匙胚','耗材','支','依規格建立 SKU',FALSE,30,150,'待填價｜待採購覆核'),
('MAT-KEY-002','鑰匙','特殊鑰匙胚','耗材','支','依規格建立 SKU',FALSE,40,200,'待填價｜待採購覆核'),
('MAT-MISC-001','耗材','螺絲 / 固定耗材','耗材','組','可併入工資或獨立計價',FALSE,40,200,'待決策｜待採購覆核'),
('MAT-MISC-002','耗材','其他現場耗材','耗材','項','需備註與照片',TRUE,20,100,'待填價｜待採購覆核')
ON CONFLICT (material_code) DO NOTHING;

INSERT INTO surcharge_rule (rule_code, rule_type, rule_name, condition_note, unit, amount, value_text, decision_status, note) VALUES
('DIST-01','區域','同區 same_zone','林口、新莊為主要服務區','TWD',500,NULL,'已知規格','可依合約覆寫'),
('DIST-02','區域','跨區 cross_zone','其他區域需評估；跨區安裝僅限電子門鎖','TWD',800,NULL,'已知規格','可依合約覆寫'),
('DIST-03','區域','偏遠 remote','偏遠地區','TWD',1200,NULL,'已知規格','可依合約覆寫'),
('URG-01','急件','locked_out / trapped_inside / safety_risk','可先派工，4 小時內補 retrospective quote audit','加價方式',1500,'暫定固定額 1500，待定固定額或百分比','待決策','esales Q-03'),
('TIME-01','夜間','夜間服務','需定義起訖時間','加價方式',2000,'暫定 2000，待填時段與固定額/百分比','待決策','esales Q-04'),
('HOL-01','假日','假日服務','需定義週末、國定假日或連假','加價方式',2000,'暫定 2000，待填適用日與固定額/百分比','待決策','esales Q-05'),
('CNL-S1','取消費','S1 尚未指派','取消費 0','TWD',0,NULL,'已知規格','ADR-0102'),
('CNL-S1.5','取消費','S1.5 已指派但師傅未出發','取消費 0','TWD',0,NULL,'已知規格','ADR-0102'),
('CNL-S2','取消費','S2 師傅已出發','取消費','TWD',300,NULL,'已知規格','ADR-0102'),
('CNL-S3','取消費','S3 師傅接近 / 已安排時段','取消費','TWD',500,NULL,'已知規格','ADR-0102'),
('CNL-S4','取消費','S4 師傅已到場','取消費','TWD',800,NULL,'已知規格','ADR-0102'),
('CNL-S5','取消費','S5 已施工 / 已使用材料','全額或依實際工項','規則',NULL,'50% from the final quote（待定義計算方式）','待決策','esales Q-06')
ON CONFLICT (rule_code) DO NOTHING;

COMMENT ON TABLE service_catalog IS 'CR-0034 服務主檔（28 服務）；數值為 esales mock(is_mock)，正式價待業主回 esales Q-01';
COMMENT ON TABLE material_catalog IS 'CR-0034 材料主檔（20 材料）；mock，待採購覆核(esales Q-02)';
COMMENT ON TABLE surcharge_rule IS 'CR-0034 加價/取消費規則；區域+取消費已知規格(ADR-0102)，急件/夜間/假日/S5 待決策(esales Q-03~Q-06)';
