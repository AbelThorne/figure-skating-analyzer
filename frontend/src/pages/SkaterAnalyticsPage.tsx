import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
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
import { api, downloadPdf, Element, Score, CategoryResult, TimelineEntry, WeeklyReview, TrainingIncident } from "../api/client";
import ElementGOEChart from "../components/ElementGOEChart";
import PCSRadarChart from "../components/PCSRadarChart";
import ElementDifficultyChart from "../components/ElementDifficultyChart";
import JudgePanel from "../components/JudgePanel";
import ScoreCardModal from "../components/ScoreCardModal";
import TrainingEvolutionChart from "../components/TrainingEvolutionChart";
import { countryFlag } from "../utils/countryFlags";
import { isJumpElement, isSpinElement, isStepElement, elementLevel } from "../utils/elementClassifier";
import { useAuth } from "../auth/AuthContext";

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
  info,
}: {
  label: string;
  value: string;
  unit?: string;
  percent?: number;
  info?: string;
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center gap-1.5 mb-2">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
          {label}
        </p>
        {info && (
          <span className="group relative cursor-help">
            <span className="material-symbols-outlined text-on-surface-variant text-[14px]">info</span>
            <span className="invisible group-hover:visible absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 w-56 bg-on-surface text-surface text-[11px] font-body font-normal normal-case tracking-normal rounded-lg px-3 py-2 shadow-lg z-50 leading-relaxed">
              {info}
            </span>
          </span>
        )}
      </div>
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

// ─── Dual metric card (level + GOE side by side) ────────────────────────────
function DualMetricCard({
  label,
  leftLabel,
  leftValue,
  rightLabel,
  rightValue,
  info,
}: {
  label: string;
  leftLabel: string;
  leftValue: string;
  rightLabel: string;
  rightValue: string;
  info?: string;
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center gap-1.5 mb-3">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
          {label}
        </p>
        {info && (
          <span className="group relative cursor-help">
            <span className="material-symbols-outlined text-on-surface-variant text-[14px]">info</span>
            <span className="invisible group-hover:visible absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 w-56 bg-on-surface text-surface text-[11px] font-body font-normal normal-case tracking-normal rounded-lg px-3 py-2 shadow-lg z-50 leading-relaxed">
              {info}
            </span>
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-0.5">
            {leftLabel}
          </p>
          <p className="text-xl font-extrabold font-headline text-on-surface font-mono">
            {leftValue}
          </p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-0.5">
            {rightLabel}
          </p>
          <p className="text-xl font-extrabold font-headline text-on-surface font-mono">
            {rightValue}
          </p>
        </div>
      </div>
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
  const { user } = useAuth();
  const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
  const [analyticsTab, setAnalyticsTab] = useState<"competitions" | "training">(
    user?.role === "skater" ? "training" : "competitions"
  );

  const { data: skater, isLoading: loadingSkater } = useQuery({
    queryKey: ["skater", skaterId],
    queryFn: () => api.skaters.get(skaterId),
  });

  const { data: seasons } = useQuery({
    queryKey: ["skater-seasons", skaterId],
    queryFn: () => api.skaters.seasons(skaterId),
  });

  const { data: scores, isLoading: loadingScores } = useQuery({
    queryKey: ["skater-scores", skaterId, selectedSeason],
    queryFn: () => api.skaters.scores(skaterId, selectedSeason ?? undefined),
    placeholderData: keepPreviousData,
  });

  const { data: elements, isLoading: loadingElements } = useQuery({
    queryKey: ["skater-elements", skaterId, selectedSeason],
    queryFn: () => api.skaters.elements(skaterId, { season: selectedSeason ?? undefined }),
    placeholderData: keepPreviousData,
  });

  const { data: categoryResults, isLoading: loadingCatResults } = useQuery({
    queryKey: ["skater-category-results", skaterId, selectedSeason],
    queryFn: () => api.skaters.categoryResults(skaterId, selectedSeason ?? undefined),
    placeholderData: keepPreviousData,
  });

  const { data: timeline } = useQuery({
    queryKey: ["training", "timeline", skaterId],
    queryFn: () => api.training.timeline({ skater_id: skaterId }),
    enabled: user?.role === "skater",
  });

  const { data: trainingReviews } = useQuery({
    queryKey: ["training", "reviews", skaterId],
    queryFn: () => api.training.reviews.list({ skater_id: skaterId }),
    enabled: user?.role === "skater",
  });

  const { data: trainingIncidents } = useQuery({
    queryKey: ["training", "incidents", skaterId],
    queryFn: () => api.training.incidents.list({ skater_id: skaterId }),
    enabled: user?.role === "skater",
  });

  const isLoading = loadingSkater || loadingScores || loadingElements || loadingCatResults;

  // ── Progression chart mode ─────────────────────────────────────────────────
  const [progressionMode, setProgressionMode] = useState<"result" | "segments" | "tes" | "pcs">("result");
  const [pcsSegmentFilter, setPcsSegmentFilter] = useState<"sp" | "fs">("sp");

  // ── Derived: score progression (competition results) ───────────────────────
  // Use categoryResults as primary source; fall back to scores for competitions
  // where no category_result row exists (e.g. single-segment with missing row).
  const progressionDataResult = (() => {
    const map = new Map<string, { date: string; label: string; total: number | null }>();

    // Seed from categoryResults first
    for (const r of categoryResults ?? []) {
      if (r.combined_total == null) continue;
      const key = `${r.competition_id}__${r.category ?? ""}`;
      map.set(key, {
        date: r.competition_date ? r.competition_date.slice(0, 10) : (r.competition_name ?? "?"),
        label: `${r.competition_name ?? ""} · ${r.category ?? ""}`,
        total: r.combined_total,
      });
    }

    // Fill gaps from scores (single-segment competitions missing a category result)
    for (const s of scores ?? []) {
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

  // ── Derived: score progression (segments: SP and FS on separate series) ────
  const progressionDataSegments = (() => {
    // Group scores by competition+category, keyed by date label
    const map = new Map<string, { date: string; label: string; sp?: number; fs?: number }>();
    for (const s of (scores ?? []).filter((s) => s.total_score != null)) {
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

  // ── Derived: TES progression (SP and FS technical_score) ──────────────────
  const progressionDataTes = (() => {
    const map = new Map<string, { date: string; label: string; sp?: number; fs?: number }>();
    for (const s of (scores ?? []).filter((s) => s.technical_score != null)) {
      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!map.has(key)) {
        map.set(key, {
          date: s.competition_date ? s.competition_date.slice(0, 10) : (s.competition_name ?? "?"),
          label: `${s.competition_name ?? ""} · ${s.category ?? ""}`,
        });
      }
      const entry = map.get(key)!;
      const seg = s.segment?.toUpperCase();
      if (seg === "SP" || seg === "PH") entry.sp = s.technical_score ?? undefined;
      else if (seg === "FS" || seg === "FP" || seg === "LD") entry.fs = s.technical_score ?? undefined;
    }
    return [...map.values()].sort((a, b) => (a.date > b.date ? 1 : -1));
  })();

  // ── Derived: PCS progression (per-component, filtered by segment) ───────
  const PCS_COLORS = ["#2e6385", "#7cb9e8", "#e57373", "#81c784", "#ffb74d", "#ba68c8", "#4dd0e1", "#f06292"];

  const pcsComponentNames = (() => {
    const nameSet = new Set<string>();
    for (const s of scores ?? []) {
      if (!s.components) continue;
      const seg = s.segment?.toUpperCase();
      const matchesSp = seg === "SP" || seg === "PH";
      const matchesFs = seg === "FS" || seg === "FP" || seg === "LD";
      if ((pcsSegmentFilter === "sp" && matchesSp) || (pcsSegmentFilter === "fs" && matchesFs)) {
        for (const name of Object.keys(s.components)) nameSet.add(name);
      }
    }
    return [...nameSet].sort();
  })();

  const progressionDataPcs = (() => {
    const map = new Map<string, { date: string; label: string; [comp: string]: string | number | undefined }>();
    for (const s of scores ?? []) {
      if (!s.components) continue;
      const seg = s.segment?.toUpperCase();
      const matchesSp = seg === "SP" || seg === "PH";
      const matchesFs = seg === "FS" || seg === "FP" || seg === "LD";
      if ((pcsSegmentFilter === "sp" && !matchesSp) || (pcsSegmentFilter === "fs" && !matchesFs)) continue;

      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!map.has(key)) {
        map.set(key, {
          date: s.competition_date ? s.competition_date.slice(0, 10) : (s.competition_name ?? "?"),
          label: `${s.competition_name ?? ""} · ${s.category ?? ""}`,
        });
      }
      const entry = map.get(key)!;
      for (const [name, value] of Object.entries(s.components)) {
        entry[name] = value;
      }
    }
    return [...map.values()].sort((a, b) => (String(a.date) > String(b.date) ? 1 : -1));
  })();

  // ── Derived: sorted competition history ────────────────────────────────────
  const sortedScores: Score[] = [...(scores ?? [])].sort((a, b) => {
    if (a.competition_date && b.competition_date)
      return a.competition_date > b.competition_date ? -1 : 1;
    return 0;
  });

  // ── Derived: competition history rows (group by competition+category) ────
  interface HistoryRow {
    key: string;
    competitionId: number;
    competitionName: string | null;
    competitionDate: string | null;
    category: string | null;
    catResult: CategoryResult | null;
    segmentScores: Score[];
  }

  const historyRows: HistoryRow[] = (() => {
    const map = new Map<string, HistoryRow>();
    for (const s of sortedScores) {
      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!map.has(key)) {
        const cr = (categoryResults ?? []).find(
          (r) => r.competition_id === s.competition_id && r.category === s.category
        ) ?? null;
        map.set(key, {
          key,
          competitionId: s.competition_id,
          competitionName: s.competition_name,
          competitionDate: s.competition_date,
          category: s.category,
          catResult: cr,
          segmentScores: [],
        });
      }
      map.get(key)!.segmentScores.push(s);
    }
    return [...map.values()].sort((a, b) => {
      if (a.competitionDate && b.competitionDate)
        return a.competitionDate > b.competitionDate ? -1 : 1;
      return 0;
    });
  })();

  // ── Derived: best TSS (max across category results + scores without a result) ──
  const bestTss = (() => {
    const catKeys = new Set<string>();
    let best: number | null = null;

    for (const r of categoryResults ?? []) {
      if (r.combined_total == null) continue;
      catKeys.add(`${r.competition_id}__${r.category ?? ""}`);
      if (best == null || r.combined_total > best) best = r.combined_total;
    }

    // Also consider scores from competitions missing a category result
    for (const s of scores ?? []) {
      if (s.total_score == null) continue;
      const key = `${s.competition_id}__${s.category ?? ""}`;
      if (!catKeys.has(key)) {
        if (best == null || s.total_score > best) best = s.total_score;
      }
    }

    return best;
  })();

  // ── Derived: element KPIs ──────────────────────────────────────────────────
  const hasElements = elements && elements.length > 0;

  const jumpPrecision = (() => {
    if (!elements?.length) return null;
    const jumps = elements.filter((el) => isJumpElement(el.element_name));
    if (!jumps.length) return null;
    const positive = jumps.filter((el) => (el.goe ?? 0) > 0).length;
    return (positive / jumps.length) * 100;
  })();

  const spinStats = (() => {
    if (!elements?.length) return null;
    const spins = elements.filter((el) => isSpinElement(el.element_name));
    if (!spins.length) return null;
    const levels = spins.map((el) => elementLevel(el.element_name));
    const goeVals = spins.map((el) => el.goe).filter((g): g is number => g != null);
    return {
      avgLevel: avg(levels),
      avgGoe: avg(goeVals),
    };
  })();

  const stepStats = (() => {
    if (!elements?.length) return null;
    const steps = elements.filter((el) => isStepElement(el.element_name));
    if (!steps.length) return null;
    const levels = steps.map((el) => elementLevel(el.element_name));
    const goeVals = steps.map((el) => el.goe).filter((g): g is number => g != null);
    return {
      avgLevel: avg(levels),
      avgGoe: avg(goeVals),
    };
  })();

  // ── Selected score for element detail panel ────────────────────────────────
  const [selectedScoreId, setSelectedScoreId] = useState<number | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // ── Score card modal ───────────────────────────────────────────────────────
  const [modalScore, setModalScore] = useState<Score | null>(null);

  function toggleCollapsed(key: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }
  const activeScoreId = selectedScoreId ?? sortedScores[0]?.id ?? null;
  const activeScore = sortedScores.find((s) => s.id === activeScoreId) ?? null;
  const activeScoreElements = (elements ?? []).filter(
    (el) => activeScore && el.score_id === activeScore.id
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
      {/* Score card modal */}
      {modalScore && (
        <ScoreCardModal
          score={modalScore}
          skaterName={skater ? `${skater.first_name} ${skater.last_name}` : ""}
          onClose={() => setModalScore(null)}
        />
      )}

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
        <div className="bg-gradient-to-r from-primary to-on-primary-fixed-variant py-6 px-4 sm:py-8 sm:px-8 flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-6">
          <div className="flex items-center gap-4 w-full min-w-0 sm:flex-1">
            <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center text-2xl font-extrabold font-headline text-white ring-2 ring-white/30 shrink-0">
              {skater?.last_name?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0 overflow-hidden">
              <h1 className="text-2xl sm:text-3xl font-extrabold font-headline text-white leading-tight truncate">
                {skater ? `${skater.first_name} ${skater.last_name}` : "—"}
              </h1>
              <p className="text-sm text-white/70 mt-1 truncate">
                {[
                  skater?.club,
                  skater?.nationality ? `${countryFlag(skater.nationality) ?? ""} ${skater.nationality}` : null,
                ].filter(Boolean).join(" · ")}
                {skater?.birth_year ? ` · ${skater.birth_year}` : ""}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3 shrink-0 items-center">
            {seasons && seasons.length > 0 && (
              <select
                value={selectedSeason ?? ""}
                onChange={(e) => setSelectedSeason(e.target.value || null)}
                className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2.5 text-sm text-white font-bold font-headline appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-white/30"
              >
                <option value="" className="text-on-surface bg-surface">Toutes les saisons</option>
                {seasons.map((s) => (
                  <option key={s} value={s} className="text-on-surface bg-surface">{s}</option>
                ))}
              </select>
            )}
            {selectedSeason && (
              <button
                onClick={() => downloadPdf(`/reports/skater/${skaterId}/pdf?season=${selectedSeason}`).catch((e) => alert(`Erreur : ${e.message}`))}
                className="flex items-center gap-1.5 bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2.5 text-sm text-white font-bold font-headline hover:bg-white/25 transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
                Exporter le bilan
              </button>
            )}
            <HeroStatBox
              label="Meilleur score"
              value={bestTss != null ? bestTss.toFixed(2) : "—"}
            />
            <HeroStatBox
              label="Compétitions"
              value={String(historyRows.length)}
            />
          </div>
        </div>
      )}

      {/* Tab bar for skater role */}
      {user?.role === "skater" && (
        <div className="px-6 pt-4">
          <div className="flex gap-1 bg-surface-container rounded-xl p-1 max-w-md">
            <button
              onClick={() => setAnalyticsTab("training")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                analyticsTab === "training"
                  ? "bg-white text-primary shadow-sm"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <span className="material-symbols-outlined text-lg">fitness_center</span>
              Entraînement
            </button>
            <button
              onClick={() => setAnalyticsTab("competitions")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
                analyticsTab === "competitions"
                  ? "bg-white text-primary shadow-sm"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <span className="material-symbols-outlined text-lg">emoji_events</span>
              Compétitions
            </button>
          </div>
        </div>
      )}

      {/* ── Main content ── */}
      {(analyticsTab === "competitions" || user?.role !== "skater") && (
        <>
          <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ────────── LEFT PANEL ────────── */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Score progression chart */}
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <h2 className="text-base font-extrabold font-headline text-on-surface">
                Analyse longitudinale des scores
              </h2>
              <div className="flex items-center gap-2">
                {progressionMode === "pcs" && (
                  <div className="flex rounded-lg overflow-hidden border border-outline-variant text-xs font-bold">
                    <button
                      onClick={() => setPcsSegmentFilter("sp")}
                      className={`px-2.5 py-1 transition-colors ${
                        pcsSegmentFilter === "sp"
                          ? "bg-primary text-on-primary"
                          : "bg-surface text-on-surface-variant hover:bg-surface-container"
                      }`}
                    >
                      SP
                    </button>
                    <button
                      onClick={() => setPcsSegmentFilter("fs")}
                      className={`px-2.5 py-1 transition-colors ${
                        pcsSegmentFilter === "fs"
                          ? "bg-primary text-on-primary"
                          : "bg-surface text-on-surface-variant hover:bg-surface-container"
                      }`}
                    >
                      FS
                    </button>
                  </div>
                )}
                <select
                  value={progressionMode}
                  onChange={(e) => setProgressionMode(e.target.value as typeof progressionMode)}
                  className="bg-surface-container-high rounded-lg px-3 py-1.5 text-xs font-bold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
                >
                  <option value="result">Résultat</option>
                  <option value="segments">Segments</option>
                  <option value="tes">TES</option>
                  <option value="pcs">PCS</option>
                </select>
              </div>
            </div>
            {isLoading ? (
              <Skeleton className="h-[260px] w-full" />
            ) : progressionMode === "result" && progressionDataResult.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
                Aucune donnée de résultat disponible
              </div>
            ) : progressionMode === "segments" && progressionDataSegments.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
                Aucune donnée de segment disponible
              </div>
            ) : progressionMode === "tes" && progressionDataTes.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
                Aucune donnée TES disponible
              </div>
            ) : progressionMode === "pcs" && progressionDataPcs.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] text-on-surface-variant text-sm">
                Aucune donnée PCS disponible
              </div>
            ) : progressionMode === "result" ? (
              <ResponsiveContainer width="100%" height={260}>
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
              </ResponsiveContainer>
            ) : progressionMode === "pcs" ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={progressionDataPcs} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
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
                  {pcsComponentNames.map((name, i) => (
                    <Line
                      key={name}
                      type="monotone"
                      dataKey={name}
                      name={name}
                      stroke={PCS_COLORS[i % PCS_COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 3, fill: PCS_COLORS[i % PCS_COLORS.length], stroke: "#fff", strokeWidth: 1.5 }}
                      activeDot={{ r: 5 }}
                      connectNulls={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              /* segments + tes share the same dual-line layout */
              <ResponsiveContainer width="100%" height={260}>
                <LineChart
                  data={progressionMode === "tes" ? progressionDataTes : progressionDataSegments}
                  margin={{ top: 4, right: 8, left: -16, bottom: 4 }}
                >
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
            ) : historyRows.length === 0 ? (
              <p className="text-on-surface-variant text-sm">
                Aucune compétition enregistrée.
              </p>
            ) : (
              <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                <table className="w-full min-w-[560px] border-collapse">
                  <thead className="sticky top-0 z-10">
                    <tr className="bg-surface-container-low">
                      {["", "Compétition", "Catégorie", "Rang", "Total", "TES", "PCS", "Date"].map(
                        (col, i) => (
                          <th
                            key={col || `col-${i}`}
                            className={`text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 ${
                              i <= 1 ? "text-left" : "text-right"
                            } ${i === 0 ? "rounded-tl-xl" : ""} ${i === 7 ? "rounded-tr-xl" : ""}`}
                          >
                            {col}
                          </th>
                        )
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {historyRows.map((row, rowIdx) => {
                      const isMultiSegment = row.catResult != null && row.catResult.segment_count > 1;
                      const isCollapsed = !expandedRows.has(row.key);

                      return (
                        <React.Fragment key={row.key}>
                          {/* Overall result row for multi-segment */}
                          {isMultiSegment && row.catResult ? (
                            <tr
                              className={
                                (rowIdx % 2 === 0
                                  ? "bg-surface-container-lowest"
                                  : "bg-surface-container-low/30") +
                                " cursor-pointer select-none hover:bg-surface-container-low/60 transition-colors"
                              }
                              onClick={() => toggleCollapsed(row.key)}
                            >
                              {/* col 0: button (empty for overall row) */}
                              <td className="px-3 py-2" />
                              {/* col 1: competition name */}
                              <td className="px-3 py-2 text-sm text-on-surface">
                                <div className="flex items-center gap-1.5">
                                  <span className="material-symbols-outlined text-sm text-on-surface-variant leading-none">
                                    {isCollapsed ? "chevron_right" : "expand_more"}
                                  </span>
                                  {user?.role === "skater" ? (
                                    <span className="font-medium text-on-surface">
                                      {row.competitionName ?? `#${row.competitionId}`}
                                    </span>
                                  ) : (
                                    <Link
                                      to={`/competitions/${row.competitionId}`}
                                      className="text-primary hover:underline font-medium"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      {row.competitionName ?? `#${row.competitionId}`}
                                    </Link>
                                  )}
                                </div>
                              </td>
                              {/* col 2: category */}
                              <td className="px-3 py-2 text-right text-sm text-on-surface-variant whitespace-nowrap">
                                {row.category ?? "—"}
                              </td>
                              {/* col 3: rank */}
                              <td className="px-3 py-2 text-right">
                                {row.catResult.overall_rank != null ? (
                                  row.catResult.overall_rank <= 3 ? (
                                    <span className="bg-tertiary-container/30 text-on-tertiary-container text-xs font-bold px-2 py-1 rounded-full">
                                      {row.catResult.overall_rank}
                                    </span>
                                  ) : (
                                    <span className="font-mono text-sm text-on-surface">
                                      {row.catResult.overall_rank}
                                    </span>
                                  )
                                ) : (
                                  <span className="text-on-surface-variant text-sm">—</span>
                                )}
                              </td>
                              {/* col 4: total */}
                              <td className="px-3 py-2 text-right font-mono text-sm font-bold text-on-surface">
                                {row.catResult.combined_total?.toFixed(2) ?? "—"}
                              </td>
                              {/* col 5: TES (n/a for overall) */}
                              <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">—</td>
                              {/* col 6: PCS (n/a for overall) */}
                              <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant">—</td>
                              {/* col 7: date */}
                              <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant whitespace-nowrap">
                                {row.competitionDate ? row.competitionDate.slice(0, 10) : "—"}
                              </td>
                            </tr>
                          ) : null}

                          {/* Individual segment rows */}
                          {(!isMultiSegment || !isCollapsed) && row.segmentScores.map((s) => (
                            <tr
                              key={s.id}
                              className={
                                rowIdx % 2 === 0
                                  ? "bg-surface-container-lowest"
                                  : "bg-surface-container-low/30"
                              }
                            >
                              {/* col 0: score card button */}
                              <td className="px-3 py-2 text-left">
                                {s.elements && s.elements.length > 0 && (
                                  <button
                                    onClick={() => setModalScore(s)}
                                    className="inline-flex items-center gap-0.5 text-primary hover:text-primary/80 transition-colors text-[10px] font-bold uppercase tracking-wider"
                                    title="Voir le détail"
                                  >
                                    <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                                  </button>
                                )}
                              </td>
                              {isMultiSegment ? (
                                <>
                                  {/* col 1: segment label */}
                                  <td className="px-3 py-2 text-sm text-on-surface-variant pl-6">
                                    <span className="text-xs text-on-surface-variant/60">
                                      {s.segment}
                                    </span>
                                  </td>
                                  {/* col 2: category (empty) */}
                                  <td className="px-3 py-2" />
                                </>
                              ) : (
                                <>
                                  {/* col 1: competition name */}
                                  <td className="px-3 py-2 text-sm text-on-surface">
                                    {user?.role === "skater" ? (
                                      <span className="font-medium text-on-surface">
                                        {s.competition_name ?? `#${s.competition_id}`}
                                      </span>
                                    ) : (
                                      <Link
                                        to={`/competitions/${s.competition_id}`}
                                        className="text-primary hover:underline font-medium"
                                      >
                                        {s.competition_name ?? `#${s.competition_id}`}
                                      </Link>
                                    )}
                                  </td>
                                  {/* col 2: category */}
                                  <td className="px-3 py-2 text-right text-sm text-on-surface-variant whitespace-nowrap">
                                    {s.category ?? "—"}
                                  </td>
                                </>
                              )}
                              {/* col 3: rank */}
                              <td className="px-3 py-2 text-right">
                                {s.rank != null ? (
                                  !isMultiSegment && s.rank <= 3 ? (
                                    <span className="bg-tertiary-container/30 text-on-tertiary-container text-xs font-bold px-2 py-1 rounded-full">
                                      {s.rank}
                                    </span>
                                  ) : (
                                    <span className="font-mono text-sm text-on-surface-variant">
                                      {s.rank}
                                    </span>
                                  )
                                ) : (
                                  <span className="text-on-surface-variant text-sm">—</span>
                                )}
                              </td>
                              {/* col 4: total */}
                              <td className="px-3 py-2 text-right font-mono text-sm font-bold text-on-surface">
                                {s.total_score?.toFixed(2) ?? "—"}
                              </td>
                              {/* col 5: TES */}
                              <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                                {s.technical_score?.toFixed(2) ?? "—"}
                              </td>
                              {/* col 6: PCS */}
                              <td className="px-3 py-2 text-right font-mono text-sm text-on-surface">
                                {s.component_score?.toFixed(2) ?? "—"}
                              </td>
                              {/* col 7: date */}
                              {isMultiSegment ? (
                                <td className="px-3 py-2" />
                              ) : (
                                <td className="px-3 py-2 text-right font-mono text-sm text-on-surface-variant whitespace-nowrap">
                                  {s.competition_date ? s.competition_date.slice(0, 10) : "—"}
                                </td>
                              )}
                            </tr>
                          ))}
                        </React.Fragment>
                      );
                    })}
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
                  info="Pourcentage de sauts ayant reçu un GOE strictement positif, sur l'ensemble des compétitions."
                />
              )}
              {spinStats && (
                <DualMetricCard
                  label="Pirouettes"
                  leftLabel="Niveau moyen"
                  leftValue={spinStats.avgLevel?.toFixed(2) ?? "—"}
                  rightLabel="GOE moyen"
                  rightValue={
                    spinStats.avgGoe != null
                      ? `${spinStats.avgGoe >= 0 ? "+" : ""}${spinStats.avgGoe.toFixed(2)}`
                      : "—"
                  }
                  info="Niveau moyen des pirouettes (B = 0.5, sans niveau = 0) et GOE moyen, sur l'ensemble des compétitions."
                />
              )}
              {stepStats && (
                <DualMetricCard
                  label="Pas et séquences"
                  leftLabel="Niveau moyen"
                  leftValue={stepStats.avgLevel?.toFixed(2) ?? "—"}
                  rightLabel="GOE moyen"
                  rightValue={
                    stepStats.avgGoe != null
                      ? `${stepStats.avgGoe >= 0 ? "+" : ""}${stepStats.avgGoe.toFixed(2)}`
                      : "—"
                  }
                  info="Niveau moyen des pas et séquences chorégraphiques (B = 0.5, sans niveau = 0) et GOE moyen."
                />
              )}
            </>
          ) : (
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

        {/* Element detail panel */}
        <div className="lg:col-span-1 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <h2 className="text-base font-extrabold font-headline text-on-surface mb-3">
            Détail des éléments
          </h2>
          {sortedScores.length > 0 && (
            <select
              className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary w-full mb-4"
              value={activeScoreId ?? ""}
              onChange={(e) =>
                setSelectedScoreId(e.target.value ? Number(e.target.value) : null)
              }
            >
              {sortedScores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.competition_name ?? "?"} · {s.segment}
                </option>
              ))}
            </select>
          )}
          {isLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : (
            <JudgePanel elements={activeScoreElements} />
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
        </>
      )}

      {/* ── Training content ── */}
      {analyticsTab === "training" && user?.role === "skater" && (
        <div className="p-6 space-y-6">
          {/* Evolution chart */}
          <TrainingEvolutionChart
            reviews={trainingReviews ?? []}
            incidents={trainingIncidents ?? []}
          />

          {/* Timeline */}
          <div className="space-y-3">
            <h4 className="font-headline font-bold text-on-surface text-sm">Historique</h4>
            {(timeline ?? []).length === 0 ? (
              <p className="text-sm text-on-surface-variant text-center py-10">Aucune donnée d'entraînement disponible</p>
            ) : (
              timeline?.map((entry) => {
                if (entry.type === "review") {
                  const r = entry as WeeklyReview & { type: "review" };
                  return (
                    <div key={`review-${r.id}`} className="bg-surface-container-low rounded-2xl p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="font-headline font-bold text-on-surface text-sm">
                          Semaine du {new Date(r.week_start).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
                        </h4>
                        <span className="font-mono text-xs text-on-surface-variant">{r.attendance}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-4">
                        {(["engagement", "progression", "attitude"] as const).map((field) => (
                          <div key={field}>
                            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1 capitalize">{field}</p>
                            <div className="flex gap-0.5">
                              {Array.from({ length: 5 }, (_, i) => (
                                <div key={i} className={`w-2.5 h-2.5 rounded-full ${i < r[field] ? "bg-primary" : "bg-surface-container"}`} />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                      {r.strengths && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Points forts</p>
                          <p className="text-sm text-on-surface">{r.strengths}</p>
                        </div>
                      )}
                      {r.improvements && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Axes d'amélioration</p>
                          <p className="text-sm text-on-surface">{r.improvements}</p>
                        </div>
                      )}
                    </div>
                  );
                } else {
                  const i = entry as TrainingIncident & { type: "incident" };
                  const typeMap: Record<string, { label: string; color: string; icon: string }> = {
                    injury: { label: "Blessure", color: "text-error", icon: "healing" },
                    behavior: { label: "Comportement", color: "text-orange-600", icon: "report" },
                    other: { label: "Autre", color: "text-on-surface-variant", icon: "info" },
                  };
                  const meta = typeMap[i.incident_type] ?? typeMap.other;
                  return (
                    <div key={`incident-${i.id}`} className="bg-surface-container-low rounded-2xl p-5 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`material-symbols-outlined text-lg ${meta.color}`}>{meta.icon}</span>
                          <span className={`text-sm font-bold ${meta.color}`}>{meta.label}</span>
                        </div>
                        <span className="text-xs text-on-surface-variant">
                          {new Date(i.date).toLocaleDateString("fr-FR")}
                        </span>
                      </div>
                      <p className="text-sm text-on-surface">{i.description}</p>
                    </div>
                  );
                }
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
