# 本機完整重佈署 SOP(給非工程操作者)

- **日期**:2026-07-16(20260715 會議 Action #13:寫 SOP 讓 Sunny 自己走一次完整重佈署)
- **目標**:電腦重開機 / 容器全停 / 拉了新 code 之後,把**四個站台全部重新佈署起來**並確認健康
- **前提**:裝好 Docker Desktop 並已開啟(選單列鯨魚圖示是穩定的,不在轉圈)

---

## 〇、心智圖:你要佈署的是什麼

整套系統 = **4 個 stack**(每個 stack 是一組 docker 容器):

| Stack | 內含 | 網址 |
|---|---|---|
| 品牌(dispatch) | 品牌庫 + 品牌 API + Agent + 品牌後台 | http://localhost:3000 |
| 師傅(tech) | 技師庫 + 師傅 API + 師傅站 | http://localhost:3001 |
| 導流(landing) | 導流站(純前端) | http://localhost:3002 |
| 平台(platform) | 平台庫 + 平台 API + 平台維運 + Casdoor | http://localhost:3003 |

> 順序很重要:**品牌 stack 要先起**(師傅 stack 會連品牌 stack 的網路)。

## 一、開終端機、走到專案資料夾

打開「終端機(Terminal)」,貼上:

```bash
cd /Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform
```

(如果要先拿最新 code:`git pull`。不確定就跳過,用現有的。)

## 二、重佈署四個 stack(照順序貼,每段等它跑完)

```bash
# 1. 品牌(必須第一個)
docker compose -f web/brand-portal/docker-compose.yml up -d --build

# 2. 師傅
docker compose -f web/tech-portal/docker-compose.yml up -d --build

# 3. 導流
docker compose -f web/landing/docker-compose.yml up -d --build

# 4. 平台(含 Casdoor)
docker compose -f web/platform-console/docker-compose.yml up -d --build
```

> `--build` = 把最新 code 重新打包進容器(重佈署的意義所在)。
> 只是想「把停掉的容器開回來、不換 code」→ 去掉 `--build` 即可,快很多。
> 每段第一次跑可能要 3–10 分鐘(打包前端),之後有快取會快。

## 三、確認全部活著(貼這一段,一次檢查)

```bash
for u in 3000 3001 3002 3003; do curl -s -o /dev/null -w ":$u → %{http_code}\n" http://localhost:$u; done
curl -s -o /dev/null -w "品牌API :8001 → %{http_code}\n" http://localhost:8001/health
curl -s -o /dev/null -w "師傅API :8002 → %{http_code}\n" http://localhost:8002/health
curl -s -o /dev/null -w "平台API :8003 → %{http_code}\n" http://localhost:8003/health
```

**全部顯示 200 = 佈署成功。** 再用瀏覽器開 http://localhost:3000 登入
(`test@lock-ai.com` / `changeme123`)確認畫面正常。

## 四、常見狀況對照

| 症狀 | 原因 | 怎麼辦 |
|---|---|---|
| 指令回 `Cannot connect to the Docker daemon` | Docker Desktop 沒開 | 開 Docker Desktop,等鯨魚穩定再重跑 |
| 某個埠回 000 或打不開 | 該容器沒起來 | `docker ps -a` 看狀態;`docker logs <容器名> --tail 50` 看錯誤;通常對該 stack 重跑一次 up 指令即可 |
| 師傅 stack 起不來、說找不到網路 | 品牌 stack 沒先起 | 先跑第 1 段,再跑第 2 段 |
| 頁面開得起來但東西怪怪的/是舊的 | 容器跑的是舊 code | 確認該 stack 的 up 指令有帶 `--build` 重跑 |
| 佈署後資料不見 | 不會發生——資料存在 volume,重佈署不動資料 | 若真的異常,先問工程,**不要**跑任何 `down -v`(會刪資料庫) |

## 五、停掉全部(要收工時;資料會保留)

```bash
for f in web/brand-portal web/tech-portal web/landing web/platform-console; do
  docker compose -f $f/docker-compose.yml down
done
```

> ⚠️ 永遠不要加 `-v`(`down -v` 會把資料庫 volume 一起刪掉)。

## 附錄:雲端(GCP)重佈署一句話版

雲端三個服務各有一支腳本(需要 gcloud 登入權限,目前由工程執行):

```bash
./scripts/deploy/agent.sh    # Agent(LINE 客服)
./scripts/deploy/api.sh      # API
./scripts/deploy/web.sh      # 前端
```

細節與多品牌開站見 `docs/uat/open-station-sop-20260712.md` 與
`docs/uat/R6-cloud-topology-runbook-20260712.md`。
