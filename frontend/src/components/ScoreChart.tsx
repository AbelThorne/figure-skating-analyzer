import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Score } from "../api/client";

interface Props {
  scores: Score[];
}

export default function ScoreChart({ scores }: Props) {
  if (scores.length === 0) return null;

  const data = scores.map((s) => ({
    name: s.skater_first_name ? `${s.skater_first_name} ${s.skater_last_name}` : (s.skater_last_name || `#${s.rank}`),
    TES: s.technical_score ?? 0,
    PCS: s.component_score ?? 0,
    Ded: s.deductions ? -s.deductions : 0,
  }));

  return (
    <div style={{ width: "100%", height: 220 }}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => v.toFixed(2)} />
        <Legend />
        <Bar dataKey="TES" stackId="a" fill="#2563eb" />
        <Bar dataKey="PCS" stackId="a" fill="#16a34a" />
        <Bar dataKey="Ded" stackId="a" fill="#dc2626" />
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}
