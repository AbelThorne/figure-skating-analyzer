import { useState, useRef, useEffect, useCallback } from "react";
import type { SovData } from "../../api/client";
import { getGoeBreakdown } from "../../utils/sov-calculator";

interface Props {
  sov: SovData;
  baseCode: string;
  markers: string[];
  side: "negative" | "positive";
  value: number;
  children: React.ReactNode;
  /** Optional pre-computed breakdown (for combos). Overrides internal calculation. */
  precomputedBreakdown?: { level: number; value: number }[] | null;
}

export default function GoeTooltip({
  sov,
  baseCode,
  markers,
  side,
  value,
  children,
  precomputedBreakdown,
}: Props) {
  const [visible, setVisible] = useState(false);
  const [flipUp, setFlipUp] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  const breakdown = precomputedBreakdown !== undefined
    ? precomputedBreakdown
    : getGoeBreakdown(sov, baseCode, markers, side);

  const checkPosition = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    // If less than 130px above the element, flip to show below
    setFlipUp(rect.top > 130);
  }, []);

  function handleMouseEnter() {
    checkPosition();
    timeoutRef.current = setTimeout(() => setVisible(true), 300);
  }

  function handleMouseLeave() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  }

  return (
    <div
      ref={containerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}

      {visible && breakdown && (
        <div className={`absolute z-50 left-1/2 -translate-x-1/2 bg-surface-container-lowest rounded-lg shadow-lg border border-outline-variant/20 p-2 whitespace-nowrap ${
          flipUp ? "bottom-full mb-1" : "top-full mt-1"
        }`}>
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
