import { useState, useEffect } from "react";
import { CategoryBreakdown } from "../api/client";

interface Props {
  breakdowns: CategoryBreakdown[];
  onClose: () => void;
}

export default function CategoryBreakdownModal({ breakdowns, onClose }: Props) {
  const [expanded, setExpanded] = useState<string | null>(
    breakdowns[0]?.category ?? null
  );

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-on-surface/40" />
      <div
        className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-headline font-bold text-on-surface text-base">
            Détail par catégorie
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Accordion */}
        <div className="space-y-2">
          {breakdowns.map((bd) => {
            const isOpen = expanded === bd.category;
            const clubTotal = bd.club_skaters.reduce((s, sk) => s + sk.total_points, 0);
            return (
              <div key={bd.category}>
                <button
                  onClick={() => setExpanded(isOpen ? null : bd.category)}
                  className="w-full flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg text-left hover:bg-surface-container-high transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">
                    {isOpen ? "expand_more" : "chevron_right"}
                  </span>
                  <span className="font-semibold text-xs text-on-surface">
                    {bd.category}
                  </span>
                  <span className="text-[10px] text-on-surface-variant ml-auto">
                    {bd.club_skaters.length} patineur{bd.club_skaters.length > 1 ? "s" : ""}
                    {" · "}
                    {clubTotal} pts club
                  </span>
                </button>
                {isOpen && bd.club_skaters.length > 0 && (
                  <table className="w-[calc(100%-20px)] ml-5 mt-1 text-xs">
                    <thead>
                      <tr className="text-on-surface-variant text-[10px]">
                        <td className="py-1 px-2">Rang</td>
                        <td className="py-1 px-2">Patineur</td>
                        <td className="py-1 px-2 text-right">Base</td>
                        <td className="py-1 px-2 text-right">Podium</td>
                        <td className="py-1 px-2 text-right font-semibold">Total</td>
                      </tr>
                    </thead>
                    <tbody>
                      {bd.club_skaters.map((sk) => (
                        <tr key={sk.skater_name}>
                          <td className="py-1 px-2 font-mono">{sk.rank}</td>
                          <td className="py-1 px-2 font-medium">{sk.skater_name}</td>
                          <td className="py-1 px-2 text-right font-mono">{sk.base_points}</td>
                          <td className="py-1 px-2 text-right font-mono text-primary">
                            {sk.podium_points > 0 ? `+${sk.podium_points}` : "—"}
                          </td>
                          <td className="py-1 px-2 text-right font-mono font-bold">
                            {sk.total_points}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {isOpen && bd.club_skaters.length === 0 && (
                  <p className="ml-5 mt-1 text-[10px] text-on-surface-variant">
                    Aucun patineur du club dans cette catégorie
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
