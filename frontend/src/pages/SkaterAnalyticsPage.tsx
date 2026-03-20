import { useParams, Link } from "react-router-dom";
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
import { api, Element, Score } from "../api/client";
import ElementGOEChart from "../components/ElementGOEChart";
import PCSRadarChart from "../components/PCSRadarChart";
import ElementDifficultyChart from "../components/ElementDifficultyChart";
import JudgePanel from "../components/JudgePanel";

// ─── Jump detection ───────────────────────────────────────────────────────────
// Standard single-element jump codes: Axel family + toe/edge jumps
// Matches if element_name contains one of these as a recognisable jump component
const JUMP_PATTERN = /\d*(A|T|S|F|Lo|Lz|q)\b/i;
function isJumpElement(name: string) {
  return JUMP_PATTERN.test(name);
}

// ─── Spin detection ───────────────────────────────────────────────────────────
function isSpinElement(name: string) {
  return /Sp/i.test(name);
}
function spinLevel(name: string): number | null {
  const match = name.match(/(\d)$/);
  return match ? parseInt(match[1], 10) : null;
}

// ─── Step / choreo detection ──────────────────────────────────────────────────
function isStepElement(name: string) {
  return /St|ChSq/i.test(name);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function avg(arr: number[]) {
  if (!arr.length) return null;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────
function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse bg-surface-container-low rounded-xl ${className}`}
    />
  );
}

// ─── Metric card ─────────────────────────────────────────────────────────────
function MetricCard({
  label,
  value,
  unit,
  percent,
}: {
  label: string;
  value: string;
  unit?: string;
  percent?: number; // 0–100 for progress bar
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
        {label}
      </p>
      <p className="text-2xl font-extrabold font-headline text-on-surface font-mono">
        {value}
        {unit && (
          <span className="text-sm font-body font-normal text-on-surface-variant ml-1">
            {unit}
          </span>
        )}
      </p>
      {percent != null && (
        <div className="mt-3 h-1.5 rounded-full bg-primary-container overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ─── Stats box in hero ────────────────────────────────────────────────────────
function HeroStatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/15 backdrop-blur-sm rounded-xl px-5 py-3 text-center">
      <p className="text-2xl font-extrabold font-headline text-white font-mono">{value}</p>
      <p className="text-[10px] uppercase tracking-widest text-white/70 mt-0.5">{label}</p>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function SkaterAnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const skaterId = Number(id);

  const { data: skater, isLoading: loadingSkater } = useQuery({
    queryKey: ["skater", skaterId],
    queryFn: () => api.skaters.get(skaterId),
  });

  const { data: scores, isLoading: loadingScores } = useQuery({
    queryKey: ["skater-scores", skaterId],
    queryFn: () => api.skaters.scores(skaterId),
  });

  const { data: elements, isLoading: loadingElements } = useQuery({
    queryKey: ["skater-elements", skaterId],
    queryFn: () => api.skaters.elements(skaterId),
  });

  const isLoading = loadingSkater || loadingScores || loadingElements;

  // ── Derived: score progression ──────────────────────────────────────────────
  const progressionData = (scores ?? [])
    .filter((s) => s.total_score != null)
    .sort((a, b) => {
      if (a.competition_date && b.competition_date)
        return a.competition_date > b.competition_date ? 1 : -1;
      return 0;
    })
    .map((s) => ({
      date: s.competition_date ? s.competition_date.slice(0, 10) : (s.competition_name ?? "?"),
      label: `${s.competition_name ?? ""} (${s.segment})`,
      tes: s.technical_score,
      pcs: s.component_score,
    }));

  // ── Derived: sorted competition history ────────────────────────────────────
  const sortedScores: Score[] = [...(scores ?? [])].sort((a, b) => {
    if (a.competition_date && b.competition_date)
      return a.competition_date > b.competition_date ? -1 : 1;
    return 0;
  });

  // ── Derived: best TSS ──────────────────────────────────────────────────────
  const bestTss =
    (scores ?? []).reduce<number | null>((best, s) => {
      if (s.total_score == null) return best;
      return best == null || s.total_score > best ? s.total_score : best;
    }, null) ?? null;

  // ── Derived: element KPIs ──────────────────────────────────────────────────
  const hasElements = elements && elements.length > 0;

  const jumpPrecision = (() => {
    if (!elements?.length) return null;
    const jumps = elements.filter((el) => isJumpElement(el.element_name));
    if (!jumps.length) return null;
    const positive = jumps.filter((el) => (el.goe ?? 0) > 0).length;
    return (positive / jumps.length) * 100;
  })();

  const avgSpinLevel = (() => {
    if (!elements?.length) return null;
    const levels = elements
      .filter((el) => isSpinElement(el.element_name))
      .map((el) => spinLevel(el.element_name))
      .filter((l): l is number => l != null);
    return avg(levels);
  })();

  const stepGoe = (() => {
    if (!elements?.length) return null;
    const goeVals = elements
      .filter((el) => isStepElement(el.element_name))
      .map((el) => el.goe)
      .filter((g): g is number => g != null);
    return avg(goeVals);
  })();

  // ── Derived: last score elements for judge panel ───────────────────────────
  const lastScore = sortedScores[0] ?? null;
  const lastScoreElements = (elements ?? []).filter(
    (el) => lastScore && el.score_id === lastScore.id
  );

  // ─────────────────────────────────────────────────────────────────────────────
  if (!isLoading && !skater) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-on-surface-variant font-body">
        Patineur introuvable.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface font-body">
      {/* Back link */}
      <div className="px-6 pt-5 pb-2">
        <Link
          to="/patineurs"
          className="text-primary text-xs font-bold uppercase tracking-wider hover:underline flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-base">arrow_back</span>
          Retour
        </Link>
      </div>

      {/* ── Hero ── */}
      {isLoading ? (
        <Skeleton className="mx-6 h-36 rounded-2xl" />
      ) : (
        <div className="bg-gradient-to-r from-primary to-on-primary-fixed-variant py-8 px-8 flex flex-col sm:flex-row items-start sm:items-center gap-6">
          {/* Left: avatar + name */}
          <div className="flex items-center gap-5 flex-1 min-w-0">
            <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-2xl font-extrabold font-headline text-white ring-2 ring-white/30 shrink-0">
              {skater?.name?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0">
              <h1 className="text-3xl font-extrabold font-headline text-white leading-tight truncate">
                {skater?.name ?? "—"}
              </h1>
              <p className="text-sm text-white/70 mt-1">
                {[skater?.club, skater?.nationality].filter(Boolean).join(" · ")}
                {skater?.birth_year ? ` · ${skater.birth_year}` : ""}
              </p>
            </div>
          </div>
          {/* Right: stat boxes */}
          <div className="flex gap-3 shrink-0">
            <HeroStatBox
              label="Meilleur TSS"
              value={bestTss != null ? bestTss.toFixed(2) : "—"}
            />
            <HeroStatBox
              label="Compétitions"
              value={String(scores?.length ?? 0)}
            />
          </div>
        </div>
      )}

      {/* ── Main content ── */}
      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ────────── LEFT PANEL ────────── */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Score progression chart */}
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
            <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
              Analyse longitudinale des scores
            </h2>
            {isLoading ? (
              <Skeleton className="h-[260px] w-full" />
            ) : progressionData.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
                Aucune donnée de score disponible
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={progressionData} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
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
                    labelFormatter={(label, payload) =>
                      payload?.[0]?.payload?.label ?? label
                    }
                    contentStyle={{
                      fontSize: 11,
                      fontFamily: "Inter, sans-serif",
                      borderRadius: 12,
                      border: "none",
                      boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="tes"
                    name="TES"
                    stroke="#2e6385"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#2e6385", stroke: "#fff", strokeWidth: 1.5 }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pcs"
                    name="PCS"
                    stroke="#a5d8ff"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#a5d8ff", stroke: "#fff", strokeWidth: 1.5 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Competition history table */}
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
            <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
              Historique des compétitions
            </h2>
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : sortedScores.length === 0 ? (
              <p className="text-on-surface-variant text-sm">
                Aucune compétition enregistrée.
              </p>
            ) : (
              <div className="overflow-auto">
                <table className="w-full min-w-[560px] border-collapse">
                  <thead>
                    <tr className="bg-surface-container-low">
                      {["Compétition", "Date", "Épreuve", "Rang", "TES", "PCS", "Total"].map(
                        (col, i) => (
                          <th
                            key={col}
                            className={`text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 ${
                              i === 0 ? "text-left rounded-tl-xl" : "text-right"
                            } ${i === 6 ? "rounded-tr-xl" : ""}`}
                          >
                            {col}
                          </th>
                        )
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedScores.map((s, idx) => (
                      <tr
                        key={s.id}
                        className={
                          idx % 2 === 0
                            ? "bg-surface-container-lowest"
                            : "bg-surface-container-low/30"
                        }
                      >
                        <td className="px-3 py-2 text-sm text-on-surface">
                          <Link
                            to={`/competitions/${s.competition_id}`}
                            className="text-primary hover:underline font-medium"
                          >
                            {s.competition_name ?? `#${s.competition_id}`}
                          </Link>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant whitespace-nowrap">
                          {s.competition_date ? s.competition_date.slice(0, 10) : "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-sm text-on-surface-variant whitespace-nowrap">
                          {s.segment}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {s.rank != null ? (
                            s.rank <= 3 ? (
                              <span className="bg-tertiary-container/30 text-on-tertiary-container text-xs font-bold px-2 py-1 rounded-full">
                                {s.rank}
                              </span>
                            ) : (
                              <span className="font-mono text-sm text-on-surface">{s.rank}</span>
                            )
                          ) : (
                            <span className="text-on-surface-variant text-sm">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                          {s.technical_score?.toFixed(2) ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                          {s.component_score?.toFixed(2) ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-sm font-bold text-on-surface">
                          {s.total_score?.toFixed(2) ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* ────────── RIGHT PANEL ────────── */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          {isLoading ? (
            <>
              <Skeleton className="h-[200px] w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </>
          ) : hasElements ? (
            <>
              {/* Base value evolution */}
              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
                <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
                  Valeur de base totale
                </h2>
                <ElementDifficultyChart elements={elements!} />
              </div>

              {/* KPI metrics */}
              {jumpPrecision != null && (
                <MetricCard
                  label="Précision de saut"
                  value={`${jumpPrecision.toFixed(1)}%`}
                  percent={jumpPrecision}
                />
              )}
              {avgSpinLevel != null && (
                <MetricCard
                  label="Niveau de spin moyen"
                  value={avgSpinLevel.toFixed(2)}
                />
              )}
              {stepGoe != null && (
                <MetricCard
                  label="Note de pas"
                  value={`${stepGoe >= 0 ? "+" : ""}${stepGoe.toFixed(2)}`}
                />
              )}
            </>
          ) : (
            /* No elements: enrichissement card */
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
                    Importez les PDFs pour voir l'analyse d'éléments détaillée.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Second row: full-width charts ── */}
      <div className="px-6 pb-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* GOE chart */}
        <div className="lg:col-span-1 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
            GOE par élément
          </h2>
          {isLoading ? (
            <Skeleton className="h-[280px] w-full" />
          ) : (
            <ElementGOEChart elements={elements ?? []} />
          )}
        </div>

        {/* Judge panel */}
        <div className="lg:col-span-1 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <h2 className="text-base font-extrabold font-headline text-on-surface mb-2">
            Détail des juges — dernière épreuve
          </h2>
          {lastScore && (
            <p className="text-xs text-on-surface-variant mb-4">
              {lastScore.competition_name ?? "?"} · {lastScore.segment}
            </p>
          )}
          {isLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : (
            <JudgePanel elements={lastScoreElements} />
          )}
        </div>

        {/* PCS radar */}
        <div className="lg:col-span-1 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <h2 className="text-base font-extrabold font-headline text-on-surface mb-4">
            Composantes PCS
          </h2>
          {isLoading ? (
            <Skeleton className="h-[280px] w-full" />
          ) : (
            <PCSRadarChart scores={scores ?? []} />
          )}
        </div>
      </div>
    </div>
  );
}
