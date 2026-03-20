import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Score } from "../api/client";

interface Props {
  scores: Score[];
}

const PCS_KEYS = [
  { key: "co", label: "CO — Composition" },
  { key: "pr", label: "PR — Présentation" },
  { key: "sk", label: "SK — Patinage de base" },
  { key: "pe", label: "PE — Performance" },
  { key: "in", label: "IN — Interprétation" },
];

const COLORS = ["#2e6385", "#a5d8ff", "#fdc97f"];

export default function PCSRadarChart({ scores }: Props) {
  // Filter to scores that have components
  const scoredWithComponents = scores.filter(
    (s) => s.components && Object.keys(s.components).length > 0
  );

  if (scoredWithComponents.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-on-surface-variant text-sm font-body">
        Aucune donnée de composantes disponible
      </div>
    );
  }

  // Take last 3 scores
  const last3 = scoredWithComponents.slice(-3);

  // Build radar data: one entry per PCS component
  const radarData = PCS_KEYS.map(({ key, label }) => {
    const entry: Record<string, string | number> = { subject: label };
    last3.forEach((score, idx) => {
      entry[`score_${idx}`] = score.components?.[key] ?? 0;
    });
    return entry;
  });

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={radarData} margin={{ top: 8, right: 24, left: 24, bottom: 8 }}>
        <PolarGrid stroke="#e0e3e5" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fontSize: 10, fontFamily: "Inter, sans-serif", fill: "#41484d" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 10]}
          tick={{ fontSize: 9, fontFamily: "monospace", fill: "#888" }}
          tickCount={5}
          axisLine={false}
        />
        <Tooltip
          formatter={(value: number, name: string) => {
            const idx = parseInt(name.replace("score_", ""), 10);
            const score = last3[idx];
            const label = score
              ? `${score.competition_name ?? "?"} (${score.segment})`
              : name;
            return [value?.toFixed(2), label];
          }}
          contentStyle={{
            fontSize: 11,
            fontFamily: "Inter, sans-serif",
            borderRadius: 12,
            border: "none",
            boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
          }}
        />
        {last3.map((score, idx) => (
          <Radar
            key={`score_${idx}`}
            name={`score_${idx}`}
            dataKey={`score_${idx}`}
            stroke={COLORS[idx]}
            fill={COLORS[idx]}
            fillOpacity={0.15}
            strokeWidth={2}
          />
        ))}
        <Legend
          formatter={(_value: string, entry: any) => {
            const idx = parseInt(entry.dataKey.replace("score_", ""), 10);
            const score = last3[idx];
            if (!score) return entry.dataKey;
            return `${score.competition_name ?? "?"} · ${score.segment}`;
          }}
          wrapperStyle={{ fontSize: 10, fontFamily: "Inter, sans-serif" }}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
