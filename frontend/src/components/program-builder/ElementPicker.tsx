import { useState, useRef, useEffect } from "react";
import type { SovData } from "../../api/client";
import { getBaseElements } from "../../utils/sov-calculator";

const TYPE_LABELS: Record<string, string> = {
  jump: "Sauts",
  spin: "Pirouettes",
  step: "Pas",
  choreo: "Chorégraphique",
  lift: "Portés",
  throw: "Jetés",
  twist: "Twist lifts",
  death_spiral: "Spirales de la mort",
  pair_spin: "Pirouettes couple",
  pivot: "Pivot",
};

const TYPE_ORDER = [
  "jump", "spin", "step", "choreo",
  "lift", "throw", "twist", "death_spiral", "pair_spin", "pivot",
];

interface Props {
  sov: SovData;
  includePairs: boolean;
  onSelect: (code: string) => void;
  /** If true, only show jumps (for combo add). */
  jumpsOnly?: boolean;
  /** Placeholder text. */
  placeholder?: string;
}

export default function ElementPicker({
  sov,
  includePairs,
  onSelect,
  jumpsOnly = false,
  placeholder = "Rechercher un élément...",
}: Props) {
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const allGroups = getBaseElements(sov, includePairs);

  // Filter groups by search and jumpsOnly
  const filteredGroups: Record<string, string[]> = {};
  const searchLower = search.toLowerCase();

  for (const type of TYPE_ORDER) {
    if (jumpsOnly && type !== "jump") continue;
    const codes = allGroups[type];
    if (!codes) continue;

    const filtered = codes.filter(code =>
      code.toLowerCase().includes(searchLower),
    );
    if (filtered.length > 0) {
      filteredGroups[type] = filtered;
    }
  }

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleSelect(code: string) {
    onSelect(code);
    setSearch("");
    setIsOpen(false);
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        value={search}
        placeholder={placeholder}
        onChange={e => {
          setSearch(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        className="w-full px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      {isOpen && Object.keys(filteredGroups).length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-xl bg-surface-container-lowest shadow-lg border border-outline-variant/20">
          {Object.entries(filteredGroups).map(([type, codes]) => (
            <div key={type}>
              <div className="px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant bg-surface-container-low/50 sticky top-0">
                {TYPE_LABELS[type] ?? type}
              </div>
              {codes.map(code => (
                <button
                  key={code}
                  onClick={() => handleSelect(code)}
                  className="w-full text-left px-3 py-1.5 text-sm font-mono hover:bg-surface-container transition-colors"
                >
                  {code}
                  <span className="ml-2 text-xs text-on-surface-variant">
                    {sov.elements[code]?.base_value.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      {isOpen && Object.keys(filteredGroups).length === 0 && search && (
        <div className="absolute z-50 mt-1 w-full rounded-xl bg-surface-container-lowest shadow-lg border border-outline-variant/20 p-3 text-sm text-on-surface-variant">
          Aucun élément trouvé
        </div>
      )}
    </div>
  );
}
