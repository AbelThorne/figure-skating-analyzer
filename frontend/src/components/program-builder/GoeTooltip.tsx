import { useState, useRef } from "react";
import type { SovData } from "../../api/client";
import { getGoeBreakdown } from "../../utils/sov-calculator";

interface Props {
  sov: SovData;
  baseCode: string;
  markers: string[];
  side: "negative" | "positive";
  value: number;
  children: React.ReactNode;
}

export default function GoeTooltip({
  sov,
  baseCode,
  markers,
  side,
  value,
  children,
}: Props) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const breakdown = getGoeBreakdown(sov, baseCode, markers, side);

  function handleMouseEnter() {
    timeoutRef.current = setTimeout(() => setVisible(true), 300);
  }

  function handleMouseLeave() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  }

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}

      {visible && breakdown && (
        <div className="absolute z-50 bottom-full mb-1 left-1/2 -translate-x-1/2 bg-surface-container-lowest rounded-lg shadow-lg border border-outline-variant/20 p-2 whitespace-nowrap">
          <table className="text-[10px] font-mono">
            <tbody>
              {breakdown.map(({ level, value: goeValue }) => (
                <tr key={level}>
                  <td className={`pr-2 font-bold ${
                    side === "negative" ? "text-[#ba1a1a]" : "text-primary"
                  }`}>
                    {level > 0 ? `+${level}` : level}
                  </td>
                  <td className="text-right text-on-surface">
                    {goeValue.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
