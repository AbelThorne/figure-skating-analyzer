import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Dot,
  Legend,
} from "recharts";
import { Element } from "../api/client";

interface Props {
  elements: Element[];
}

interface ChartEntry {
  date: string;
  competitionName: string;
  sp?: number;
  fs?: number;
}

function isShortProgram(segment: string): boolean {
  const s = segment.toUpperCase();
  return s === "SP" || s === "PH";
}

function isFreeSkating(segment: string): boolean {
  const s = segment.toUpperCase();
  return s === "FS" || s === "FP" || s === "LD";
}

export default function ElementDifficultyChart({ elements }: Props) {
  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-on-surface-variant text-sm font-body">
        Aucune donnée disponible
      </div>
    );
  }

  // Group by score_id → sum base values per score, track segment type
  const byScoreId = new Map<number, { date: string; total: number; competitionName: string; segment: string }>();
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
        segment: el.segment ?? "",
      });
    }
  }

  // Group by competition date+name → merge SP and FS base values
  const byCompetition = new Map<string, ChartEntry>();
  for (const { date, total, competitionName, segment } of byScoreId.values()) {
    const key = `${date}__${competitionName}`;
    if (!byCompetition.has(key)) {
      byCompetition.set(key, { date, competitionName });
    }
    const entry = byCompetition.get(key)!;
    const rounded = Math.round(total * 100) / 100;
    if (isShortProgram(segment)) {
      entry.sp = rounded;
    } else if (isFreeSkating(segment)) {
      entry.fs = rounded;
    } else {
      // Unknown segment — put in FS by default
      entry.fs = rounded;
    }
  }

  const data = [...byCompetition.values()].sort((a, b) =>
    a.date < b.date ? -1 : a.date > b.date ? 1 : 0
  );

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-on-surface-variant text-sm font-body">
        Aucune donnée disponible
      </div>
    );
  }

  const hasSp = data.some((d) => d.sp != null);
  const hasFs = data.some((d) => d.fs != null);

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const entry: ChartEntry = payload[0].payload;
    return (
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-3 text-xs font-body">
        <p className="text-on-surface-variant">{entry.competitionName}</p>
        <p className="text-on-surface-variant">{entry.date}</p>
        {entry.sp != null && (
          <p className="font-mono font-bold mt-1" style={{ color: "#2e6385" }}>
            Programme court : {entry.sp.toFixed(2)}
          </p>
        )}
        {entry.fs != null && (
          <p className="font-mono font-bold mt-1" style={{ color: "#7b4f9e" }}>
            Programme libre : {entry.fs.toFixed(2)}
          </p>
        )}
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
        {hasSp && hasFs && (
          <Legend
            formatter={(value: string) => value === "sp" ? "Programme court" : "Programme libre"}
            wrapperStyle={{ fontSize: 11, fontFamily: "Inter, sans-serif" }}
          />
        )}
        {hasSp && (
          <Line
            type="monotone"
            dataKey="sp"
            name="sp"
            stroke="#2e6385"
            strokeWidth={2}
            connectNulls
            dot={<Dot r={4} fill="#2e6385" stroke="#fff" strokeWidth={2} />}
            activeDot={{ r: 5, fill: "#2e6385", stroke: "#fff", strokeWidth: 2 }}
          />
        )}
        {hasFs && (
          <Line
            type="monotone"
            dataKey="fs"
            name="fs"
            stroke="#7b4f9e"
            strokeWidth={2}
            connectNulls
            dot={<Dot r={4} fill="#7b4f9e" stroke="#fff" strokeWidth={2} />}
            activeDot={{ r: 5, fill: "#7b4f9e", stroke: "#fff", strokeWidth: 2 }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
