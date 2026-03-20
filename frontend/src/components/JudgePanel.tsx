import { Element } from "../api/client";

interface Props {
  elements: Element[];
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
            return (
              <tr
                key={`${el.score_id}-${el.element_name}-${rowIdx}`}
                className={rowIdx % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"}
              >
                <td className="font-mono text-sm text-on-surface px-4 py-2 whitespace-nowrap">
                  {el.element_name}
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
