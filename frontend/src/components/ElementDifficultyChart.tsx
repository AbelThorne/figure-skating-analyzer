import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Dot,
} from "recharts";
import { Element } from "../api/client";

interface Props {
  elements: Element[];
}

interface ChartEntry {
  date: string;
  totalBaseValue: number;
  scoreId: number;
  competitionName: string;
}

export default function ElementDifficultyChart({ elements }: Props) {
  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-on-surface-variant text-sm font-body">
        Aucune donnée disponible
      </div>
    );
  }

  // Group by score_id → sum base values
  const byScoreId = new Map<number, { date: string; total: number; competitionName: string }>();
  for (const el of elements) {
    if (el.base_value == null) continue;
    const existing = byScoreId.get(el.score_id);
    if (existing) {
      existing.total += el.base_value;
    } else {
      byScoreId.set(el.score_id, {
        date: el.competition_date ? el.competition_date.slice(0, 10) : (el.competition_name ?? "?"),
        total: el.base_value,
        competitionName: el.competition_name ?? "?",
      });
    }
  }

  const data: ChartEntry[] = Array.from(byScoreId.entries())
    .map(([scoreId, { date, total, competitionName }]) => ({
      date,
      totalBaseValue: Math.round(total * 100) / 100,
      scoreId,
      competitionName,
    }))
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-on-surface-variant text-sm font-body">
        Aucune donnée disponible
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const entry: ChartEntry = payload[0].payload;
    return (
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-3 text-xs font-body">
        <p className="text-on-surface-variant">{entry.competitionName}</p>
        <p className="text-on-surface-variant">{entry.date}</p>
        <p className="font-mono font-bold text-primary mt-1">
          BV total : {entry.totalBaseValue.toFixed(2)}
        </p>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#e0e3e5" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fontFamily: "Inter, sans-serif", fill: "#41484d" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fontFamily: "monospace", fill: "#41484d" }}
          axisLine={false}
          tickLine={false}
          domain={["auto", "auto"]}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="totalBaseValue"
          stroke="#2e6385"
          strokeWidth={2}
          dot={<Dot r={4} fill="#2e6385" stroke="#fff" strokeWidth={2} />}
          activeDot={{ r: 5, fill: "#2e6385", stroke: "#fff", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
