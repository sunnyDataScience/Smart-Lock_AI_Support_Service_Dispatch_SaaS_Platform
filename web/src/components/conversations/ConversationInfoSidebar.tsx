import { Phone, MessageCircle, MapPin } from "lucide-react";

function InfoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border-[1.5px] border-[#E4E4E7] bg-[var(--bg-surface)] p-4">
      <h3 className="text-[14px] font-semibold text-[#18181B]">{title}</h3>
      {children}
    </div>
  );
}

function InfoRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[13px] text-[#A1A1AA]">{label}</span>
      <span
        className="text-[13px] font-medium"
        style={{ color: valueColor ?? "#18181B" }}
      >
        {value}
      </span>
    </div>
  );
}

export default function ConversationInfoSidebar() {
  return (
    <aside className="flex w-[380px] flex-col gap-4 overflow-auto border-l border-[var(--border)] bg-[var(--bg-surface)] p-6">
      <InfoCard title="客戶資訊">
        <span className="text-[16px] font-bold text-[#18181B]">陳小姐</span>
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-[#71717A]" />
          <span className="text-[13px] text-[#71717A]">0912-345-678</span>
        </div>
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-[#71717A]" />
          <span className="text-[13px] text-[#71717A]">@chen_mei</span>
        </div>
        <div className="flex gap-2">
          <MapPin className="mt-[2px] h-4 w-4 shrink-0 text-[#71717A]" />
          <span className="text-[13px] leading-[1.5] text-[#71717A]">
            台北市大安區忠孝東路四段100號12F
          </span>
        </div>
        <span className="text-[12px] text-[#A1A1AA]">歷史對話 3 次</span>
        <button className="text-left text-[13px] font-medium text-[var(--primary)]">
          查看歷史 →
        </button>
      </InfoCard>

      <InfoCard title="問題摘要">
        <p className="text-[13px] leading-[1.5] text-[#71717A]">
          Yale YDM-4109
          電子鎖密碼驗證通過但無法解鎖，疑似離合器故障。電池上月更換，螢幕顯示鎖頭圖案錯誤代碼。
        </p>
        <div className="flex gap-2">
          <span className="rounded-lg border-[1.5px] border-[#E4E4E7] px-[10px] py-1 text-[12px] font-medium text-[#18181B]">
            Yale
          </span>
          <span className="rounded-lg border-[1.5px] border-[var(--primary)] px-[10px] py-1 text-[12px] font-medium text-[var(--primary)]">
            YDM-4109
          </span>
        </div>
        <div className="flex flex-wrap gap-[6px]">
          {["無法解鎖", "離合器異常", "錯誤代碼"].map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-[#EFF6FF] px-[10px] py-1 text-[11px] font-medium text-[var(--primary)]"
            >
              {tag}
            </span>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-[12px] font-semibold uppercase tracking-wider text-[#A1A1AA]">
            AI 診斷結論
          </span>
          <p className="text-[13px] font-medium leading-[1.4] text-[#18181B]">
            AI 初步診斷: 鎖體離合器故障 (信心度 87%)
          </p>
          <div className="h-[6px] w-full overflow-hidden rounded-full bg-[#E4E4E7]">
            <div className="h-full w-[87%] rounded-full bg-[var(--primary)]" />
          </div>
        </div>
      </InfoCard>

      <InfoCard title="關聯工單">
        <span className="text-[12px] text-[#A1A1AA]">
          此對話尚未關聯工單
        </span>
        <button className="w-full rounded-lg bg-[var(--primary)] py-[10px] text-center text-[14px] font-semibold text-white">
          建立工單
        </button>
      </InfoCard>

      <InfoCard title="對話資訊">
        <InfoRow label="建立時間" value="2026-04-22 14:23" />
        <InfoRow label="最後更新" value="2026-04-22 14:26" />
        <InfoRow label="訊息總數" value="6 則" />
        <InfoRow label="AI 回覆" value="2 則" />
        <InfoRow label="標記回饋" value="1 則" valueColor="#F59E0B" />
      </InfoCard>
    </aside>
  );
}
