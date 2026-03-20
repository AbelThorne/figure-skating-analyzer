import { Element } from "../api/client";

interface Props {
  elements: Element[];
}

const JUDGES = [1, 2, 3, 4, 5, 6, 7, 8, 9];

function judgeCell(value: number | null | undefined) {
  if (value == null) return { label: "—", className: "bg-surface-container text-on-surface-variant" };
  if (value > 0)
    return {
      label: `+${value}`,
      className: "bg-primary-container/40 text-on-primary-container",
    };
  if (value < 0)
    return {
      label: String(value),
      className: "bg-error-container/40 text-on-error-container",
    };
  return { label: "0", className: "bg-surface-container text-on-surface-variant" };
}

export default function JudgePanel({ elements }: Props) {
  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-on-surface-variant text-sm font-body">
        Aucune donnée de juges disponible
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-auto">
      <table className="w-full min-w-[640px] border-collapse">
        <thead>
          <tr className="bg-surface-container-low">
            <th className="text-left text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-4 py-2.5 rounded-tl-xl">
              Élément
            </th>
            {JUDGES.map((j) => (
              <th
                key={j}
                className="text-center text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-2 py-2.5"
              >
                J{j}
              </th>
            ))}
            <th className="text-center text-[10px] font-black uppercase tracking-widest text-on-surface-variant px-3 py-2.5 rounded-tr-xl">
              GOE
            </th>
          </tr>
        </thead>
        <tbody>
          {elements.map((el, rowIdx) => (
            <tr
              key={`${el.score_id}-${el.element_name}-${rowIdx}`}
              className={rowIdx % 2 === 0 ? "bg-surface-container-lowest" : "bg-surface-container-low/30"}
            >
              <td className="font-mono text-sm text-on-surface px-4 py-2 whitespace-nowrap">
                {el.element_name}
              </td>
              {JUDGES.map((j) => {
                const jIdx = j - 1;
                const val = el.judges?.[jIdx] ?? null;
                const { label, className } = judgeCell(val);
                return (
                  <td key={j} className="px-1.5 py-2 text-center">
                    <span
                      className={`inline-block font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded ${className}`}
                    >
                      {label}
                    </span>
                  </td>
                );
              })}
              <td className="px-3 py-2 text-center">
                {el.goe != null ? (
                  <span
                    className={`font-mono font-bold text-sm ${
                      el.goe > 0
                        ? "text-primary"
                        : el.goe < 0
                        ? "text-[#ba1a1a]"
                        : "text-on-surface-variant"
                    }`}
                  >
                    {el.goe > 0 ? "+" : ""}
                    {el.goe.toFixed(2)}
                  </span>
                ) : (
                  <span className="font-mono text-sm text-on-surface-variant">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
