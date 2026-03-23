import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceArea, ReferenceLine,
  BarChart, Bar,
} from "recharts";
import { api, ProgressionRankingEntry, Skater, CategoryResult, BenchmarkData } from "../api/client";

// ─── Sparkline component ─────────────────────────────────────────────────────
function Sparkline({ data }: { data: { value: number }[] }) {
  if (data.length < 2) return null;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 80, h = 24;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke="#2e6385" strokeWidth="1.5" />
    </svg>
  );
}

// ─── Sort helper ──────────────────────────────────────────────────────────────
type SortKey = "tss_gain" | "last_tss" | "skater_name" | "competitions_count";

export default function StatsPage() {
  // ── Shared filter state ────────────────────────────────────────────────────
  const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [selectedAgeGroup, setSelectedAgeGroup] = useState<string | null>(null);
  const [selectedGender, setSelectedGender] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("tss_gain");
  const [sortAsc, setSortAsc] = useState(false);

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  const season = selectedSeason ?? config?.current_season ?? undefined;

  // ── Progression ranking ────────────────────────────────────────────────────
  const { data: ranking = [], isLoading: loadingRanking } = useQuery({
    queryKey: ["progression-ranking", season, selectedLevel, selectedAgeGroup, selectedGender],
    queryFn: () =>
      api.stats.progressionRanking({
        season,
        skating_level: selectedLevel ?? undefined,
        age_group: selectedAgeGroup ?? undefined,
        gender: selectedGender ?? undefined,
      }),
    placeholderData: keepPreviousData,
  });

  // ── Derive filter options from ranking data ────────────────────────────────
  const filterOptions = useMemo(() => {
    const levels = new Set<string>();
    const ages = new Set<string>();
    const genders = new Set<string>();
    for (const r of ranking) {
      if (r.skating_level) levels.add(r.skating_level);
      if (r.age_group) ages.add(r.age_group);
      if (r.gender) genders.add(r.gender);
    }
    return {
      levels: [...levels].sort(),
      ageGroups: [...ages].sort(),
      genders: [...genders].sort(),
    };
  }, [ranking]);

  // ── Sorted ranking ─────────────────────────────────────────────────────────
  const sortedRanking = useMemo(() => {
    const sorted = [...ranking].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "skater_name") cmp = a.skater_name.localeCompare(b.skater_name);
      else cmp = (a[sortKey] ?? 0) - (b[sortKey] ?? 0);
      if (cmp === 0) cmp = (b.last_tss ?? 0) - (a.last_tss ?? 0); // tie-break
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [ranking, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  }

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? "arrow_upward" : "arrow_downward") : "";

  // ── Comparison section state ───────────────────────────────────────────────
  const [selectedSkaterIds, setSelectedSkaterIds] = useState<number[]>([]);
  const [levelOverride, setLevelOverride] = useState<string | null>(null);

  const { data: skaters = [] } = useQuery({
    queryKey: ["skaters", config?.club_short],
    queryFn: () => api.skaters.list(config?.club_short),
    enabled: !!config?.club_short,
  });

  const SKATER_COLORS = ["#2e6385", "#7cb9e8", "#e8a87c"];

  // Fetch category results for each selected skater (max 3, fixed-length hook calls)
  const skater0Query = useQuery({
    queryKey: ["skater-category-results", selectedSkaterIds[0], season],
    queryFn: () => api.skaters.categoryResults(selectedSkaterIds[0]!, season),
    enabled: selectedSkaterIds.length > 0,
  });
  const skater1Query = useQuery({
    queryKey: ["skater-category-results", selectedSkaterIds[1], season],
    queryFn: () => api.skaters.categoryResults(selectedSkaterIds[1]!, season),
    enabled: selectedSkaterIds.length > 1,
  });
  const skater2Query = useQuery({
    queryKey: ["skater-category-results", selectedSkaterIds[2], season],
    queryFn: () => api.skaters.categoryResults(selectedSkaterIds[2]!, season),
    enabled: selectedSkaterIds.length > 2,
  });

  const skaterResults = useMemo(() =>
    selectedSkaterIds.map((id, i) => ({
      id,
      color: SKATER_COLORS[i],
      results: [skater0Query, skater1Query, skater2Query][i]?.data ?? [],
    })),
    [selectedSkaterIds, skater0Query.data, skater1Query.data, skater2Query.data]
  );

  // Determine benchmark params from first selected skater's results
  const firstSkaterResult = skaterResults[0]?.results[0];
  const benchmarkLevel = levelOverride ?? firstSkaterResult?.skating_level ?? null;
  const benchmarkAgeGroup = firstSkaterResult?.age_group ?? null;
  const benchmarkGender = firstSkaterResult?.gender ?? null;

  const { data: benchmark } = useQuery({
    queryKey: ["benchmarks", benchmarkLevel, benchmarkAgeGroup, benchmarkGender, season],
    queryFn: () =>
      api.stats.benchmarks({
        skating_level: benchmarkLevel!,
        age_group: benchmarkAgeGroup!,
        gender: benchmarkGender!,
        season,
      }),
    enabled: !!benchmarkLevel && !!benchmarkAgeGroup && !!benchmarkGender,
  });

  // Build chart data: merge all skaters' results onto a common date axis
  const comparisonData = useMemo(() => {
    const dateMap = new Map<string, Record<string, number | null>>();
    for (const { id, results } of skaterResults) {
      for (const r of results) {
        if (!r.competition_date || r.combined_total == null) continue;
        const date = r.competition_date.slice(0, 10);
        if (!dateMap.has(date)) dateMap.set(date, {});
        dateMap.get(date)![`skater_${id}`] = r.combined_total;
      }
    }
    return [...dateMap.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, values]) => ({ date, ...values }));
  }, [skaterResults]);

  function toggleSkater(id: number) {
    setSelectedSkaterIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 3) return prev;
      return [...prev, id];
    });
  }

  // ── Element mastery ────────────────────────────────────────────────────────
  const { data: mastery, isLoading: loadingMastery } = useQuery({
    queryKey: ["element-mastery", season, selectedLevel, selectedAgeGroup, selectedGender],
    queryFn: () =>
      api.stats.elementMastery({
        season,
        skating_level: selectedLevel ?? undefined,
        age_group: selectedAgeGroup ?? undefined,
        gender: selectedGender ?? undefined,
      }),
    placeholderData: keepPreviousData,
  });

  const hasElements = mastery && (mastery.jumps.length > 0 || mastery.spins.length > 0 || mastery.steps.length > 0);

  return (
    <div className="p-6 space-y-6 font-body">
      {/* Page header */}
      <div>
        <h1 className="font-headline text-2xl font-bold text-on-surface">Vue club</h1>
        <p className="text-sm text-on-surface-variant mt-1">
          Analyse collective des patineurs du club
        </p>
      </div>

      {/* Shared filters */}
      <div className="flex flex-wrap gap-3">
        {config?.current_season && (
          <select
            className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            value={selectedSeason ?? ""}
            onChange={(e) => setSelectedSeason(e.target.value || null)}
          >
            <option value="">Saison en cours</option>
          </select>
        )}
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedLevel ?? ""}
          onChange={(e) => setSelectedLevel(e.target.value || null)}
        >
          <option value="">Tous les niveaux</option>
          {filterOptions.levels.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedAgeGroup ?? ""}
          onChange={(e) => setSelectedAgeGroup(e.target.value || null)}
        >
          <option value="">Toutes les catégories</option>
          {filterOptions.ageGroups.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select
          className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedGender ?? ""}
          onChange={(e) => setSelectedGender(e.target.value || null)}
        >
          <option value="">Tous</option>
          {filterOptions.genders.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      </div>

      {/* ── PROGRESSION SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Progression
        </h2>
        {loadingRanking ? (
          <div className="animate-pulse bg-surface-container-low rounded-xl h-40" />
        ) : sortedRanking.length === 0 ? (
          <p className="text-on-surface-variant text-sm">
            {selectedLevel || selectedAgeGroup || selectedGender
              ? "Aucun résultat pour les filtres sélectionnés."
              : "Aucun patineur n'a participé à au moins 2 compétitions cette saison."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse">
              <thead>
                <tr className="bg-surface-container-low">
                  {[
                    { key: "skater_name" as SortKey, label: "Patineur", left: true },
                    { key: null, label: "Niveau / Catégorie", left: false },
                    { key: null, label: "Premier", left: false },
                    { key: null, label: "Dernier", left: false },
                    { key: "tss_gain" as SortKey, label: "\u0394", left: false },
                    { key: null, label: "Tendance", left: false },
                    { key: "competitions_count" as SortKey, label: "Comp.", left: false },
                  ].map((col, i) => (
                    <th
                      key={col.label}
                      className={`text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 ${
                        col.left ? "text-left" : "text-right"
                      } ${i === 0 ? "rounded-tl-xl" : ""} ${i === 6 ? "rounded-tr-xl" : ""} ${
                        col.key ? "cursor-pointer select-none hover:text-on-surface" : ""
                      }`}
                      onClick={col.key ? () => toggleSort(col.key!) : undefined}
                    >
                      {col.label}
                      {col.key && sortIcon(col.key) && (
                        <span className="material-symbols-outlined text-[12px] ml-0.5 align-middle">
                          {sortIcon(col.key)}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRanking.map((entry, idx) => (
                  <tr
                    key={`${entry.skater_id}-${entry.skating_level}`}
                    className={idx % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"}
                  >
                    <td className="px-3 py-2 text-sm">
                      <Link
                        to={`/patineurs/${entry.skater_id}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {entry.skater_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className="inline-block bg-primary-container/30 text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded-full">
                        {[entry.skating_level, entry.age_group].filter(Boolean).join(" \u00b7 ")}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">
                      {entry.first_tss.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                      {entry.last_tss.toFixed(2)}
                    </td>
                    <td className={`px-3 py-2 text-right font-mono text-sm font-bold ${
                      entry.tss_gain > 0 ? "text-green-700" : entry.tss_gain < 0 ? "text-error" : "text-on-surface-variant"
                    }`}>
                      {entry.tss_gain > 0 ? "+" : ""}{entry.tss_gain.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Sparkline data={entry.sparkline} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">
                      {entry.competitions_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── COMPARISON SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Comparaison
        </h2>

        {/* Skater selector as pills */}
        <div className="flex flex-wrap gap-2 mb-4">
          {skaters.map((s: Skater) => {
            const selected = selectedSkaterIds.includes(s.id);
            const idx = selectedSkaterIds.indexOf(s.id);
            return (
              <button
                key={s.id}
                onClick={() => toggleSkater(s.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-colors ${
                  selected
                    ? "text-white"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container"
                }`}
                style={selected ? { backgroundColor: SKATER_COLORS[idx] } : {}}
                disabled={!selected && selectedSkaterIds.length >= 3}
              >
                {s.first_name} {s.last_name}
              </button>
            );
          })}
        </div>

        {/* Level override */}
        {selectedSkaterIds.length > 0 && (
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs text-on-surface-variant">Comparer au niveau :</span>
            <select
              className="bg-surface-container-high rounded-lg px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={levelOverride ?? ""}
              onChange={(e) => setLevelOverride(e.target.value || null)}
            >
              <option value="">
                {benchmarkLevel ?? "Auto"}
              </option>
              {filterOptions.levels.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            {benchmark && benchmark.data_points > 0 && benchmark.data_points < 3 && (
              <span className="text-xs text-on-surface-variant italic">
                Données insuffisantes pour le benchmark
              </span>
            )}
          </div>
        )}

        {selectedSkaterIds.length === 0 ? (
          <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
            Sélectionnez des patineurs pour comparer leur progression.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={comparisonData} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
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
                contentStyle={{
                  fontSize: 11, fontFamily: "Inter, sans-serif",
                  borderRadius: 12, border: "none",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />

              {/* Benchmark bands */}
              {benchmark && benchmark.data_points >= 3 && benchmark.min != null && benchmark.max != null && (
                <>
                  <ReferenceArea
                    y1={benchmark.min} y2={benchmark.max}
                    fill="#2e6385" fillOpacity={0.04}
                    label={{ value: "", position: "right" }}
                  />
                  <ReferenceArea
                    y1={benchmark.p25!} y2={benchmark.p75!}
                    fill="#2e6385" fillOpacity={0.08}
                  />
                  <ReferenceLine
                    y={benchmark.median!}
                    stroke="#2e6385" strokeDasharray="4 4" strokeOpacity={0.5}
                    label={{ value: "Médiane", position: "right", fontSize: 9, fill: "#41484d" }}
                  />
                </>
              )}

              {/* Skater lines */}
              {skaterResults.map(({ id, color }) => {
                const skater = skaters.find((s: Skater) => s.id === id);
                return (
                  <Line
                    key={id}
                    type="monotone"
                    dataKey={`skater_${id}`}
                    name={skater ? `${skater.first_name} ${skater.last_name}` : `#${id}`}
                    stroke={color}
                    strokeWidth={2}
                    dot={{ r: 3, fill: color, stroke: "#fff", strokeWidth: 1.5 }}
                    connectNulls={false}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── ELEMENT MASTERY SECTION ── */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
        <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
          Maîtrise des éléments
        </h2>

        {loadingMastery ? (
          <div className="animate-pulse bg-surface-container-low rounded-xl h-60" />
        ) : !hasElements ? (
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 border-l-4 border-tertiary">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-tertiary text-2xl mt-0.5">
                picture_as_pdf
              </span>
              <div>
                <p className="font-bold font-headline text-on-surface">
                  Enrichir avec les PDF
                </p>
                <p className="text-xs text-on-surface-variant mt-1">
                  {mastery && mastery.jumps.length === 0 && (selectedLevel || selectedAgeGroup || selectedGender)
                    ? "Aucun élément trouvé pour les filtres sélectionnés."
                    : "Importez les PDFs pour voir l'analyse d'éléments détaillée."}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Jump success rates */}
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Taux de réussite des sauts
              </h3>
              <ResponsiveContainer width="100%" height={Math.max(200, mastery!.jumps.length * 32)}>
                <BarChart
                  data={mastery!.jumps}
                  layout="vertical"
                  margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
                >
                  <CartesianGrid horizontal={false} stroke="#e0e3e5" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category" dataKey="jump_type" width={40}
                    tick={{ fontSize: 11, fontFamily: "monospace", fill: "#191c1e" }}
                    axisLine={false} tickLine={false}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
                    contentStyle={{ fontSize: 11, borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                  />
                  <Bar dataKey="positive_goe_pct" name="GOE +" stackId="goe" fill="#4caf50" />
                  <Bar dataKey="neutral_goe_pct" name="GOE 0" stackId="goe" fill="#ffc107" />
                  <Bar dataKey="negative_goe_pct" name="GOE −" stackId="goe" fill="#f44336" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Spin/step level distribution */}
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Niveaux pirouettes et pas
              </h3>
              {(() => {
                const LEVEL_COLORS = ["#e0e0e0", "#b0bec5", "#78909c", "#455a64", "#263238"];
                const combined = [...(mastery!.spins ?? []), ...(mastery!.steps ?? [])];
                const chartData = combined.map((el) => ({
                  name: el.element_type,
                  ...Object.fromEntries(
                    Object.entries(el.level_distribution).map(([k, v]) => [`level_${k}`, v])
                  ),
                  avg_goe: el.avg_goe,
                  attempts: el.attempts,
                }));
                return (
                  <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 32)}>
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid horizontal={false} stroke="#e0e3e5" />
                      <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category" dataKey="name" width={60}
                        tick={{ fontSize: 11, fontFamily: "monospace", fill: "#191c1e" }}
                        axisLine={false} tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{ fontSize: 11, borderRadius: 12, border: "none", boxShadow: "0 1px 4px rgba(0,0,0,0.12)" }}
                      />
                      {[0, 1, 2, 3, 4].map((level) => (
                        <Bar
                          key={level}
                          dataKey={`level_${level}`}
                          name={`Niveau ${level}`}
                          stackId="levels"
                          fill={LEVEL_COLORS[level]}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                );
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
