import React from "react";
import { Archive, ArrowDownRight, ArrowUpRight } from "lucide-react";

function cx(...items: Array<string | false | null | undefined>): string {
  return items.filter(Boolean).join(" ");
}

const MASTER_WAVE_MAIN =
  "M -20,7 C 60,7 100,16 160,16 C 220,16 260,3 295,3 C 330,3 370,6 420,9 C 470,12 510,13 550,11 C 580,9 610,4 660,3 C 720,2 750,14 800,14 C 850,14 880,1 930,1 C 970,1 1010,6 1040,10 C 1070,14 1100,15 1130,12 C 1160,8 1190,2 1230,1";

const MASTER_WAVE_SHEEN =
  "M -20,4 C 60,4 100,13 160,13 C 220,13 260,0 295,0 C 330,0 370,3 420,6 C 470,9 510,10 550,8 C 580,6 610,1 660,0 C 720,-1 750,11 800,11 C 850,11 880,-2 930,-2 C 970,-2 1010,3 1040,7 C 1070,11 1100,12 1130,9 C 1160,5 1190,-1 1230,-2";

export function MetricCardWave({ index, totalCards = 7 }: { index: number; totalCards?: number }) {
  const cardCount = Math.max(totalCards, 1);
  const sliceW = 1200 / cardCount;
  const sliceX = (index % cardCount) * sliceW;
  const gradId = `cardWaveGrad_${index}_${cardCount}`;
  const glowId = `cardWaveGlow_${index}_${cardCount}`;
  const sheenId = `cardWaveSheen_${index}_${cardCount}`;

  return (
    <svg
      className="card-ribbon-svg"
      viewBox={`${sliceX} -2 ${sliceW} 26`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.32" />
          <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.48" />
          <stop offset="70%" stopColor="#f97316" stopOpacity="0.40" />
          <stop offset="100%" stopColor="#e39439" stopOpacity="0.26" />
        </linearGradient>
        <linearGradient id={glowId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.10" />
          <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#ea580c" stopOpacity="0.08" />
        </linearGradient>
        <linearGradient id={sheenId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.45" />
          <stop offset="50%" stopColor="#fff7ed" stopOpacity="0.80" />
          <stop offset="100%" stopColor="#fed7aa" stopOpacity="0.30" />
        </linearGradient>
      </defs>
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${glowId})`}
        strokeWidth="14"
        strokeLinecap="round"
      />
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="7"
        strokeLinecap="round"
      />
      <path
        d={MASTER_WAVE_SHEEN}
        fill="none"
        stroke={`url(#${sheenId})`}
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function MetricCard({
  icon,
  label,
  value,
  trendText,
  subTrendText,
  trend,
  tone = "neutral",
  cardIndex = 0,
  totalCards = 7,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  trendText?: string;
  subTrendText?: string;
  trend?: "up" | "down";
  tone?: "neutral" | "good" | "warn" | "bad" | "attention";
  cardIndex?: number;
  totalCards?: number;
}) {
  return (
    <article className={cx("metric-card", `metric-${tone}`)}>
      <MetricCardWave index={cardIndex} totalCards={totalCards} />
      <div className="metric-card-top">
        <div className="metric-header-left">
          {icon}
          <p>{label}</p>
        </div>
        <div className="sparkline-bars">
          <span style={{ height: 6 }} />
          <span style={{ height: 10 }} />
          <span style={{ height: 14 }} />
        </div>
      </div>
      <div className="metric-value-row">
        <strong>{typeof value === "number" ? value.toLocaleString() : value}</strong>
      </div>
      <div className="metric-footer">
        {trendText && (
          <span className={cx("trend-badge", trend)}>
            {trend === "up" ? <ArrowUpRight size={13} /> : trend === "down" ? <ArrowDownRight size={13} /> : null}
            {trendText}
          </span>
        )}
        {subTrendText && (
          <span className={cx("trend-badge", trend)}>
            {trend === "up" ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {subTrendText}
          </span>
        )}
      </div>
    </article>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <Archive aria-hidden="true" size={22} />
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
