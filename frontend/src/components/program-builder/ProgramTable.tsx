import { useState, useRef, useEffect } from "react";
import type { SovData } from "../../api/client";
import type { ProgramElement } from "../../utils/program-validator";
import ModifierDropdown from "./ModifierDropdown";
import GoeTooltip from "./GoeTooltip";
import ElementPicker from "./ElementPicker";

// Marker styles matching ScoreCardModal exactly
const MARKER_STYLE: Record<string, { color: string; label: string }> = {
  "*":    { color: "text-[#ba1a1a]", label: "Annulé" },
  "<<":   { color: "text-[#ba1a1a]", label: "Déclassé" },
  "<":    { color: "text-[#e65100]", label: "Sous-rotation" },
  "q":    { color: "text-[#e65100]", label: "Quart court" },
  "e":    { color: "text-[#e65100]", label: "Carre incorrecte" },
  "!":    { color: "text-[#b45309]", label: "Carre incertaine" },
  "x":    { color: "text-primary",   label: "Bonus 2e moitié" },
  "+REP": { color: "text-primary",   label: "Répétition" },
  "V":    { color: "text-[#e65100]", label: "Valeur réduite" },
};

/** Render markers as superscripts matching ScoreCardModal style. */
function MarkerSuperscripts({ markers }: { markers: string[] }) {
  const display = markers.filter(m => !["x", "+REP"].includes(m));
  if (display.length === 0) return null;
  return (
    <>
      {display.map((m, i) => {
        const style = MARKER_STYLE[m] ?? { color: "text-on-surface-variant", label: m };
        return (
          <span
            key={i}
            className={`font-mono text-[9px] font-bold ${style.color} align-super ml-[1px]`}
            title={style.label}
          >
            {m}
          </span>
        );
      })}
    </>
  );
}

/** Render element name with markers, handling combos with per-jump markers. */
function ElementDisplay({ element }: { element: ProgramElement }) {
  if (element.comboJumps && element.comboJumps.length > 1) {
    return (
      <span className="font-mono font-semibold">
        {element.comboJumps.map((jump, i) => (
          <span key={i}>
            {i > 0 && <span className="text-on-surface-variant">+</span>}
            <span>{jump.code}</span>
            <MarkerSuperscripts markers={jump.markers} />
          </span>
        ))}
        {/* Show combo-level markers (x, +REP) at end */}
        <MarkerSuperscripts markers={element.markers.filter(m => ["x", "+REP"].includes(m))} />
      </span>
    );
  }

  return (
    <span className="font-mono font-semibold">
      {element.baseCode}
      <MarkerSuperscripts markers={element.markers} />
    </span>
  );
}

interface Props {
  sov: SovData;
  elements: ProgramElement[];
  includePairs: boolean;
  onUpdateMarkers: (elementId: string, markers: string[]) => void;
  onUpdateComboJumpMarkers: (elementId: string, jumpIndex: number, markers: string[]) => void;
  onAddComboJump: (elementId: string, jumpCode: string) => void;
  onReplaceElement: (elementId: string, newCode: string) => void;
  onDeleteElement: (elementId: string) => void;
}

