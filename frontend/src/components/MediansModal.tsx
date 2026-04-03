import { useState, useEffect } from "react";

interface MediansModalProps {
  medians: Record<string, Record<string, number>>;
  onSave: (medians: Record<string, Record<string, number>>) => void;
  onClose: () => void;
  saving?: boolean;
  title?: string;
}

const DIVISIONS = ["D1", "D2", "D3"];

const CATEGORY_ORDER = [
  "Poussins dames",
  "Poussins messieurs",
  "Benjamins dames",
  "Benjamins messieurs",
  "Minimes dames",
  "Minimes messieurs",
  "Novices dames",
  "Novices messieurs",
  "Juniors dames",
  "Juniors messieurs",
  "Seniors dames",
  "Seniors messieurs",
  "Couples novices",
  "Couples juniors",
  "Couples seniors",
];

export default function MediansModal({ medians, onSave, onClose, saving, title }: MediansModalProps) {
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});

  useEffect(() => {
    const d: Record<string, Record<string, string>> = {};
    for (const cat of CATEGORY_ORDER) {
      d[cat] = {};
      for (const div of DIVISIONS) {
        const val = medians[cat]?.[div];
        d[cat][div] = val != null ? String(val) : "";
      }
    }
    setDraft(d);
  }, [medians]);

  const handleChange = (cat: string, div: string, value: string) => {
    setDraft((prev) => ({
      ...prev,
      [cat]: { ...prev[cat], [div]: value },
    }));
  };

  const handleSave = () => {
    const result: Record<string, Record<string, number>> = {};
    for (const cat of CATEGORY_ORDER) {
      result[cat] = {};
      for (const div of DIVISIONS) {
        const val = parseFloat(draft[cat]?.[div] || "");
        if (!isNaN(val) && val > 0) {
          result[cat][div] = val;
        }
      }
      if (Object.keys(result[cat]).length === 0) {
        delete result[cat];
      }
    }
    onSave(result);
  };

  const isCouples = (cat: string) => cat.startsWith("Couples");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl max-w-2xl w-full mx-4 max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-bold text-on-surface">
            {title || "Modifier les medianes"}
          </h2>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-on-surface-variant uppercase tracking-wider">
                <th className="py-2 pr-4">Categorie</th>
                <th className="py-2 px-2 text-right w-20">D1</th>
                <th className="py-2 px-2 text-right w-20">D2</th>
                <th className="py-2 px-2 text-right w-20">D3</th>
              </tr>
            </thead>
            <tbody>
              {CATEGORY_ORDER.map((cat) => (
                <tr key={cat} className="border-t border-gray-100">
                  <td className="py-2 pr-4 font-medium text-on-surface">{cat}</td>
                  {DIVISIONS.map((div) => (
                    <td key={div} className="py-2 px-2">
                      {isCouples(cat) && div !== "D1" ? (
                        <span className="text-gray-300 text-center block">—</span>
                      ) : (
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={draft[cat]?.[div] ?? ""}
                          onChange={(e) => handleChange(cat, div, e.target.value)}
                          className="w-full px-2 py-1 bg-surface-container-low rounded-lg text-right font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-xl text-on-surface-variant hover:bg-surface-container"
          >
            Annuler
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm rounded-xl bg-primary text-white hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
