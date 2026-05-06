"""品質檢測腳本 — UAT 測試題目（依 50題測試題目.xlsx 設計）驗證 agent 回答水準。

題庫範圍：
  - 50 道主測試（H-1~H-10、S-1~S-10、W-1~W-10、Y-1~Y-10、M-1~M-5、G-1~G-5）
  - 11 道實戰追加（E-1~E-11，硬體維修延伸案例）
  - 6 道品牌路由補強（B-1~B-6，驗證 brand-specific skill 載入）

用法：
  cd agent && python -m quality.quality_check                # 完整測試（含 LLM-as-Judge）
  cd agent && python -m quality.quality_check --no-judge     # 只跑 agent 回答 + 關鍵詞
  cd agent && python -m quality.quality_check --judge-only   # 用現有 JSON 重跑 LLM 評分
  cd agent && python -m quality.quality_check --retry-failed # 只重測上次非 pass 的案例，更新報告

輸出：quality/quality_report.json + quality/quality_report.html
"""

import os
import sys
import json
import re
import asyncio
import time
import argparse
from dataclasses import dataclass, asdict

# 與 production debounce.py 一致：剝除 LLM 可能誤抄的 [已參考: ...] / [已參考技能: ...]
_REF_MARKER_RE = re.compile(r"\s*\[已參考(?:技能)?:[^\]]*\][\s,，]*")


def _strip_ref_markers(text: str) -> str:
    return _REF_MARKER_RE.sub("", text).strip()


# Quick Reply 模擬：production 在 brand 未知時會透過 LINE Quick Reply 強制收集品牌，
# 用戶點選後才進 agent。test 環境沒有 LINE，當 device_brand 未設且
# infer_brand_from_text 失敗時，模擬「用戶透過 Quick Reply 選了預設品牌」。
# 預設選 Chatlock —— 這是有完整 mega-doc 且最常見的品牌，對大多數 brand-agnostic
# 問題（店家資訊、安裝流程、保固等）影響中性，因為 LLM 仍會載入 _common/*。
QUICK_REPLY_DEFAULT_BRAND = "Chatlock"

# 將 agent/ 加入 sys.path，讓 agent_tools / harness / product_info 等模組可 import
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _AGENT_DIR)

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(_AGENT_DIR, "..", ".env"))

from langchain_litellm import ChatLiteLLM
from core.config import load_config
from agent import build_agent
from langgraph.checkpoint.memory import MemorySaver
from llms import get_llm
from llms.litellm_model import _ensure_vertex_credentials, build_litellm

# ─────────────────────────────────────────────
# 測試案例定義
# ─────────────────────────────────────────────


@dataclass
class TestCase:
    id: str
    category: str
    question: str
    expected: str
    keywords: list[str]  # 回答中應包含的關鍵詞（至少命中一半算 keyword pass）
    device_brand: str = ""  # 品牌路由測試用：注入 [用戶資料] + [可用技能] 前綴
    device_model: str = ""  # 型號路由測試用
    auto_reply: str = ""    # 多輪模擬：agent 追問後自動回覆的內容（空=單輪測試）