export default function ProgramTable({
  sov,
  elements,
  includePairs,
  onUpdateMarkers,
  onUpdateComboJumpMarkers,
  onAddComboJump,
  onReplaceElement,
  onDeleteElement,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click or Escape
  useEffect(() => {
    if (!editingId) return;

    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setEditingId(null);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setEditingId(null);
    }

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [editingId]);

  // Totals
  const totalBV = elements.reduce((s, e) => s + e.bv, 0);
  const totalMin = elements.reduce((s, e) => s + e.min, 0);
  const totalMax = elements.reduce((s, e) => s + e.max, 0);

  return (
    <div className="overflow-x-auto rounded-xl">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="bg-surface-container-low">
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2 rounded-tl-xl w-8">#</th>
            <th className="w-8 px-1 py-2"></th>
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Élément</th>
            <th className="text-left font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Mod.</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">BV</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Min</th>
            <th className="text-right font-black uppercase tracking-widest text-on-surface-variant px-3 py-2">Max</th>
            <th className="w-10 px-1 py-2 rounded-tr-xl"></th>
          </tr>
        </thead>
        <tbody>
          {elements.map((el, i) => {
            const isCombo = el.comboJumps && el.comboJumps.length > 1;
            const canAddCombo = el.type === "jump" && (!el.comboJumps || el.comboJumps.length < 3);
            const rowBg = i % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30";

            return (
              <tr key={el.id} className={rowBg}>
                <td className="px-3 py-2 text-on-surface-variant">{i + 1}</td>

                {/* Combo add button */}
                <td className="px-1 py-2 text-center">
                  {canAddCombo && (
                    <AddComboButton
                      sov={sov}
                      includePairs={includePairs}
                      elementId={el.id}
                      currentJumps={el.comboJumps?.length ?? 1}
                      onAdd={onAddComboJump}
                    />
                  )}
                </td>

                {/* Element name — click to edit */}
                <td className="px-3 py-2 relative">
                  <button
                    onClick={() => setEditingId(editingId === el.id ? null : el.id)}
                    className="hover:bg-surface-container px-1 -mx-1 rounded transition-colors cursor-pointer"
                    title="Cliquer pour remplacer"
                  >
                    <ElementDisplay element={el} />
                  </button>

                  {/* Inline edit popover */}
                  {editingId === el.id && (
                    <div
                      ref={popoverRef}
                      className="absolute z-50 top-full left-0 mt-1 w-64 bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant/20 p-2"
                    >
                      <ElementPicker
                        sov={sov}
                        includePairs={includePairs}
                        onSelect={(code) => {
                          onReplaceElement(el.id, code);
                          setEditingId(null);
                        }}
                        placeholder="Remplacer par..."
                      />
                    </div>
                  )}
                </td>

                {/* Modifiers */}
                <td className="px-3 py-2">
                  {isCombo ? (
                    <div className="flex flex-col gap-1">
                      {el.comboJumps!.map((jump, ji) => (
                        <div key={ji} className="flex items-center gap-1">
                          <span className="text-[9px] text-on-surface-variant font-mono w-8 shrink-0">{jump.code}</span>
                          <ModifierDropdown
                            elementCode={jump.code}
                            elementType="jump"
                            activeMarkers={jump.markers}
                            onChange={(markers) => onUpdateComboJumpMarkers(el.id, ji, markers)}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <ModifierDropdown
                      elementCode={el.baseCode}
                      elementType={el.type}
                      activeMarkers={el.markers}
                      onChange={(markers) => onUpdateMarkers(el.id, markers)}
                    />
                  )}
                </td>

                {/* BV */}
                <td className="px-3 py-2 text-right font-mono font-bold text-on-surface">
                  {el.bv.toFixed(2)}
                </td>

                {/* Min with GOE tooltip */}
                <td className="px-3 py-2 text-right">
                  <GoeTooltip
                    sov={sov}
                    baseCode={el.baseCode}
                    markers={el.markers}
                    side="negative"
                    value={el.min}
                  >
                    <span className="font-mono text-[#ba1a1a] cursor-default">
                      {el.min.toFixed(2)}
                    </span>
                  </GoeTooltip>
                </td>

                {/* Max with GOE tooltip */}
                <td className="px-3 py-2 text-right">
                  <GoeTooltip
                    sov={sov}
                    baseCode={el.baseCode}
                    markers={el.markers}
                    side="positive"
                    value={el.max}
                  >
                    <span className="font-mono text-primary cursor-default">
                      {el.max.toFixed(2)}
                    </span>
                  </GoeTooltip>
                </td>

                {/* Delete */}
                <td className="px-1 py-2 text-center">
                  <button
                    onClick={() => onDeleteElement(el.id)}
                    className="text-on-surface-variant hover:text-error transition-colors p-0.5"
                    title="Supprimer"
                  >
                    <span className="material-symbols-outlined text-base">delete</span>
                  </button>
                </td>
              </tr>
            );
          })}

          {/* Total row */}
          {elements.length > 0 && (
            <tr className="bg-surface-container-low border-t border-outline-variant/30">
              <td colSpan={4} className="px-3 py-2 font-black uppercase tracking-widest text-on-surface-variant text-[10px]">
                Total
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-on-surface">
                {totalBV.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-[#ba1a1a]">
                {totalMin.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-right font-mono font-bold text-primary">
                {totalMax.toFixed(2)}
              </td>
              <td />
            </tr>
          )}

          {/* Empty state */}
          {elements.length === 0 && (
            <tr>
              <td colSpan={8} className="px-3 py-8 text-center text-on-surface-variant text-sm">
                Aucun élément. Utilisez le sélecteur ci-dessus pour ajouter des éléments.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/** Small inline button to add a jump to a combo. Opens a filtered jump picker. */
function AddComboButton({
  sov,
  includePairs,
  elementId,
  currentJumps,
  onAdd,
}: {
  sov: SovData;
  includePairs: boolean;
  elementId: string;
  currentJumps: number;
  onAdd: (elementId: string, jumpCode: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-on-surface-variant hover:text-primary transition-colors p-0.5"
        title={`Ajouter un saut (${currentJumps}/3)`}
      >
        <span className="material-symbols-outlined text-base">add</span>
      </button>

      {isOpen && (
        <div className="absolute z-50 top-full left-0 mt-1 w-48 bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant/20 p-2">
          <ElementPicker
            sov={sov}
            includePairs={includePairs}
            onSelect={(code) => {
              onAdd(elementId, code);
              setIsOpen(false);
            }}
            jumpsOnly
            placeholder="Ajouter un saut..."
          />
        </div>
      )}
    </div>
  );
}
