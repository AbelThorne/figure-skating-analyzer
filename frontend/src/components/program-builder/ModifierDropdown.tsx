import { useState, useRef, useEffect } from "react";
import { isFlipOrLutz } from "../../utils/sov-calculator";

/** Marker definitions with labels, exclusion groups, and compatibility. */
interface MarkerDef {
  value: string;
  label: string;
  desc: string;
  group?: string; // Markers in the same group are mutually exclusive
  flipLutzOnly?: boolean;
}

const JUMP_MARKERS: MarkerDef[] = [
  { value: "q", label: "q", desc: "Quart court", group: "rotation" },
  { value: "<", label: "<", desc: "Sous-rotation", group: "rotation" },
  { value: "<<", label: "<<", desc: "Déclassé", group: "rotation" },
  { value: "e", label: "e", desc: "Carre incorrecte", group: "edge", flipLutzOnly: true },
  { value: "!", label: "!", desc: "Carre incertaine", group: "edge", flipLutzOnly: true },
  { value: "*", label: "*", desc: "Annulé" },
  { value: "x", label: "x", desc: "Bonus 2e moitié" },
];

const SPIN_MARKERS: MarkerDef[] = [
  { value: "V", label: "V", desc: "Valeur réduite" },
  { value: "*", label: "*", desc: "Annulé" },
];

const GENERIC_MARKERS: MarkerDef[] = [
  { value: "*", label: "*", desc: "Annulé" },
];

interface Props {
  elementCode: string;
  elementType: string;
  activeMarkers: string[];
  onChange: (markers: string[]) => void;
  /** Markers to exclude from the dropdown (e.g., combo-level markers like "x"). */
  excludeMarkers?: string[];
}

export default function ModifierDropdown({
  elementCode,
  elementType,
  activeMarkers,
  onChange,
  excludeMarkers,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isFL = isFlipOrLutz(elementCode);

  // Close on outside click or Escape
  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [isOpen]);

  // Get available markers based on element type
  let availableMarkers: MarkerDef[];
  if (elementType === "jump") {
    availableMarkers = JUMP_MARKERS.filter(m => !m.flipLutzOnly || isFL);
  } else if (elementType === "spin" || elementType === "pair_spin") {
    availableMarkers = SPIN_MARKERS;
  } else {
    availableMarkers = GENERIC_MARKERS;
  }

  // Filter out excluded markers (e.g., "x" for individual combo jumps)
  if (excludeMarkers?.length) {
    availableMarkers = availableMarkers.filter(m => !excludeMarkers.includes(m.value));
  }

  function toggleMarker(marker: string) {
    if (marker === "*") {
      // * is exclusive with everything
      if (activeMarkers.includes("*")) {
        onChange([]);
      } else {
        onChange(["*"]);
      }
      return;
    }

    // If * is active, remove it first
    let current = activeMarkers.filter(m => m !== "*");

    if (current.includes(marker)) {
      // Remove the marker
      onChange(current.filter(m => m !== marker));
      return;
    }

    // Find the marker definition to check group exclusivity
    const def = availableMarkers.find(m => m.value === marker);
    if (def?.group) {
      // Remove other markers in the same group
      const sameGroup = availableMarkers
        .filter(m => m.group === def.group && m.value !== marker)
        .map(m => m.value);
      current = current.filter(m => !sameGroup.includes(m));
    }

    onChange([...current, marker]);
  }

  if (availableMarkers.length === 0) return null;

  const hasActive = activeMarkers.length > 0;

  return (
    <div className="relative" ref={ref}>
      {/* Trigger: show active markers as chips, or a subtle "+" button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded transition-colors cursor-pointer ${
          hasActive
            ? "bg-primary/5 hover:bg-primary/10"
            : "hover:bg-surface-container"
        }`}
        title="Modificateurs"
      >
        {hasActive ? (
          activeMarkers.map(m => (
            <span
              key={m}
              className={`text-[10px] font-mono font-bold ${
                m === "*" || m === "<<"
                  ? "text-[#ba1a1a]"
                  : m === "x"
                    ? "text-primary"
                    : "text-[#e65100]"
              }`}
            >
              {m}
            </span>
          ))
        ) : (
          <span className="material-symbols-outlined text-sm text-on-surface-variant">
            tune
          </span>
        )}
      </button>

      {/* Popover with marker toggles */}
      {isOpen && (
        <div className="absolute z-50 top-full left-0 mt-1 bg-surface-container-lowest rounded-lg shadow-lg border border-outline-variant/20 p-1.5 min-w-[140px]">
          {availableMarkers.map(marker => {
            const isActive = activeMarkers.includes(marker.value);
            return (
              <button
                key={marker.value}
                onClick={() => toggleMarker(marker.value)}
                className={`w-full flex items-center gap-2 px-2 py-1 rounded text-left transition-colors cursor-pointer ${
                  isActive
                    ? "bg-primary/10"
                    : "hover:bg-surface-container"
                }`}
              >
                <span className={`font-mono text-xs font-bold w-5 text-center ${
                  isActive ? "text-primary" : "text-on-surface-variant"
                }`}>
                  {marker.label}
                </span>
                <span className={`text-[10px] ${
                  isActive ? "text-on-surface" : "text-on-surface-variant"
                }`}>
                  {marker.desc}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
