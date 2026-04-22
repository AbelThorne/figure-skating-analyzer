import { useState, useEffect } from "react";
import type { ProgramRulesData } from "../../api/client";
import type { ProgramElement } from "../../utils/program-validator";
import { matchCategories, getBestMatch } from "../../utils/category-matcher";

interface Props {
  elements: ProgramElement[];
  rulesData: ProgramRulesData | undefined;
}

export default function CategoryPanel({ elements, rulesData }: Props) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const matches = rulesData && elements.length > 0
    ? matchCategories(elements, rulesData)
    : [];
  const best = getBestMatch(matches);

  // Default display: top 5 matches (sorted by violations then warnings)
  const displayed = showAll ? matches : matches.slice(0, 5);
  const hasMore = matches.length > 5;

  // The selected match for displaying validation details
  const selected = selectedKey
    ? matches.find(m => `${m.categoryName}-${m.segmentKey}` === selectedKey) ?? best
    : best;

  // Auto-select best when selection becomes invalid
  useEffect(() => {
    if (selectedKey && !matches.find(m => `${m.categoryName}-${m.segmentKey}` === selectedKey)) {
      setSelectedKey(null);
    }
  }, [matches, selectedKey]);

  if (!rulesData || elements.length === 0) {
    return (
      <div className="space-y-6">
        <SummarySection elements={elements} />
        <div className="text-sm text-on-surface-variant">
          Ajoutez des éléments pour voir la catégorie suggérée.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Category list */}
      <div>
        <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
          Catégories détectées
        </h3>
        <div className="space-y-1.5">
          {displayed.map(m => {
            const key = `${m.categoryName}-${m.segmentKey}`;
            const isSelected = selected && `${selected.categoryName}-${selected.segmentKey}` === key;
            const isPerfect = m.violations === 0 && m.warnings === 0;
            const isCompatible = m.violations === 0;

            return (
              <button
                key={key}
                onClick={() => setSelectedKey(key)}
                className={`w-full text-left px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                  isSelected
                    ? isPerfect
                      ? "bg-green-600/10 ring-2 ring-green-600/40"
                      : isCompatible
                        ? "bg-primary/10 ring-2 ring-primary/40"
                        : "bg-error/5 ring-2 ring-error/30"
                    : isPerfect
                      ? "bg-green-600/5 hover:bg-green-600/10"
                      : isCompatible
                        ? "bg-surface-container-low hover:bg-primary/5"
                        : "bg-surface-container-low hover:bg-error/5"
                }`}
              >
                <span className={`text-sm font-bold ${
                  isPerfect ? "text-green-700" : isCompatible ? "text-primary" : "text-on-surface"
                }`}>
                  {m.categoryLabel}
                </span>
                <span className="text-xs text-on-surface-variant ml-2">
                  — {m.segmentLabel}
                </span>
                {/* Violation and warning badges */}
                <span className="float-right flex items-center gap-2">
                  {m.violations > 0 && (
                    <span className="inline-flex items-center gap-0.5 text-error">
                      <span className="material-symbols-outlined text-sm">cancel</span>
                      <span className="text-xs font-bold">{m.violations}</span>
                    </span>
                  )}
                  {m.warnings > 0 && (
                    <span className="inline-flex items-center gap-0.5 text-orange-500">
                      <span className="material-symbols-outlined text-sm">warning</span>
                      <span className="text-xs font-bold">{m.warnings}</span>
                    </span>
                  )}
                  {isPerfect && (
                    <span className="inline-flex items-center gap-0.5 text-green-600">
                      <span className="material-symbols-outlined text-sm">check_circle</span>
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="mt-2 text-xs text-primary hover:text-primary/80 transition-colors cursor-pointer"
          >
            {showAll
              ? "Moins de catégories"
              : `Voir les ${matches.length - 5} autres catégories`}
          </button>
        )}
      </div>

      {/* Validation checklist for selected category */}
      {selected && (
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
            Validation — {selected.categoryLabel} ({selected.segmentLabel})
          </h3>
          <div className="space-y-1.5">
            {selected.results.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 mt-0.5">
                  {r.status === "ok" && (
                    <span className="material-symbols-outlined text-sm text-green-600">check_circle</span>
                  )}
                  {r.status === "warning" && (
                    <span className="material-symbols-outlined text-sm text-orange-500">warning</span>
                  )}
                  {r.status === "error" && (
                    <span className="material-symbols-outlined text-sm text-error">cancel</span>
                  )}
                </span>
                <div>
                  <span className="font-medium text-on-surface">{r.label}</span>
                  <span className="text-on-surface-variant ml-1.5">{r.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      <SummarySection elements={elements} />
    </div>
  );
}

function SummarySection({ elements }: { elements: ProgramElement[] }) {
  const jumps = elements.filter(e => e.type === "jump");
  const spins = elements.filter(e => e.type === "spin" || e.type === "pair_spin");
  const steps = elements.filter(e => e.type === "step");
  const choreo = elements.filter(e => e.type === "choreo");
  const combos = elements.filter(e => e.comboJumps && e.comboJumps.length > 1);
  const secondHalf = elements.filter(e => e.markers.includes("x"));

  return (
    <div>
      <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
        Résumé
      </h3>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <CountRow label="Sauts" count={jumps.length} />
        <CountRow label="Pirouettes" count={spins.length} />
        <CountRow label="Pas" count={steps.length} />
        <CountRow label="Chorégraphique" count={choreo.length} />
        <CountRow label="Combinaisons" count={combos.length} />
        <CountRow label="2e moitié (x)" count={secondHalf.length} />
      </div>
    </div>
  );
}

function CountRow({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex justify-between py-0.5">
      <span className="text-on-surface-variant">{label}</span>
      <span className="font-mono font-bold text-on-surface">{count}</span>
    </div>
  );
}
