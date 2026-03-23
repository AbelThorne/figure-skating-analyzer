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
import { api, Skater } from "../api/client";

export default function StatsPage() {
  const [showAll, setShowAll] = useState(false);
  const [selectedSkater, setSelectedSkater] = useState<number | null>(null);
  const [progressionMode, setProgressionMode] = useState<"result" | "segments">("result");

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  const clubShort = config?.club_short;

  const { data: skaters = [] } = useQuery({
    queryKey: ["skaters", showAll ? null : clubShort],
    queryFn: () => api.skaters.list(showAll ? undefined : clubShort),
    enabled: showAll || !!clubShort,
  });

  const { data: skaterScores } = useQuery({
    queryKey: ["skater-scores", selectedSkater],
    queryFn: () => api.skaters.scores(selectedSkater!),
    enabled: selectedSkater != null,
  });

  const { data: categoryResults } = useQuery({
    queryKey: ["skater-category-results", selectedSkater],
    queryFn: () => api.skaters.categoryResults(selectedSkater!),
    enabled: selectedSkater != null,
  });

  // Progression by combined result — categoryResults primary, scores fallback
  const progressionDataResult = (() => {
    const map = new Map<string, { date: string; label: string; total: number | null }>();
    for (const r of categoryResults ?? []) {
      if (r.combined_total == null) continue;
      const key = `${r.competition_id}__${r.category ?? ""}`;
      map.set(key, {
        date: r.competition_date ? r.competition_date.slice(0, 10) : (r.competition_name ?? "?"),
        label: `${r.competition_name ?? ""} · ${r.category ?? ""}`,
        total: r.combined_total,
      });
    }
    for (const s of skaterScores ?? []) {
      if (s.total_score == null) continue;
      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!map.has(key)) {
        map.set(key, {
          date: s.competition_date ? s.competition_date.slice(0, 10) : (s.competition_name ?? "?"),
          label: `${s.competition_name ?? ""} · ${s.category ?? ""}`,
          total: s.total_score,
        });
      }
    }
    return [...map.values()].sort((a, b) => (a.date > b.date ? 1 : -1));
  })();

  // Progression by segment (SP and FS as separate series)
  const progressionDataSegments = (() => {
    const map = new Map<string, { date: string; label: string; sp?: number; fs?: number }>();
    for (const s of (skaterScores ?? []).filter((s) => s.total_score != null)) {
      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!map.has(key)) {
        map.set(key, {
          date: s.competition_date ? s.competition_date.slice(0, 10) : (s.competition_name ?? "?"),
          label: `${s.competition_name ?? ""} · ${s.category ?? ""}`,
        });
      }
      const entry = map.get(key)!;
      const seg = s.segment?.toUpperCase();
      if (seg === "SP" || seg === "PH") entry.sp = s.total_score ?? undefined;
      else if (seg === "FS" || seg === "FP" || seg === "LD") entry.fs = s.total_score ?? undefined;
    }
    return [...map.values()].sort((a, b) => (a.date > b.date ? 1 : -1));
  })();

  const progressionData = progressionMode === "result" ? progressionDataResult : progressionDataSegments;

  return (
    <div className="p-6 space-y-6 font-body">
      {/* Page header */}
      <div>
        <h1 className="font-headline text-2xl font-bold text-on-surface">Statistiques</h1>
        <p className="text-sm text-on-surface-variant mt-1">Progression individuelle des patineurs</p>
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
          <h2 className="text-base font-extrabold font-headline text-on-surface">
            Progression d'un patineur
          </h2>
          {/* Result / Segments toggle */}
          {selectedSkater && (
            <div className="flex rounded-lg overflow-hidden border border-outline-variant text-xs font-bold">
              <button
                onClick={() => setProgressionMode("result")}
                className={`px-3 py-1.5 transition-colors ${
                  progressionMode === "result"
                    ? "bg-primary text-on-primary"
                    : "bg-surface text-on-surface-variant hover:bg-surface-container"
                }`}
              >
                Résultat
              </button>
              <button
                onClick={() => setProgressionMode("segments")}
                className={`px-3 py-1.5 transition-colors ${
                  progressionMode === "segments"
                    ? "bg-primary text-on-primary"
                    : "bg-surface text-on-surface-variant hover:bg-surface-container"
                }`}
              >
                Segments
              </button>
            </div>
          )}
        </div>

        {/* Skater selector + club toggle */}
        <div className="flex items-center gap-3 flex-wrap mb-5">
          <select
            className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary flex-1 max-w-xs"
            value={selectedSkater ?? ""}
            onChange={(e) => setSelectedSkater(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Sélectionner un patineur…</option>
            {skaters.map((s: Skater) => (
              <option key={s.id} value={s.id}>
                {s.first_name} {s.last_name}{s.club ? ` · ${s.club}` : ""}
              </option>
            ))}
          </select>

          {clubShort && (
            <button
              onClick={() => setShowAll((v) => !v)}
              className="border border-outline-variant text-on-surface-variant rounded-lg py-2 px-3 text-xs font-bold active:scale-95 transition-all"
            >
              {showAll ? "Afficher mon club uniquement" : "Afficher tous les clubs"}
            </button>
          )}
        </div>

        {selectedSkater && progressionData.length === 0 && (
          <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
            Aucune donnée disponible pour ce patineur.
          </div>
        )}

        {!selectedSkater && (
          <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
            Sélectionnez un patineur pour afficher sa progression.
          </div>
        )}

        {progressionData.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            {progressionMode === "result" ? (
              <LineChart data={progressionDataResult} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
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
                <Tooltip
                  formatter={(value: number) => [value?.toFixed(2), "Total"]}
                  labelFormatter={(label, payload) => payload?.[0]?.payload?.label ?? label}
                  contentStyle={{ fontSize: 11, fontFamily: "Inter, sans-serif", borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Total"
                  stroke="#2e6385"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "#2e6385", stroke: "#fff", strokeWidth: 1.5 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            ) : (
              <LineChart data={progressionDataSegments} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
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
                <Tooltip
                  formatter={(value: number) => value?.toFixed(2)}
                  labelFormatter={(label, payload) => payload?.[0]?.payload?.label ?? label}
                  contentStyle={{ fontSize: 11, fontFamily: "Inter, sans-serif", borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="sp"
                  name="Programme Court"
                  stroke="#2e6385"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#2e6385", stroke: "#fff", strokeWidth: 1.5 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="fs"
                  name="Programme Libre"
                  stroke="#7cb9e8"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#7cb9e8", stroke: "#fff", strokeWidth: 1.5 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