TEST_CASES: list[TestCase] = [
    # ── 1. 硬體維修技師 (H-1 ~ H-10) ──
    TestCase("H-1", "硬體維修", "預售屋想換電子鎖要提供什麼資訊供技師評估？",
             "告知需提供現有鎖體正面及鎖匣照片，以便評估側板規格。",
             ["照片", "側板", "評估"]),
    TestCase("H-2", "硬體維修", "什麼是電子鎖的側板和受口？",
             "解釋鎖匣外鐵片與門框孔位的定義，這會影響型號選擇。",
             ["鎖匣", "鐵片", "門框", "受口"]),
    TestCase("H-3", "硬體維修", "推拉式和把手式電子鎖的開門動作差異？",
             "解釋推拉式為直接進門，把手式則需下壓把手的機械區別。",
             ["推拉", "把手", "下壓"]),
    TestCase("H-4", "硬體維修", "全自動鎖匣的鎖舌感應機制是什麼？",
             "解釋其具備感應器，當門關閉後會自動驅動鎖栓伸出上鎖。",
             ["感應器", "自動", "鎖栓"]),
    TestCase("H-5", "硬體維修", "鎖舌在室內拉不開門的緊急處理？",
             "指導「先將門推緊，再拉動把手」的緩解動作。",
             ["推緊", "拉", "把手"],
             device_brand="Chatlock",
             auto_reply="鎖舌縮不回去，門是關著的"),
    TestCase("H-6", "硬體維修", "鎖在室外推不開門的緊急處理？",
             "指導「先拉緊把手使門閉合，完成解鎖後再用力推動」。",
             ["拉緊", "把手", "推"],
             device_brand="Dormakaba"),
    TestCase("H-7", "硬體維修", "門扇反弓會對鎖舌造成什麼具體影響？",
             "指出鉸鏈區域擠壓問題會導致鎖舌與受口片卡澀難開，也可能會無法開啟。需將門先拉緊或推緊後解鎖，再放開手才能開門。",
             ["鉸鏈", "反弓", "受口片", "卡"]),
    TestCase("H-8", "硬體維修", "出現關鎖失敗警報時，使用者可以如何自行初步排查？",
             "指導在開門狀態下測試鎖栓伸縮是否正常，之後再確認是否為受口位移造成。",
             ["受口", "鎖栓", "排查"],
             device_brand="Dormakaba"),
    TestCase("H-9", "硬體維修", "Dormakaba 雙重認證模式啟動後會有什麼現象？",
             "Dormakaba 品牌已知但型號未知時：應簡述雙重認證的通用現象（單一驗證無法開門、需兩種方式組合），並請客戶補充型號取得對應型號的解除步驟。",
             ["雙重", "兩種", "型號"],
             device_brand="Dormakaba"),
    TestCase("H-10", "硬體維修", "Chatlock貓眼鏡頭旁閃爍紅燈的含義？",
             "說明鏡頭正在主動啟動人臉或掌靜脈辨識，屬於正常工作狀態。",
             ["紅燈", "辨識", "正常"],
             device_brand="Chatlock", device_model="AI-99"),

    # ── 2. 報價與客服專員 (S-1 ~ S-10) ──
    TestCase("S-1", "報價客服", "預約師傅到府安裝電子鎖的具體流程？",
             "說明預約安裝大致流程（諮詢、評估、安裝），並引導客戶提供聯絡方式或撥打店家電話／LINE 線上客服進行預約。",
             ["諮詢", "評估", "安裝"]),
    TestCase("S-2", "報價客服", "我想知道安裝報價，可以直接告訴我嗎？",
             "報價、費用一律轉接真人專員處理，不在 AI 客服範圍內。",
             ["報價", "真人", "轉接"]),
    TestCase("S-3", "報價客服", "師傅完成安裝後會提供哪些教學服務？",
             "告知師傅完成安裝後會現場提供使用教學（如管理員/用戶設定、操作示範等）。",
             ["教學", "現場"]),
    TestCase("S-4", "報價客服", "自備鎖請你們代工，如果之後壞了有保固嗎？",
             "說明代工服務僅針對安裝品質，產品本身故障需洽原購買商。",
             ["代工", "安裝", "保固"]),
    TestCase("S-5", "報價客服", "林口以外的地區有提供電子鎖安裝服務嗎？",
             "告知實體門市位置並強調安裝服務可提供跨區支援。",
             ["林口", "跨區", "安裝"]),
    TestCase("S-6", "報價客服", "遺失實體鑰匙導致無法進門，這在保固範圍內嗎？",
             "明確告知鑰匙遺失屬於人為因素，不包含在免費保固中；建議聯繫客服安排技師到場協助處理。",
             ["保固", "鑰匙", "人為"]),
    TestCase("S-7", "報價客服", "如果我想更換整組鎖體，建議先準備什麼資料？",
             "引導使用者提供現有門鎖的照片與門厚資訊以利作業，以及需提供欲安裝的品牌及型號。",
             ["照片", "門厚", "品牌", "型號"]),
    TestCase("S-8", "報價客服", "你們有提供鑰匙複製服務嗎？",
             "回答有提供，包含一般鑰匙、車輛遙控器與社區門禁磁扣／卡片複製。",
             ["鑰匙複製", "服務"]),
    TestCase("S-9", "報價客服", "請問汽機車開鎖你們也有提供嗎？",
             "說明鎖市除了電子鎖外也有提供汽機車開鎖服務。",
             ["汽機車", "開鎖"]),
    TestCase("S-10", "報價客服", "有網路連線功能的電子鎖，對生活有哪些具體好處？",
              "提及可異地遠端開門、即時收到家人到家通知及紀錄查詢。",
              ["遠端", "通知", "紀錄"]),

    # ── 3. 門市與規格助理 (W-1 ~ W-10) ──
    TestCase("W-1", "門市規格", "鎖市的店內聯絡電話是多少？",
             "提供店內電話 02-8601-9952。",
             ["02", "8601", "9952"]),
    TestCase("W-2", "門市規格", "林口鎖市地址為何？",
             "新北市林口區民富街83號1樓。",
             ["林口", "民富", "83"]),
    TestCase("W-3", "門市規格", "門市除了電子鎖還有提供印章服務嗎？",
             "回答有提供，包含印章刻印代工與名片製作。",
             ["印章", "刻印"]),
    TestCase("W-4", "門市規格", "電子鎖完全沒電時，有哪些緊急供電方案？",
             "Chatlock AI-99：底部圓形蓋向下壓向右轉開，使用 Type-C 線接行動電源喚醒；旁邊另有鑰匙孔可用備用鑰匙開門。",
             ["Type-C", "行動電源", "鑰匙"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("W-5", "門市規格", "為什麼電子鎖不建議混用不同品牌的電池？",
             "解釋不同電壓可能導致漏液風險，強力推薦國際牌鹼性電池。",
             ["漏液", "電池", "鹼性"]),
    TestCase("W-6", "門市規格", "老人家指紋較淺，在設定上有什麼建議？",
             "建議同一根手指用不同角度（指尖／指腹／側邊）多登錄幾次，或登錄紋路較清楚的不同手指。",
             ["角度", "登錄", "手指"]),
    TestCase("W-7", "門市規格", "鎖市有賣 Milre 美樂 6500F 嗎？",
             "本店各品牌電子鎖皆可協助安裝/販售；Milre 6500F 詳細規格與報價請聯繫真人專員確認。",
             ["Milre", "提供"]),
    TestCase("W-8", "門市規格", "哪裡可以下載 GL220 電子鎖的說明書？",
             "提供 GL220 的 Google Drive 分享連結。",
             ["GL220", "Drive"]),
    TestCase("W-9", "門市規格", "我想找 FA9000 電子鎖的操作手冊。",
             "提供 FA9000 的 Google Drive 連結。",
             ["FA9000", "Drive"],
             device_brand="Dormakaba", device_model="FA9000"),
    TestCase("W-10", "門市規格", "ML660 的故障排除手冊連結？",
              "提供 ML660 的 Google Drive 連結。",
              ["ML660", "Drive"],
              device_brand="Dormakaba", device_model="ML660"),

    # ── 4. APP 設定專家 (Y-1 ~ Y-10) ──
    TestCase("Y-1", "APP設定", "AS701 智慧鎖如何進入密碼登記模式？",
             "按背面【註冊】鍵 → 輸入管理者密碼 → 按【#】鍵 → 按【1】進入新增使用者密碼 → 輸入新密碼後按【#】完成。",
             ["註冊", "管理者密碼", "#"]),
    TestCase("Y-2", "APP設定", "如何在 AS701 上新增 RFID 感應卡？",
             "按下登記鍵後，將卡片貼近感應區並按 * 鍵完成。",
             ["登記", "卡片", "*"]),
    TestCase("Y-3", "APP設定", "A90 電子鎖完全沒電，如何用行動電源喚醒？",
             "按壓底部圓蓋右轉取出，使用 Type-C 線連接供電。",
             ["底部", "Type-C", "行動電源"]),
    TestCase("Y-4", "APP設定", "Dormakaba APP 怎麼設定遠端金鑰？",
             "Dormakaba 品牌已知但型號未知時：應請客戶補充型號（如 AS701/RL360 等），告知補上後可提供對應型號的 APP 遠端金鑰操作手冊（GDrive 連結）。",
             ["型號", "手冊"]),
    TestCase("Y-5", "APP設定", "AS701 如何刪除單張感應卡片？",
             "長按背面註冊鍵約 5 秒（面板閃爍） → 輸入管理者密碼 → 按【2】 → 感應欲刪除的卡片或輸入順序數字 → 按【*】退出。",
             ["註冊", "管理者密碼", "*"]),
    TestCase("Y-6", "APP設定", "ML550 電子鎖的基本操作說明在哪看？",
             "提供 ML550 專屬的 GDrive 使用說明書連結。",
             ["ML550", "說明"]),
    TestCase("Y-7", "APP設定", "Chatlock AI-99 臨時密碼的首位數字有什麼規定？",
             "明確指出臨時密碼的第一個數字必須設定為「1」。",
             ["臨時密碼", "1"]),
    TestCase("Y-8", "APP設定", "AI-99 如何查看過去的開鎖紀錄？",
             "在 AI-99 內側觸控螢幕的【選單】中點選【記錄查詢】查看開鎖紀錄。",
             ["選單", "記錄"]),
    TestCase("Y-9", "APP設定", "為什麼播放 AI-99 的語音留言需要驗證管理員？",
             "說明是基於隱私安全規範，確保只有授權者可聽取。",
             ["管理員", "隱私", "授權"]),
    TestCase("Y-10", "APP設定", "如何在 A90 上完成掌靜脈的錄入？",
              "提示手掌應保持在鏡頭正前方 15 至 30 公分處進行掃描。",
              ["掌靜脈", "15", "30", "公分"]),

    # ── 5. 多意圖協作 (M-1 ~ M-5) ──
    TestCase("M-1", "多意圖", "我想預約師傅安裝，順便告訴我你們林口門市在哪？",
             "同時回應預約流程與林口門市正確地址。",
             ["預約", "安裝", "林口", "地址"]),
    TestCase("M-2", "多意圖", "我的鎖舌卡住了怎麼修？預約維修要準備什麼？",
             "給予物理檢查建議，並告知預約維修需提供的型號與症狀資訊。",
             ["鎖舌", "型號", "症狀"]),
    TestCase("M-3", "多意圖", "AS701 怎麼改密碼？另外你們週日有營業嗎？",
             "同時教學 AS701 改密碼步驟，並確認週日營業時間。",
             ["AS701", "密碼", "週日"]),
    TestCase("M-4", "多意圖", "FA9000 的說明書在哪？這台可以用手機開門嗎？",
             "提供手冊連結並解釋該型號的連網開鎖功能。",
             ["FA9000", "手冊", "手機"],
             device_brand="Dormakaba", device_model="FA9000"),
    TestCase("M-5", "多意圖", "為什麼指紋一直失敗？老人家要怎麼設定比較好？",
             "解釋指紋辨識失敗原因，並提供長輩重複錄入的專業建議。",
             ["指紋", "失敗", "重複"]),

    # ── 6. 圍籬與領域外 (G-1 ~ G-5) ──
    TestCase("G-1", "圍籬測試", "幫我推薦林口好吃的火鍋店。",
             "禮貌告知職責為電子鎖服務，無法提供美食建議。",
             ["電子鎖", "無法"]),
    TestCase("G-2", "圍籬測試", "今天林口天氣怎麼樣？會下雨嗎？",
             "告知無法提供即時天氣預報，詢問是否有門鎖問題需協助。",
             ["無法", "門鎖"]),
    TestCase("G-3", "圍籬測試", "最近台積電的股價值得買入嗎？",
             "告知非財經專家，僅能協助處理電子鎖相關專業諮詢。",
             ["電子鎖", "無法"]),
    TestCase("G-4", "圍籬測試", "你會寫 Python 程式碼嗎？",
             "告知職責範圍為電子鎖諮詢，無法提供程式開發服務。",
             ["電子鎖", "無法"]),
    TestCase("G-5", "圍籬測試", "牛肉麵要怎麼煮才好吃？",
             "告知無法提供食譜，引導使用者回歸電子鎖相關話題。",
             ["電子鎖", "無法"]),

    # ── 7. 追加實戰案例 (E-1 ~ E-11) ──
    TestCase("E-1", "硬體維修", "換完電池還是會一直無法上鎖",
             "應確認電池品牌是否正確，建議使用 Panasonic 鹼性電池",
             ["Panasonic", "鹼性", "電池"],
             device_brand="Chatlock",
             auto_reply="用的是金鼎電池，關門後是自動上鎖的"),
    TestCase("E-2", "硬體維修", "螢幕一直閃爍，無法感應任何開鎖方式",
             "Chatlock AI99/A90：先確認電池為 Panasonic 鹼性電池並更換全新一組；若仍無反應，使用 5V1A/5V2A 行動電源從底部 Type-C 孔位緊急供電",
             ["電池", "行動電源", "Type-C"],
             device_brand="Chatlock"),
    TestCase("E-3", "硬體維修", "Chatlock電子鎖網路一直斷線",
             "Chatlock AI-99/A90/AI-88 系列 Wi-Fi 模組整合在內側螢幕內，多數情況是內側螢幕未插好導致 Wi-Fi 模組斷線；建議重新確認內側螢幕插入到底並完整蓋上，並嘗試 APP【清理緩存】或【解除綁定】後重新配對。",
             ["螢幕", "Wi-Fi", "緩存"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("E-4", "硬體維修", "電子鎖配對網路時要注意什麼？",
             "電子鎖只能連 2.4GHz 頻段；家用路由器 2.4G 與 5G 必須分開設定（合併會 IoT 異常耗電與連線不穩）；不建議 Wi-Fi 6/7/8 路由器（協定相容性差）。",
             ["2.4G", "5G", "分開"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("E-5", "硬體維修", "Chatlock 鎖栓伸不出來、卡頓不順怎麼辦？",
             "鎖栓動作開著門就異常（伸不出、縮不回、卡頓）屬機械問題，建議派工請師傅檢查。",
             ["鎖栓", "派工"],
             device_brand="Chatlock", device_model="AI-99",
             auto_reply="開著門按開鎖也不會動"),
    TestCase("E-6", "硬體維修", "為什麼只有動畫在跑動但是沒有感應人臉辨識？",
             "確認鏡頭兩旁是否有紅燈亮起，沒有紅燈代表經過的人較多導致感應太多次失敗，先使用其他方式開門",
             ["紅燈", "感應", "其他方式"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("E-7", "硬體維修", "請問我的門可以安裝嗎？",
             "請客戶提供門的正面、背面、側面、門框位置的照片以進行評估",
             ["照片", "正面", "評估"]),
    TestCase("E-8", "硬體維修", "我想預約你們的安裝服務，要怎麼開始？",
             "說明安裝預約需確認服務區域（林口、新莊為主）、門鎖類型，並引導留聯絡方式或撥打店家電話／LINE 線上客服。",
             ["林口", "電話", "LINE"]),
    TestCase("E-9", "硬體維修", "為什麼我的APP網路延遲這麼嚴重？",
             "Chatlock AI-99 常見原因為內側觸控螢幕沒插好導致 Wi-Fi 模組斷線；可重新確認螢幕安裝、清理 APP 緩存，或檢查家用 2.4G Wi-Fi 是否分開設定。",
             ["螢幕", "Wi-Fi", "緩存"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("E-10", "硬體維修", "鋰電池怎麼充電？",
             "使用 5V1A 或 5V2A 充電頭、Type-C 線材；嚴禁使用快充（10W/15W/20W 以上），會造成電池膨脹或損壞。",
             ["5V1A", "5V2A", "快充"]),
    TestCase("E-11", "硬體維修", "Chatlock售後是怎麼保固？",
             "Chatlock 產品自安裝完成日起享有原廠保固，保固期依產品型號或購買通路為準",
             ["保固", "安裝", "原廠"],
             device_brand="Chatlock"),

    # ── 品牌路由測試：驗證已知品牌用戶是否載入正確的品牌版技能 ──
    TestCase("B-1", "品牌路由", "門打不開",
             "Dormakaba 品牌已知但型號未知時：應給通用推緊/拉緊門法（依推/拉開門方向），並提示客戶補充型號以取得 Dormakaba 型號專屬步驟。",
             ["推緊", "型號"],
             device_brand="Dormakaba",
             auto_reply="我在門外，門是關著的，按開鎖有聽到馬達聲"),
    TestCase("B-2", "品牌路由", "門打不開",
             "回答應包含推緊門板法或 Type-C 緊急供電等 Chatlock 門扇卡死的處理方式",
             ["推緊", "Type-C"],
             device_brand="Chatlock",
             auto_reply="我在門外，門是關著的，按開鎖有聽到馬達聲"),
    TestCase("B-3", "品牌路由", "電池很快沒電",
             "Dormakaba 品牌已知但型號未知時：先給通用耗電排查（推薦 Panasonic 鹼性電池、確認 Wi-Fi 2.4G/5G 分開設定），並請客戶補充型號取得對應型號專屬資訊。",
             ["Panasonic", "鹼性", "型號"],
             device_brand="Dormakaba"),
    TestCase("B-4", "品牌路由", "我設定後變成要先按指紋再輸密碼才能開門，怎麼解除？",
             "Chatlock AI-99：在【選單】→【系統設定】→【高級設定】→【雙重認證模式】關閉開關",
             ["系統設定", "高級設定", "雙重認證"],
             device_brand="Chatlock", device_model="AI-99"),
    TestCase("B-5", "品牌路由", "鎖一直嗶嗶叫",
             "Dormakaba 品牌已知但型號未知時：先給通用警報排查（電池品牌、門是否關緊、是否近期換過電池/設定），並請客戶補充型號以取得 Dormakaba 對應型號的警報信號表。",
             ["警報", "型號"],
             device_brand="Dormakaba"),
    TestCase("B-6", "品牌路由", "APP 怎麼配對",
             "Chatlock AI-99：在【選單】→【網路設定】→【網路配對】→【開始配對】，門鎖顯示「連網中」後等待配對成功",
             ["網路設定", "配對"],
             device_brand="Chatlock", device_model="AI-99"),
]

# ─────────────────────────────────────────────
# LLM-as-Judge 評分
# ─────────────────────────────────────────────

JUDGE_PROMPT = """\
你是品質評審員。請判斷 AI 客服的回答是否符合預期。

## 測試題目（用戶第一輪訊息）
{question}

## 用戶後續補充（多輪測試的第二輪訊息，若無則略過）
{auto_reply}

## 用戶資料 profile（測試環境注入的品牌/型號）
{profile}

## 預期回答方向
{expected}

## AI 實際回答（這是 AI 在收到第一輪訊息（+若有第二輪補充與 profile 上下文）後，最終給用戶的回覆）
{answer}

## 評分標準
- **pass**: 回答的核心意思符合預期方向（不需要完全一致，意思到即可）
- **partial**: 回答部分符合但有明顯遺漏或偏差
- **fail**: 回答完全不相關、錯誤、或未回答問題

## 評分注意事項
- AI 若在回覆中**引用「用戶後續補充」段提到的內容**（例如品牌、型號、症狀細節），這是合理的對話上下文使用，**不應視為臆測或幻覺**
- AI 若在回覆中**引用「用戶資料 profile」**（如客戶品牌已知）做更精準回答，這也是正確的多輪流程

請只回覆一個 JSON（不要 markdown code block）：
{{"verdict": "pass/partial/fail", "reason": "一句話說明"}}
"""


async def judge_answer(judge_model, tc: TestCase, answer: str) -> dict:
    """用 LLM 評判回答品質。"""
    profile_parts = []
    if tc.device_brand:
        profile_parts.append(f"device_brand={tc.device_brand}")
    if tc.device_model:
        profile_parts.append(f"device_model={tc.device_model}")
    profile_str = ", ".join(profile_parts) if profile_parts else "(profile 未設定)"

    prompt = JUDGE_PROMPT.format(
        question=tc.question,
        auto_reply=tc.auto_reply or "(無第二輪補充)",
        profile=profile_str,
        expected=tc.expected,
        answer=answer,
    )
    # llm_metrics.log_simple 會在 storage 未注入時自動 noop（離線跑 quality_check 時不寫 DB）
    try:
        from harness.llm_metrics import log_simple as _log_simple
    except Exception:
        _log_simple = None
    model_name = getattr(judge_model, "model", "unknown") or "unknown"
    t0 = time.monotonic()
    try:
        resp = await judge_model.ainvoke(prompt)
        if _log_simple:
            _log_simple(
                user_id=f"quality:{tc.id}",
                call_site="quality_judge",
                model=str(model_name),
                response=resp,
                latency_ms=int((time.monotonic() - t0) * 1000),
                user_question=prompt,
                metadata={"category": tc.category},
            )
        content = resp.content
        if isinstance(content, list):
            content = "".join(
                b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        # 嘗試解析 JSON
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except Exception as e:
        if _log_simple:
            _log_simple(
                user_id=f"quality:{tc.id}",
                call_site="quality_judge",
                model=str(model_name),
                latency_ms=int((time.monotonic() - t0) * 1000),
                success=False,
                error_type=type(e).__name__,
                user_question=prompt,
            )
        return {"verdict": "error", "reason": f"Judge 解析失敗: {e}"}


def keyword_score(tc: TestCase, answer: str) -> tuple[int, int]:
    """計算關鍵詞命中數。"""
    hits = sum(1 for kw in tc.keywords if kw.lower() in answer.lower())
    return hits, len(tc.keywords)


# ─────────────────────────────────────────────
# 回答提取（同 main.py）
# ─────────────────────────────────────────────

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(content)
    return str(content)


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

async def run_single(agent, judge_model, tc: TestCase, config: dict, *, use_judge: bool = True) -> dict:
    """執行單一測試並評分。"""
    t0 = time.time()

    # 組裝訊息：注入 [可用產品資料] 模擬 debounce.run_agent() 的新架構行為
    from agent_tools.tools import (
        set_current_user_id,
        set_current_brand,
        set_current_user_input,
    )
    from product_info import has_brand as has_product_brand, filter_loadable as filter_product_loadable
    from harness.line_ui_factory import infer_brand_from_text
    brand = tc.device_brand or None
    model = tc.device_model or None
    # 品牌未知時，從問題文字自動推論（同生產路徑 debounce.py:289）
    if not brand:
        inferred_brand, inferred_model = infer_brand_from_text(tc.question)
        if inferred_brand:
            brand = inferred_brand
            if inferred_model and not model:
                model = inferred_model
    # Quick Reply 模擬：仍未取得品牌 → 套用預設（mimic production Quick Reply 強制收集後的狀態）
    quick_reply_used = False
    if not brand:
        brand = QUICK_REPLY_DEFAULT_BRAND
        quick_reply_used = True
    # 同步生產路徑：ContextVar 注入 user_id / brand / model / user_input
    # load_product_info 會用 ContextVar 做 profile gating
    set_current_user_id(f"qc-{tc.id}")
    set_current_brand(brand, model)
    set_current_user_input(tc.question)

    # 構建 [可用產品資料] 前綴 — 對齊 debounce.py 4 條路徑
    if brand and has_product_brand(brand) and model:
        # A) brand+model 齊備
        docs = filter_product_loadable(brand, model)
        info_header = f"[可用產品資料]\n（用戶為 {brand} {model}，使用 load_product_info 載入）\n"
    elif brand and has_product_brand(brand):
        # B) brand 已知、model 未知
        docs = filter_product_loadable(None, None)
        info_header = (
            f"[可用產品資料]\n"
            f"⚠️ {brand} 型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
            f"「以下為通用建議，您的型號實際操作可能略有差異，建議補充型號取得精準步驟。」\n"
        )
    elif brand:
        # C) brand 已知但 product_info 無此品牌（如 Waferlock）
        docs = filter_product_loadable(None, None)
        info_header = (
            f"[可用產品資料]\n"
            f"⚠️ 目前無 {brand} 詳細產品資料，僅能提供通用建議。回覆時請聲明：\n"
            f"「我這邊沒有 {brand} 的詳細資料，建議您查看說明書，或我幫您安排專員協助。」\n"
        )
    else:
        # D) 全未知
        docs = filter_product_loadable(None, None)
        info_header = (
            "[可用產品資料]\n"
            "⚠️ 品牌或型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
            "「以下為通用建議，您的型號實際操作可能略有差異。」\n"
            "**請呼叫 update_user_info 確認用戶品牌。**\n"
        )
    doc_lines = "\n".join(f"- {d.name}: {d.description}" for d in docs)
    skills_prefix = f"{info_header}{doc_lines}\n\n"

    # 用 brand/model（含 infer 後值）建構 [用戶資料] 區塊，與生產路徑一致
    profile_lines = []
    if brand:
        profile_lines.append(f"[Verified Fact] device_brand: {brand}")
    if model:
        profile_lines.append(f"[Verified Fact] device_model: {model}")
    if profile_lines:
        content = (
            f"{skills_prefix}"
            f"[用戶資料]\n" + "\n".join(profile_lines) + "\n\n"
            f"[用戶訊息]\n{tc.question}"
        )
    else:
        content = (
            f"{skills_prefix}"
            f"[用戶訊息]\n{tc.question}"
        )

    # 第一輪：呼叫 agent
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": content}]},
        config,
    )

    # 提取回答（與 production 一致剝除 [已參考: ...] 引用標記）
    answer = ""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            answer = _strip_ref_markers(_extract_text(msg.content))
            break

    # 多輪模擬：若有 auto_reply 且 agent 回覆含追問（？）→ 發送第二輪
    if tc.auto_reply and "？" in answer:
        # 對齊 production：第二輪前先跑 checkpoint cleanup（替換 ToolMessage / 中間 AIMessage）
        try:
            from harness.debounce import _cleanup_tool_checkpoint
            # quality_check 的 agent 沒注入到 debounce 模組，臨時 patch _agent 全域
            import harness.debounce as _dbnc
            _orig_agent = getattr(_dbnc, "_agent", None)
            _dbnc._agent = agent
            try:
                await _cleanup_tool_checkpoint(config, messages)
            finally:
                _dbnc._agent = _orig_agent
        except Exception as e:
            print(f"\n       [cleanup warn] {e}", end="")

        if profile_lines:
            reply_content = (
                f"{skills_prefix}"
                f"[用戶資料]\n" + "\n".join(profile_lines) + "\n\n"
                f"[用戶訊息]\n{tc.auto_reply}"
            )
        else:
            reply_content = (
                f"{skills_prefix}"
                f"[用戶訊息]\n{tc.auto_reply}"
            )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": reply_content}]},
            config,  # 同一 thread_id，MemorySaver 保留上下文
        )
        # 重新提取最終回答（同樣剝除引用標記）
        answer = ""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                answer = _strip_ref_markers(_extract_text(msg.content))
                break

    elapsed = round(time.time() - t0, 1)

    # 收集 skill / product_info 呼叫紀錄（從 tool messages，包含兩輪）
    skills_loaded = []
    for msg in messages:
        if hasattr(msg, "type") and msg.type == "tool" and hasattr(msg, "content"):
            text = _extract_text(msg.content)
            for marker in ("已載入產品資料:", "已載入技能:"):
                if text.startswith(marker):
                    name = text.split(marker)[1].split("\n")[0].strip()
                    if name not in skills_loaded:
                        skills_loaded.append(name)
                    break

    # 關鍵詞命中
    kw_hits, kw_total = keyword_score(tc, answer)

    # LLM Judge（可選）
    if use_judge and judge_model:
        judge_result = await judge_answer(judge_model, tc, answer)
    else:
        # 只用關鍵詞命中率判定
        ratio = kw_hits / kw_total if kw_total else 0
        if ratio >= 0.5:
            judge_result = {"verdict": "pass", "reason": f"keyword {kw_hits}/{kw_total}"}
        elif ratio > 0:
            judge_result = {"verdict": "partial", "reason": f"keyword {kw_hits}/{kw_total}"}
        else:
            judge_result = {"verdict": "fail", "reason": f"keyword 0/{kw_total}"}

    return {
        "id": tc.id,
        "category": tc.category,
        "question": tc.question,
        "expected": tc.expected,
        "answer": answer[:500],
        "skills_loaded": skills_loaded,
        "keyword_hits": f"{kw_hits}/{kw_total}",
        "verdict": judge_result.get("verdict", "error"),
        "reason": judge_result.get("reason", ""),
        "elapsed_sec": elapsed,
        "brand_resolved": brand or "",
        "model_resolved": model or "",
        "quick_reply_used": quick_reply_used,
    }


def _parse_args():
    p = argparse.ArgumentParser(description="Agent Skills Quality Check")
    p.add_argument("--no-judge", action="store_true", help="跳過 LLM-as-Judge，只用關鍵詞評分")
    p.add_argument("--judge-only", action="store_true", help="不呼叫 agent，用現有 JSON 重新跑 LLM 評分")
    p.add_argument("--retry-failed", action="store_true", help="只重測上次非 pass 的案例，更新報告")
    return p.parse_args()


async def _rejudge(judge_model, json_path: str) -> dict:
    """讀取現有 JSON，對每筆結果重新跑 LLM Judge。"""
    with open(json_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    results = report.get("results", [])
    stats = {"pass": 0, "partial": 0, "fail": 0, "error": 0}
    category_stats: dict[str, dict] = {}

    print(f"  Re-judging {len(results)} results...\n")

    for i, r in enumerate(results):
        tc = TestCase(
            id=r["id"], category=r["category"], question=r["question"],
            expected=r["expected"], keywords=[],
        )
        # 找回原始 keywords
        for orig in TEST_CASES:
            if orig.id == r["id"]:
                tc.keywords = orig.keywords
                break

        print(f"  [{i+1:02d}/{len(results)}] {r['id']}...", end=" ", flush=True)
        judge_result = await judge_answer(judge_model, tc, r.get("answer", ""))
        r["verdict"] = judge_result.get("verdict", "error")
        r["reason"] = judge_result.get("reason", "")
        print(f"[{r['verdict']}] {r['reason']}")

        stats[r["verdict"]] = stats.get(r["verdict"], 0) + 1
        cat = r["category"]
        if cat not in category_stats:
            category_stats[cat] = {"pass": 0, "partial": 0, "fail": 0, "error": 0, "total": 0}
        category_stats[cat][r["verdict"]] = category_stats[cat].get(r["verdict"], 0) + 1
        category_stats[cat]["total"] += 1

    return {"summary": stats, "category_stats": category_stats, "results": results}


async def main():
    args = _parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "quality_report.json")
    html_path = os.path.join(base_dir, "quality_report.html")
    md_dir = os.path.join(base_dir, "reports")

    _ensure_vertex_credentials()

    # ── --judge-only 模式：只重新評分 ──
    if args.judge_only:
        if not os.path.isfile(json_path):
            print(f"  ERROR: {json_path} not found. Run without --judge-only first.")
            return

        judge_model = ChatLiteLLM(model="vertex_ai/gemini-2.5-flash", temperature=0.0)

        print("=" * 60)
        print("  Quality Check — Re-Judge Only")
        print("=" * 60)

        report = await _rejudge(judge_model, json_path)
        _save_report(report, json_path, html_path, md_dir)
        return

    # ── --retry-failed 模式：只重測非 pass 的案例 ──
    if args.retry_failed:
        if not os.path.isfile(json_path):
            print(f"  ERROR: {json_path} not found. Run full test first.")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            prev_report = json.load(f)
        prev_results = {r["id"]: r for r in prev_report.get("results", [])}

        # 找出需要重測的案例
        retry_ids = {rid for rid, r in prev_results.items() if r["verdict"] != "pass"}
        retry_cases = [tc for tc in TEST_CASES if tc.id in retry_ids]

        if not retry_cases:
            print("  All cases passed! Nothing to retry.")
            return

        use_judge = not args.no_judge

        os.chdir(_AGENT_DIR)
        cfg = load_config()

        # 初始化 Quick Reply / 品牌字典（與正常模式同步）
        # 沒做 → infer_brand_from_text 永遠返回 (None, None)，未寫死 device_brand 的 case 會被 brand gate 拒絕
        from harness.line_ui_factory import init_quick_reply
        init_quick_reply(cfg.quick_reply)

        model = ChatLiteLLM(model="vertex_ai/gemini-2.5-pro", temperature=0.3)

        judge_model = None
        if use_judge:
            judge_model = ChatLiteLLM(model="vertex_ai/gemini-2.5-flash", temperature=0.0)

        agent = build_agent(model, cfg, checkpointer=MemorySaver())

        print("=" * 60)
        print(f"  Quality Check — Retry Failed ({len(retry_cases)} cases)")
        print("=" * 60)

        for i, tc in enumerate(retry_cases):
            config = {"configurable": {"thread_id": f"qc-retry-{tc.id}"}}
            prev_verdict = prev_results[tc.id]["verdict"]

            print(f"\n[{i+1:02d}/{len(retry_cases)}] {tc.id} (was {prev_verdict}) | {tc.question[:40]}...", end=" ", flush=True)

            try:
                r = await run_single(agent, judge_model, tc, config, use_judge=use_judge)
            except Exception as e:
                r = {
                    "id": tc.id, "category": tc.category, "question": tc.question,
                    "expected": tc.expected, "answer": f"ERROR: {e}",
                    "skills_loaded": [], "keyword_hits": "0/0",
                    "verdict": "error", "reason": str(e), "elapsed_sec": 0,
                }

            icon = {"pass": "O", "partial": "~", "fail": "X", "error": "!"}.get(r["verdict"], "?")
            changed = " ✦" if r["verdict"] != prev_verdict else ""
            skills_str = ",".join(r["skills_loaded"]) if r["skills_loaded"] else "-"
            print(f"[{icon}] {r['elapsed_sec']}s | kw={r['keyword_hits']} | skills={skills_str}{changed}")
            if r["verdict"] != "pass":
                print(f"       reason: {r['reason']}")

            # 更新結果
            prev_results[tc.id] = r

        # 按原始順序重組結果
        all_ids = [tc.id for tc in TEST_CASES]
        merged = [prev_results[tid] for tid in all_ids if tid in prev_results]

        # 重新計算統計
        stats = {"pass": 0, "partial": 0, "fail": 0, "error": 0}
        category_stats: dict[str, dict] = {}
        for r in merged:
            v = r["verdict"]
            stats[v] = stats.get(v, 0) + 1
            cat = r["category"]
            if cat not in category_stats:
                category_stats[cat] = {"pass": 0, "partial": 0, "fail": 0, "error": 0, "total": 0}
            category_stats[cat][v] = category_stats[cat].get(v, 0) + 1
            category_stats[cat]["total"] += 1

        report = {"summary": stats, "category_stats": category_stats, "results": merged}
        _save_report(report, json_path, html_path, md_dir)
        return

    # ── 正常模式 / --no-judge 模式 ──
    use_judge = not args.no_judge
    mode_label = "Full (Agent + LLM Judge)" if use_judge else "Fast (Agent + Keywords only)"

    # 切到 agent/ 目錄，讓 config.toml 等相對路徑正確
    os.chdir(_AGENT_DIR)

    cfg = load_config()

    # 初始化 Quick Reply / 品牌字典（生產 app.py:126 會做）
    # 沒做 → infer_brand_from_text 永遠返回 (None, None)，品牌路由失準
    from harness.line_ui_factory import init_quick_reply
    init_quick_reply(cfg.quick_reply)

    # 主模型走 config.toml 的 [llm] 設定（含 thinking_budget 等）
    # 如此 quality_check 才能驗證實際生產環境的模型表現
    model = get_llm(cfg.llm)
    print(f"[Quality Check] Using model: {cfg.llm.get('model')} (thinking={cfg.llm.get('thinking_budget', 'N/A')})")

    judge_model = None
    if use_judge:
        # judge 用 Gemini 2.5 Flash GA（與被測模型解耦；GA 配額充裕，避免 preview 限速）
        judge_model = ChatLiteLLM(model="vertex_ai/gemini-2.5-flash", temperature=0.0)

    agent = build_agent(model, cfg, checkpointer=MemorySaver())

    print("=" * 60)
    print(f"  Quality Check — {mode_label} ({len(TEST_CASES)} cases)")
    print("=" * 60)

    results = []
    stats = {"pass": 0, "partial": 0, "fail": 0, "error": 0}
    category_stats: dict[str, dict] = {}

    for i, tc in enumerate(TEST_CASES):
        config = {"configurable": {"thread_id": f"qc-{tc.id}"}}

        print(f"\n[{i+1:02d}/{len(TEST_CASES)}] {tc.id} | {tc.category} | {tc.question[:40]}...", end=" ", flush=True)

        # 429 retry with exponential backoff (Vertex AI Flash 突發 RPM 保護)
        r = None
        for attempt in range(4):
            try:
                r = await run_single(agent, judge_model, tc, config, use_judge=use_judge)
                break
            except Exception as e:
                msg = str(e)
                is_429 = "RESOURCE_EXHAUSTED" in msg or "429" in msg or "RateLimitError" in msg
                if is_429 and attempt < 3:
                    backoff = 15 * (2 ** attempt)  # 15s, 30s, 60s
                    print(f"\n       [429] retry in {backoff}s (attempt {attempt+1}/3)...", flush=True)
                    await asyncio.sleep(backoff)
                    continue
                r = {
                    "id": tc.id, "category": tc.category, "question": tc.question,
                    "expected": tc.expected, "answer": f"ERROR: {e}",
                    "skills_loaded": [], "keyword_hits": "0/0",
                    "verdict": "error", "reason": str(e), "elapsed_sec": 0,
                }
                break

        results.append(r)
        verdict = r["verdict"]
        stats[verdict] = stats.get(verdict, 0) + 1

        cat = tc.category
        if cat not in category_stats:
            category_stats[cat] = {"pass": 0, "partial": 0, "fail": 0, "error": 0, "total": 0}
        category_stats[cat][verdict] = category_stats[cat].get(verdict, 0) + 1
        category_stats[cat]["total"] += 1

        icon = {"pass": "O", "partial": "~", "fail": "X", "error": "!"}.get(verdict, "?")
        skills_str = ",".join(r["skills_loaded"]) if r["skills_loaded"] else "-"
        print(f"[{icon}] {r['elapsed_sec']}s | kw={r['keyword_hits']} | skills={skills_str}")
        if verdict != "pass":
            print(f"       reason: {r['reason']}")

        # Throttle: 避免 Vertex AI Flash 突發 RPM 上限
        await asyncio.sleep(1.5)

    report = {"summary": stats, "category_stats": category_stats, "results": results}
    _save_report(report, json_path, html_path, md_dir)


def _save_report(report: dict, json_path: str, html_path: str, md_dir: str | None = None) -> None:
    """輸出 JSON + HTML（+ Markdown）報告並印出摘要。"""
    stats = report["summary"]
    category_stats = report["category_stats"]
    total = sum(stats.values())

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total:   {total}")
    print(f"  Pass:    {stats.get('pass',0)}  ({stats.get('pass',0)/total*100:.0f}%)")
    print(f"  Partial: {stats.get('partial',0)}  ({stats.get('partial',0)/total*100:.0f}%)")
    print(f"  Fail:    {stats.get('fail',0)}  ({stats.get('fail',0)/total*100:.0f}%)")
    print(f"  Error:   {stats.get('error',0)}  ({stats.get('error',0)/total*100:.0f}%)")

    print(f"\n  {'Category':<12} {'Pass':>6} {'Partial':>8} {'Fail':>6} {'Total':>6} {'Rate':>6}")
    print("  " + "-" * 50)
    for cat, cs in category_stats.items():
        rate = cs.get("pass", 0) / cs["total"] * 100 if cs.get("total") else 0
        print(f"  {cat:<12} {cs.get('pass',0):>6} {cs.get('partial',0):>8} {cs.get('fail',0):>6} {cs['total']:>6} {rate:>5.0f}%")

    # 輸出 JSON + HTML
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  JSON saved: {json_path}")

    _generate_html(report, html_path)
    print(f"  HTML saved: {html_path}")

    if md_dir:
        md_path = _generate_md(report, md_dir)
        print(f"  MD saved:   {md_path}")


def _generate_md(report: dict, out_dir: str) -> str:
    """輸出 Markdown 摘要報告（適合貼進 PR / Slack / docs），檔名壓時間戳避免覆蓋。"""
    from datetime import datetime

    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now()
    path = os.path.join(out_dir, f"quality_report_{now.strftime('%Y-%m-%d_%H%M')}.md")

    stats = report.get("summary", {})
    category_stats = report.get("category_stats", {})
    results = report.get("results", [])
    total = sum(stats.values()) or 1
    pass_n = stats.get("pass", 0)
    partial_n = stats.get("partial", 0)
    fail_n = stats.get("fail", 0)
    error_n = stats.get("error", 0)
    pass_rate = pass_n / total * 100

    lines: list[str] = []
    lines.append(f"# Quality Report — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"- **總案例數**: {total}")
    lines.append(f"- **通過率**: {pass_rate:.0f}% ({pass_n}/{total})")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append("| Verdict | Count | Ratio |")
    lines.append("| :--- | ---: | ---: |")
    for label, n in (("Pass", pass_n), ("Partial", partial_n), ("Fail", fail_n), ("Error", error_n)):
        lines.append(f"| {label} | {n} | {n / total * 100:.0f}% |")
    lines.append("")

    if category_stats:
        lines.append("## 分類表現")
        lines.append("")
        lines.append("| Category | Pass | Partial | Fail | Error | Total | Pass Rate |")
        lines.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for cat, cs in category_stats.items():
            t = cs.get("total", 0) or 1
            rate = cs.get("pass", 0) / t * 100
            lines.append(
                f"| {cat} | {cs.get('pass', 0)} | {cs.get('partial', 0)} | "
                f"{cs.get('fail', 0)} | {cs.get('error', 0)} | {cs.get('total', 0)} | {rate:.0f}% |"
            )
        lines.append("")

    non_pass = [r for r in results if r.get("verdict") != "pass"]
    if non_pass:
        lines.append(f"## 未通過案例（{len(non_pass)} 筆）")
        lines.append("")
        icon = {"partial": "WARN", "fail": "FAIL", "error": "ERR"}
        for r in non_pass:
            v = r.get("verdict", "?")
            lines.append(f"### [{icon.get(v, v.upper())}] {r.get('id', '?')} — {r.get('category', '?')}")
            lines.append("")
            lines.append(f"- **Question**: {r.get('question', '')}")
            lines.append(f"- **Expected**: {r.get('expected', '')}")
            lines.append(f"- **Keywords**: {r.get('keyword_hits', '-')}")
            skills = r.get("skills_loaded") or []
            lines.append(f"- **Skills**: {', '.join(skills) if skills else '-'}")
            lines.append(f"- **Elapsed**: {r.get('elapsed_sec', 0)}s")
            reason = (r.get("reason") or "").strip()
            if reason:
                lines.append(f"- **Reason**: {reason}")
            answer = (r.get("answer") or "").strip()
            if answer:
                lines.append("- **Answer**:")
                lines.append("")
                lines.append("  ```")
                for ln in answer.splitlines() or [answer]:
                    lines.append(f"  {ln}")
                lines.append("  ```")
            lines.append("")
    else:
        lines.append("## 未通過案例")
        lines.append("")
        lines.append("全部通過 ✅")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _generate_html(report: dict, path: str) -> None:
    """將報告數據內嵌進 HTML，雙擊即可開啟。"""
    data_json = json.dumps(report, ensure_ascii=False)
    html = f"""\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>Agent Skills — Quality Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,"Microsoft JhengHei",sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}}
  h1{{font-size:1.5rem;margin-bottom:8px}}
  .sub{{color:#94a3b8;margin-bottom:24px;font-size:.85rem}}
  .cards{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:#1e293b;border-radius:10px;padding:16px 24px;min-width:120px;text-align:center}}
  .card .n{{font-size:2rem;font-weight:700}}
  .card .l{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
  .card.pass .n{{color:#4ade80}}.card.partial .n{{color:#fbbf24}}.card.fail .n{{color:#f87171}}.card.error .n{{color:#a78bfa}}.card.total .n{{color:#38bdf8}}
  .sec{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:24px}}
  .sec h2{{font-size:1rem;margin-bottom:14px}}
  .cr{{display:flex;align-items:center;margin-bottom:8px}}
  .cl{{width:90px;font-size:.8rem;color:#cbd5e1;flex-shrink:0}}
  .cb{{flex:1;height:22px;background:#334155;border-radius:4px;overflow:hidden;display:flex}}
  .cb .s{{height:100%}}.s.pass{{background:#4ade80}}.s.partial{{background:#fbbf24}}.s.fail{{background:#f87171}}
  .rt{{width:50px;text-align:right;font-size:.8rem;color:#94a3b8;margin-left:8px}}
  .fb{{display:flex;gap:8px;margin:12px 0;flex-wrap:wrap}}
  .fb button{{background:#334155;border:none;color:#cbd5e1;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:.8rem}}
  .fb button.on{{background:#3b82f6;color:#fff}}
  table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:8px}}
  th{{text-align:left;padding:8px 6px;color:#94a3b8;border-bottom:1px solid #334155;position:sticky;top:0;background:#1e293b}}
  td{{padding:8px 6px;border-bottom:1px solid #1e293b;vertical-align:top}}
  tr:hover td{{background:#273548}}
  .b{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600}}
  .b.pass{{background:#166534;color:#4ade80}}.b.partial{{background:#713f12;color:#fbbf24}}.b.fail{{background:#7f1d1d;color:#f87171}}.b.error{{background:#3b0764;color:#a78bfa}}
  .sk{{display:inline-block;background:#334155;padding:1px 6px;border-radius:3px;font-size:.7rem;margin:1px;color:#38bdf8}}
  .ac{{max-width:320px;line-height:1.4}}.rc{{color:#94a3b8;max-width:200px}}
</style>
</head>
<body>
<h1>Smart Lock AI Agent — Quality Report</h1>
<p class="sub" id="sub"></p>
<div class="cards" id="cards"></div>
<div class="sec"><h2>Category Breakdown</h2><div id="cat"></div></div>
<div class="sec"><h2>Test Results</h2><div class="fb" id="fb"></div><div style="overflow-x:auto"><table><thead><tr>
<th>ID</th><th>Category</th><th>Question</th><th>Verdict</th><th>Keywords</th><th>Skills</th><th>Answer</th><th>Reason</th><th>Time</th>
</tr></thead><tbody id="tb"></tbody></table></div></div>
<script>
const D={data_json};
const R=D.results||[];
const S=D.summary||{{}};
const T=(S.pass||0)+(S.partial||0)+(S.fail||0)+(S.error||0);
document.getElementById('sub').textContent=T+' test cases | Pass rate: '+(T?((S.pass||0)/T*100).toFixed(0):0)+'%';
document.getElementById('cards').innerHTML=[
['total',T,'Total'],['pass',S.pass||0,'Pass'],['partial',S.partial||0,'Partial'],['fail',S.fail||0,'Fail'],['error',S.error||0,'Error']
].map(c=>'<div class="card '+c[0]+'"><div class="n">'+c[1]+'</div><div class="l">'+c[2]+'</div></div>').join('');
const C=D.category_stats||{{}};
document.getElementById('cat').innerHTML=Object.entries(C).map(([n,c])=>{{
const t=c.total||1;return'<div class="cr"><span class="cl">'+n+'</span><div class="cb">'+
'<div class="s pass" style="width:'+(c.pass||0)/t*100+'%"></div>'+
'<div class="s partial" style="width:'+(c.partial||0)/t*100+'%"></div>'+
'<div class="s fail" style="width:'+(c.fail||0)/t*100+'%"></div>'+
'</div><span class="rt">'+((c.pass||0)/t*100).toFixed(0)+'%</span></div>'}}).join('');
const fs=['all',...new Set(R.map(r=>r.verdict))];
document.getElementById('fb').innerHTML=fs.map(f=>'<button class="'+(f==='all'?'on':'')+'" onclick="go(this,\\''+f+'\\')">'+f+'</button>').join('');
function go(el,f){{document.querySelectorAll('.fb button').forEach(b=>b.className=b.textContent===f?'on':'');render(f)}}
function render(f){{
document.getElementById('tb').innerHTML=R.filter(r=>f==='all'||r.verdict===f).map(r=>'<tr>'+
'<td><b>'+e(r.id)+'</b></td><td>'+e(r.category)+'</td><td>'+e(r.question)+'</td>'+
'<td><span class="b '+r.verdict+'">'+r.verdict+'</span></td>'+
'<td>'+e(r.keyword_hits)+'</td>'+
'<td>'+((r.skills_loaded||[]).map(s=>'<span class="sk">'+e(s)+'</span>').join(' ')||'-')+'</td>'+
'<td class="ac">'+e(r.answer||'')+'</td><td class="rc">'+e(r.reason||'')+'</td>'+
'<td>'+r.elapsed_sec+'s</td></tr>').join('')}}
function e(s){{const d=document.createElement('div');d.textContent=s;return d.innerHTML}}
render('all');
</script>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    asyncio.run(main())
