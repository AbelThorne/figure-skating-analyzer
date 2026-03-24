import { useEffect } from "react";
import { Score } from "../api/client";

interface Props {
  score: Score;
  skaterName: string;
  onClose: () => void;
}

// ISU marker display config
const MARKER_STYLE: Record<string, { color: string; label: string }> = {
  "*":  { color: "text-[#ba1a1a]", label: "Annulé" },
  "<<": { color: "text-[#ba1a1a]", label: "Déclassé" },
  "<":  { color: "text-[#e65100]", label: "Sous-rotation" },
  "q":  { color: "text-[#e65100]", label: "Quart court" },
  "e":  { color: "text-[#e65100]", label: "Carre incorrecte" },
  "!":  { color: "text-[#b45309]", label: "Carre incertaine" },
  "x":  { color: "text-primary",   label: "Bonus 2e moitié" },
  "F":  { color: "text-[#ba1a1a]", label: "Chute" },
};

const COMPONENT_LABELS: Record<string, string> = {
  CO: "Composition",
  PR: "Présentation",
  SK: "Habiletés de patinage",
  IN: "Interprétation",
  TR: "Transitions",
  PE: "Performance",
  CH: "Chorégraphie",
};

const SEGMENT_LABELS: Record<string, string> = {
  SP: "Programme Court",
  PH: "Programme Court",
  FS: "Programme Libre",
  FP: "Programme Libre",
  LD: "Danse Originale",
};

// Render a single element part with its positional marker
function ElementPartWithMarker({ part, marker }: { part: string; marker?: string }) {
  if (!marker || marker === "+") {
    return <span>{part}</span>;
  }
  const style = MARKER_STYLE[marker] ?? { color: "text-on-surface-variant", label: marker };
  return (
    <span>
      {part}
      <span className={`font-mono text-[9px] font-bold ${style.color} align-super ml-[1px]`} title={style.label}>
        {marker}
      </span>
    </span>
  );
}

// Render a full element name with positional markers
function ElementNameCell({ name, markers }: { name: string; markers: string[] }) {
  const parts = name.split("+");
  const isPositional = markers.some((m) => m === "+");

  if (markers.length === 0) {
    return <span>{name}</span>;
  }

  if (parts.length > 1 && isPositional) {
    return (
      <span>
        {parts.map((part, i) => (
          <span key={i}>
            {i > 0 && <span className="text-on-surface-variant">+</span>}
            <ElementPartWithMarker part={part} marker={markers[i]} />
          </span>
        ))}
      </span>
    );
  }

  // Flat markers on non-combo
  return (
    <span>
      {name}
      {markers.filter((m) => m !== "+").map((m, i) => {
        const style = MARKER_STYLE[m] ?? { color: "text-on-surface-variant", label: m };
        return (
          <span key={i} className={`font-mono text-[9px] font-bold ${style.color} align-super ml-[1px]`} title={style.label}>
            {m}
          </span>
        );
      })}
    </span>
  );
}

function goeColor(v: number) {
  if (v > 0) return "text-primary";
  if (v < 0) return "text-[#ba1a1a]";
  return "text-on-surface-variant";
}

function fmt(v: number | null | undefined, sign = false) {
  if (v == null) return "—";
  return (sign && v > 0 ? "+" : "") + v.toFixed(2);
}

