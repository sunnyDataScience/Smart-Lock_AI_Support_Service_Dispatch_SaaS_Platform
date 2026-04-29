-- inventory_items + inventory_transactions seed
-- 庫存表為全公司共用（無 tenant_id）；提供混合 in_stock / low_stock / out_of_stock 樣本以便 UI 展示
-- idempotent：ON CONFLICT (part_number) DO NOTHING

BEGIN;

INSERT INTO inventory_items (id, part_number, name, category, brand_compatibility, unit_cost, quantity_on_hand, reorder_point, supplier, is_active, created_at, updated_at)
VALUES
  ('a1000000-0000-0000-0000-000000000001', 'BAT-AA-001',  'AA 鹼性電池 (4入)',     'battery',       '["Yale","Samsung","Philips","Chatlock"]', 80,   245, 50, '永豐電池',   TRUE, NOW() - INTERVAL '90 days', NOW()),
  ('a1000000-0000-0000-0000-000000000002', 'BAT-LI-002',  '鋰電池模組 18650',      'battery',       '["Chatlock","Dormakaba"]',                 320,  18,  30, '台灣鋰電',   TRUE, NOW() - INTERVAL '85 days', NOW()),
  ('a1000000-0000-0000-0000-000000000003', 'FP-MOD-015',  '指紋辨識模組',          'circuit_board', '["Yale","Chatlock"]',                      850,  0,   20, 'Synaptics 代理', TRUE, NOW() - INTERVAL '80 days', NOW()),
  ('a1000000-0000-0000-0000-000000000004', 'WIFI-MOD-008','WiFi 通訊模組 ESP32',  'circuit_board', '["Chatlock","Samsung"]',                   240,  89,  25, 'ESP 代理',   TRUE, NOW() - INTERVAL '75 days', NOW()),
  ('a1000000-0000-0000-0000-000000000005', 'LB-SS-021',   '不鏽鋼鎖體 304',         'lock_body',     '["Yale","Dormakaba","美樂"]',              1200, 8,   15, '台中鎖業',   TRUE, NOW() - INTERVAL '70 days', NOW()),
  ('a1000000-0000-0000-0000-000000000006', 'IC-RDR-044',  'IC 卡讀取器',            'circuit_board', '["Samsung","Chatlock"]',                   480,  0,   10, 'NFC 代理',   TRUE, NOW() - INTERVAL '65 days', NOW()),
  ('a1000000-0000-0000-0000-000000000007', 'TP-CAP-027',  '電容式觸控面板',         'side_panel',    '["Chatlock","Yale"]',                      650,  156, 40, '觸控科技',   TRUE, NOW() - INTERVAL '60 days', NOW()),
  ('a1000000-0000-0000-0000-000000000008', 'SCR-M3-100',  'M3 不鏽鋼螺絲 (100入)', 'screw',         null,                                       45,   320, 80, '佳順五金',   TRUE, NOW() - INTERVAL '55 days', NOW())
ON CONFLICT (part_number) DO NOTHING;

-- 為部分品項插入最近一次 purchase 紀錄（last_restocked_at 衍生欄位來源）
INSERT INTO inventory_transactions (item_id, transaction_type, quantity, notes, created_at)
VALUES
  ('a1000000-0000-0000-0000-000000000001', 'purchase', 200, '常規補貨', NOW() - INTERVAL '19 days'),
  ('a1000000-0000-0000-0000-000000000002', 'purchase', 50,  '常規補貨', NOW() - INTERVAL '38 days'),
  ('a1000000-0000-0000-0000-000000000004', 'purchase', 80,  '常規補貨', NOW() - INTERVAL '11 days'),
  ('a1000000-0000-0000-0000-000000000005', 'purchase', 25,  '常規補貨', NOW() - INTERVAL '55 days'),
  ('a1000000-0000-0000-0000-000000000007', 'purchase', 150, '常規補貨', NOW() - INTERVAL '9 days');

COMMIT;
