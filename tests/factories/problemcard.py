"""ProblemCard 工廠 — 對齊 SQL/seeds/problem_cards.sql。

Schema：id, conversation_id, brand, model, category, location,
        door_status, network_status, symptoms (jsonb), urgency, intent,
        status, completeness_score
"""

from __future__ import annotations

import uuid

import factory

PROBLEM_CARD_BRANDS = ["Yale", "Chatlock", "美樂", "Dormakaba", "Philips"]
DOOR_STATUSES = ["functional", "partially_functional", "locked_out", "unknown"]
NETWORK_STATUSES = ["online", "offline", "unknown"]
URGENCY_LEVELS = ["low", "normal", "high", "critical"]
INTENTS = ["repair", "consultation", "warranty"]
PC_STATUSES = ["incomplete", "complete", "converted"]
CATEGORIES = ["故障", "密碼", "電池", "網路", "外觀", "安裝"]
TAIWAN_LOCATIONS = [
    "台北市信義區", "台北市大安區", "新北市板橋區",
    "桃園市中壢區", "台中市西屯區", "高雄市三民區",
]


class ProblemCardFactory(factory.DictFactory):
    """輸出 problem_card dict — symptoms 為 list（測試端 json.dumps 入庫）。"""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    conversation_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    brand = factory.Faker("random_element", elements=PROBLEM_CARD_BRANDS)
    model = factory.Faker("bothify", text="??-####", letters="ABCDEFGHJKLMNPQRSTUVWXYZ")
    category = factory.Faker("random_element", elements=CATEGORIES)
    location = factory.Faker("random_element", elements=TAIWAN_LOCATIONS)
    door_status = factory.Faker("random_element", elements=DOOR_STATUSES)
    network_status = factory.Faker("random_element", elements=NETWORK_STATUSES)
    symptoms = factory.LazyFunction(lambda: ["按鍵無反應", "面板閃爍"])
    urgency = factory.Faker("random_element", elements=URGENCY_LEVELS)
    intent = factory.Faker("random_element", elements=INTENTS)
    status = "incomplete"
    completeness_score = factory.Faker("pyfloat", min_value=0.3, max_value=1.0, right_digits=2)
