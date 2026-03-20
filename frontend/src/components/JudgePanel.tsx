import { Element } from "../api/client";

interface Props {
  elements: Element[];
}

// Colour + label config for each ISU marker
const MARKER_STYLE: Record<string, { color: string; title: string }> = {
  "*":  { color: "text-[#ba1a1a]", title: "Élément annulé (hors limite)" },
  "<<": { color: "text-[#ba1a1a]", title: "Déclassement (≥½ tour)" },
  "<":  { color: "text-[#e65100]", title: "Sous-rotation (¼–½ tour)" },
  "q":  { color: "text-[#e65100]", title: "Quart de tour court" },
  "e":  { color: "text-[#e65100]", title: "Carre incorrecte (décollage)" },
  "!":  { color: "text-[#b45309]", title: "Carre incertaine (avertissement)" },
  "x":  { color: "text-primary",   title: "Bonus seconde moitié (×1,10)" },
};

/**
 * Render an element name with markers annotated inline.
 *
 * The parser stores markers in two formats:
 *
 * Non-combo (no "+" in name): flat list, e.g. ["<"] or ["x"]
 *   → markers render after the element name.
 *
 * Combo (name contains "+"): positional list, one entry per jump part.
 *   "+" sentinel means no marker on that position.
 *   e.g. "2S+1T" with markers ["<", "+"] → < renders after "2S", nothing after "1T"
 *        "3F+2T" with markers ["+", "e"] → nothing after "3F", e renders after "2T"
 *
 * The positional format is detected by checking whether any marker equals "+".
 */
function ElementName({ name, markers }: { name: string; markers: string[] }) {
  const parts = name.split("+");
  const isCombo = parts.length > 1;
  const isPositional = markers.some((m) => m === "+");

  if (!markers || markers.length === 0) {
    return <span>{name}</span>;
  }

  if (isCombo && isPositional) {
    // Positional combo: markers[i] corresponds to parts[i]
    // "+" means no marker for that jump
    return (
      <span>
        {parts.map((part, i) => {
          const marker = markers[i] ?? "+";
          return (
            <span key={i}>
              {i > 0 && <span className="text-on-surface-variant">+</span>}
              <span>{part}</span>
              {marker !== "+" && <MarkerBadge marker={marker} />}
            </span>
          );
        })}
      </span>
    );
  }

  // Non-combo or old-format combo (no positional "+" sentinel): flat markers after name
  if (!isCombo) {
    return (
      <span>
        <span>{name}</span>
        {markers.map((m, i) => (
          <MarkerBadge key={i} marker={m} />
        ))}
      </span>
    );
  }

  // Fallback: combo with non-positional flat markers — append all after last jump
  return (
    <span>
      {parts.map((part, i) => {
        const isLast = i === parts.length - 1;
        return (
          <span key={i}>
            {i > 0 && <span className="text-on-surface-variant">+</span>}
            <span>{part}</span>
            {isLast && markers.map((m, j) => (
              <MarkerBadge key={j} marker={m} />
            ))}
          </span>
        );
      })}
    </span>
  );
}

function MarkerBadge({ marker }: { marker: string }) {
  const style = MARKER_STYLE[marker] ?? { color: "text-on-surface-variant", title: marker };
  return (
    <span className="relative group inline-flex align-super">
      <span className={`font-mono text-[10px] font-bold ${style.color} ml-[1px] cursor-default`}>
        {marker}
      </span>
      <span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-50 whitespace-nowrap bg-on-surface text-surface text-[10px] font-body font-normal rounded-lg px-2 py-1 shadow-lg pointer-events-none">
        {style.title}
      </span>
    </span>
  );
}

function goeCell(value: number | null | undefined) {
  if (value == null) return { label: "—", className: "text-on-surface-variant" };
  if (value > 0)
    return {
      label: `+${value.toFixed(2)}`,
      className: "text-primary font-bold",
    };
  if (value < 0)
    return {
      label: value.toFixed(2),
      className: "text-[#ba1a1a] font-bold",
    };
  return { label: "0.00", className: "text-on-surface-variant" };
}

export default function JudgePanel({ elements }: Props) {
  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-on-surface-variant text-sm font-body">
        Aucune donnée d'élément disponible
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-auto">
      <table className="w-full min-w-[400px] border-collapse">
        <thead>
          <tr className="bg-surface-container-low">
            <th className="text-left text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-4 py-2.5 rounded-tl-xl">
              Élément
            </th>
            <th className="text-right text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5">
              Base
            </th>
            <th className="text-right text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5">
              GOE
            </th>
            <th className="text-right text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 rounded-tr-xl">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {elements.map((el, rowIdx) => {
            const { label: goeLabel, className: goeCls } = goeCell(el.goe);
            const total =
              el.base_value != null && el.goe != null
                ? el.base_value + el.goe
                : el.total ?? null;
            const isNullified = el.markers?.includes("*");
            return (
              <tr
                key={`${el.score_id}-${el.element_name}-${rowIdx}`}
                className={`${rowIdx % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"} ${isNullified ? "opacity-50" : ""}`}
              >
                <td className="font-mono text-sm text-on-surface px-4 py-2 whitespace-nowrap">
                  <ElementName name={el.element_name} markers={el.markers ?? []} />
                </td>
                <td className="font-mono text-sm text-on-surface-variant px-3 py-2 text-right">
                  {el.base_value?.toFixed(2) ?? "—"}
                </td>
                <td className={`font-mono text-sm px-3 py-2 text-right ${goeCls}`}>
                  {goeLabel}
                </td>
                <td className="font-mono text-sm font-bold text-on-surface px-3 py-2 text-right">
                  {total != null ? total.toFixed(2) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
