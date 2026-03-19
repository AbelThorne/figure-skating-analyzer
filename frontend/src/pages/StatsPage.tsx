import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api, Score, Skater } from "../api/client";

export default function StatsPage() {
  const [selectedSkater, setSelectedSkater] = useState<number | null>(null);

  const { data: skaters } = useQuery({
    queryKey: ["skaters"],
    queryFn: api.skaters.list,
  });

  const { data: skaterScores } = useQuery({
    queryKey: ["skater-scores", selectedSkater],
    queryFn: () => api.skaters.scores(selectedSkater!),
    enabled: selectedSkater != null,
  });

  const progressionData = (skaterScores ?? [])
    .filter((s) => s.total_score != null)
    .sort((a, b) => {
      if (a.competition_date && b.competition_date)
        return a.competition_date > b.competition_date ? 1 : -1;
      return 0;
    })
    .map((s) => ({
      date: s.competition_date ? s.competition_date.slice(0, 10) : s.competition_name ?? "?",
      label: `${s.competition_name ?? ""} (${s.segment})`,
      total: s.total_score,
      tes: s.technical_score,
      pcs: s.component_score,
    }));

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Statistics</h1>

      <div className="bg-white border rounded p-4 shadow-sm mb-6">
        <h2 className="font-semibold mb-2">Skater progression</h2>
        <select
          className="border rounded px-3 py-2 w-full max-w-sm mb-4"
          value={selectedSkater ?? ""}
          onChange={(e) =>
            setSelectedSkater(e.target.value ? Number(e.target.value) : null)
          }
        >
          <option value="">Select a skater...</option>
          {skaters?.map((s: Skater) => (
            <option key={s.id} value={s.id}>
              {s.name} {s.nationality ? `(${s.nationality})` : ""}
            </option>
          ))}
        </select>

        {selectedSkater && progressionData.length === 0 && (
          <p className="text-gray-500 text-sm">No score data available for this skater.</p>
        )}

        {progressionData.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={progressionData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(value: number) => value?.toFixed(2)}
                labelFormatter={(label, payload) =>
                  payload?.[0]?.payload?.label ?? label
                }
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="total"
                name="Total Score"
                stroke="#2563eb"
                dot
              />
              <Line
                type="monotone"
                dataKey="tes"
                name="TES"
                stroke="#16a34a"
                dot
              />
              <Line
                type="monotone"
                dataKey="pcs"
                name="PCS"
                stroke="#d97706"
                dot
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