export default function ScoreCardModal({ score, skaterName, onClose }: Props) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Lock body scroll while open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  const elements = score.elements ?? [];
  const components = score.components ?? {};
  const judgeCount = elements[0]?.judge_goe?.length ?? 0;
  const segmentLabel = SEGMENT_LABELS[score.segment?.toUpperCase()] ?? score.segment;
  const totalBase = elements.reduce((sum, el) => sum + (el.base_value ?? 0), 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-primary to-on-primary-fixed-variant rounded-t-2xl px-4 sm:px-6 py-5 flex items-start justify-between gap-3 shrink-0">
          <div className="min-w-0 flex-1">
            <p className="text-white/70 text-xs font-bold uppercase tracking-widest mb-0.5 truncate">
              {score.competition_name ?? "—"}
              {score.competition_date ? ` · ${score.competition_date.slice(0, 10)}` : ""}
            </p>
            <h2 className="text-lg sm:text-xl font-extrabold font-headline text-white leading-tight">
              {skaterName}
            </h2>
            <p className="text-white/80 text-sm mt-0.5">
              {segmentLabel}
              {score.category ? ` · ${score.category}` : ""}
              {score.rank != null ? ` · Rang ${score.rank}` : ""}
            </p>
          </div>
          {/* Score summary — hidden on small screens (visible in breakdown table below) */}
          <div className="hidden sm:flex gap-3 shrink-0">
            {[
              { label: "TES", value: fmt(score.technical_score) },
              { label: "PCS", value: fmt(score.component_score) },
              { label: "Total", value: fmt(score.total_score) },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2 text-center min-w-[64px]">
                <p className="text-lg font-extrabold font-headline text-white font-mono leading-none">{value}</p>
                <p className="text-[9px] uppercase tracking-widest text-white/70 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 text-white/70 hover:text-white transition-colors mt-0.5"
            aria-label="Fermer"
          >
            <span className="material-symbols-outlined text-2xl">close</span>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 p-6 flex flex-col gap-6">

          {/* Elements table */}
          {elements.length > 0 && (
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Éléments exécutés
              </h3>
              <div className="overflow-x-auto rounded-xl">
                <table className="w-full border-collapse text-xs font-mono">
                  <thead>
                    <tr className="bg-surface-container-low">
                      <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2 rounded-tl-xl">#</th>
                      <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Élément</th>
                      <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Base</th>
                      {judgeCount > 0 && Array.from({ length: judgeCount }, (_, i) => (
                        <th key={i} className="text-right font-black uppercase tracking-widest text-on-surface-variant px-2 py-2">
                          J{i + 1}
                        </th>
                      ))}
                      <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">GOE</th>
                      <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2 rounded-tr-xl">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {elements.map((el, i) => {
                      const isNullified = el.markers?.includes("*");
                      const rowBg = i % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30";
                      return (
                        <tr key={i} className={`${rowBg} ${isNullified ? "opacity-50" : ""}`}>
                          <td className="px-3 py-1.5 text-on-surface-variant">{el.number}</td>
                          <td className="px-3 py-1.5 text-on-surface font-medium">
                            <ElementNameCell name={el.name} markers={el.markers ?? []} />
                          </td>
                          <td className="px-3 py-1.5 text-right text-on-surface-variant">{fmt(el.base_value)}</td>
                          {(el.judge_goe ?? []).map((g, j) => (
                            <td key={j} className={`px-2 py-1.5 text-right ${goeColor(g)}`}>
                              {g > 0 ? `+${g}` : g}
                            </td>
                          ))}
                          {/* Pad missing judge columns */}
                          {Array.from({ length: judgeCount - (el.judge_goe?.length ?? 0) }, (_, j) => (
                            <td key={`pad-${j}`} className="px-2 py-1.5 text-right text-on-surface-variant">—</td>
                          ))}
                          <td className={`px-3 py-1.5 text-right font-bold ${goeColor(el.goe ?? 0)}`}>
                            {fmt(el.goe, true)}
                          </td>
                          <td className="px-3 py-1.5 text-right font-bold text-on-surface">{fmt(el.score)}</td>
                        </tr>
                      );
                    })}
                    {/* Total row */}
                    <tr className="bg-surface-container-low border-t border-outline-variant/30">
                      <td colSpan={2} className="px-3 py-2 font-black uppercase tracking-widest text-on-surface-variant text-[10px]">Total TES</td>
                      <td className="px-3 py-2 text-right font-bold text-on-surface">{fmt(totalBase)}</td>
                      {judgeCount > 0 && <td colSpan={judgeCount} />}
                      <td className="px-3 py-2" />
                      <td className="px-3 py-2 text-right font-bold text-on-surface">{fmt(score.technical_score)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Components + deductions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* PCS */}
            {Object.keys(components).length > 0 && (
              <div>
                <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                  Composantes du programme
                </h3>
                <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
                  <table className="w-full border-collapse text-sm">
                    <tbody>
                      {Object.entries(components).map(([key, val], i) => (
                        <tr key={key} className={i % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"}>
                          <td className="px-4 py-2 text-on-surface-variant font-body">
                            {COMPONENT_LABELS[key] ?? key}
                            <span className="ml-2 text-[10px] font-mono text-on-surface-variant/60">{key}</span>
                          </td>
                          <td className="px-4 py-2 text-right font-mono font-bold text-on-surface">{fmt(val)}</td>
                        </tr>
                      ))}
                      <tr className="bg-surface-container-low border-t border-outline-variant/30">
                        <td className="px-4 py-2 font-black uppercase tracking-widest text-on-surface-variant text-[10px]">Total PCS</td>
                        <td className="px-4 py-2 text-right font-mono font-bold text-on-surface">{fmt(score.component_score)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Score breakdown */}
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
                Récapitulatif
              </h3>
              <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
                <table className="w-full border-collapse text-sm">
                  <tbody>
                    <tr className="bg-surface-container-lowest">
                      <td className="px-4 py-2 text-on-surface-variant font-body">Note technique</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-on-surface">{fmt(score.technical_score)}</td>
                    </tr>
                    <tr className="bg-surface-container-low/30">
                      <td className="px-4 py-2 text-on-surface-variant font-body">Composantes</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-on-surface">{fmt(score.component_score)}</td>
                    </tr>
                    {(score.deductions ?? 0) !== 0 && (
                      <tr className="bg-surface-container-lowest">
                        <td className="px-4 py-2 text-on-surface-variant font-body">Déductions</td>
                        <td className="px-4 py-2 text-right font-mono font-bold text-[#ba1a1a]">−{Math.abs(score.deductions ?? 0).toFixed(2)}</td>
                      </tr>
                    )}
                    <tr className="bg-surface-container-low border-t border-outline-variant/30">
                      <td className="px-4 py-2 font-black uppercase tracking-widest text-on-surface-variant text-[10px]">Total</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-on-surface text-base">{fmt(score.total_score)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Marker legend if any markers present */}
          {elements.some((el) => (el.markers ?? []).some((m) => m !== "+")) && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(MARKER_STYLE)
                .filter(([m]) => elements.some((el) => (el.markers ?? []).includes(m)))
                .map(([m, { color, label }]) => (
                  <span key={m} className={`inline-flex items-center gap-1 text-[10px] font-mono font-bold ${color}`}>
                    <span>{m}</span>
                    <span className="font-body font-normal text-on-surface-variant">= {label}</span>
                  </span>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
