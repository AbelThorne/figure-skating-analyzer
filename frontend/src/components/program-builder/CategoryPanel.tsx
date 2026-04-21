import type { ProgramRulesData } from "../../api/client";
import type { ProgramElement } from "../../utils/program-validator";
import type { CategoryMatch } from "../../utils/category-matcher";
import { matchCategories, getCompatibleCategories, getBestMatch } from "../../utils/category-matcher";

interface Props {
  elements: ProgramElement[];
  rulesData: ProgramRulesData | undefined;
}

export default function CategoryPanel({ elements, rulesData }: Props) {
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

  const matches = matchCategories(elements, rulesData);
  const compatible = getCompatibleCategories(matches);
  const best = getBestMatch(matches);

  return (
    <div className="space-y-6">
      {/* Category suggestion */}
      <div>
        <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
          Catégorie détectée
        </h3>
        {compatible.length > 0 ? (
          <div className="space-y-2">
            {compatible.map((m, i) => (
              <div
                key={`${m.categoryName}-${m.segmentKey}`}
                className={`px-3 py-2 rounded-lg ${
                  i === 0
                    ? "bg-primary/10 border border-primary/20"
                    : "bg-surface-container-low"
                }`}
              >
                <span className={`text-sm font-bold ${i === 0 ? "text-primary" : "text-on-surface"}`}>
                  {m.categoryLabel}
                </span>
                <span className="text-xs text-on-surface-variant ml-2">
                  — {m.segmentLabel}
                </span>
              </div>
            ))}
          </div>
        ) : best ? (
          <div className="px-3 py-2 rounded-lg bg-error/5 border border-error/20">
            <span className="text-sm font-bold text-on-surface">
              {best.categoryLabel}
            </span>
            <span className="text-xs text-on-surface-variant ml-2">
              — {best.segmentLabel}
            </span>
            <span className="text-xs text-error ml-2">
              ({best.violations} violation{best.violations > 1 ? "s" : ""})
            </span>
          </div>
        ) : null}
      </div>

      {/* Validation checklist */}
      {best && (
        <div>
          <h3 className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
            Validation — {best.categoryLabel} ({best.segmentLabel})
          </h3>
          <div className="space-y-1.5">
            {best.results.map((r, i) => (
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
