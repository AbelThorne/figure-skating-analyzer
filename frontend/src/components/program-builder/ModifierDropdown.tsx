import { isFlipOrLutz } from "../../utils/sov-calculator";

/** Marker definitions with labels, exclusion groups, and compatibility. */
interface MarkerDef {
  value: string;
  label: string;
  group?: string; // Markers in the same group are mutually exclusive
  flipLutzOnly?: boolean;
}

const JUMP_MARKERS: MarkerDef[] = [
  { value: "q", label: "q", group: "rotation" },
  { value: "<", label: "<", group: "rotation" },
  { value: "<<", label: "<<", group: "rotation" },
  { value: "e", label: "e", group: "edge", flipLutzOnly: true },
  { value: "!", label: "!", group: "edge", flipLutzOnly: true },
  { value: "*", label: "*" },
  { value: "x", label: "x" },
  { value: "+REP", label: "+REP" },
];

const SPIN_MARKERS: MarkerDef[] = [
  { value: "V", label: "V" },
  { value: "*", label: "*" },
];

const GENERIC_MARKERS: MarkerDef[] = [
  { value: "*", label: "*" },
];

interface Props {
  elementCode: string;
  elementType: string;
  activeMarkers: string[];
  onChange: (markers: string[]) => void;
}

export default function ModifierDropdown({
  elementCode,
  elementType,
  activeMarkers,
  onChange,
}: Props) {
  const isFL = isFlipOrLutz(elementCode);

  // Get available markers based on element type
  let availableMarkers: MarkerDef[];
  if (elementType === "jump") {
    availableMarkers = JUMP_MARKERS.filter(m => !m.flipLutzOnly || isFL);
  } else if (elementType === "spin" || elementType === "pair_spin") {
    availableMarkers = SPIN_MARKERS;
  } else {
    availableMarkers = GENERIC_MARKERS;
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

  return (
    <div className="flex gap-0.5 flex-wrap">
      {availableMarkers.map(marker => {
        const isActive = activeMarkers.includes(marker.value);
        return (
          <button
            key={marker.value}
            onClick={() => toggleMarker(marker.value)}
            title={marker.label}
            className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
              isActive
                ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container"
            }`}
          >
            {marker.label}
          </button>
        );
      })}
    </div>
  );
}
