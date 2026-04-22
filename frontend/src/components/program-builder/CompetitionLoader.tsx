import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

interface Props {
  onLoad: (elements: { code: string; markers: string[] }[]) => void;
}

export default function CompetitionLoader({ onLoad }: Props) {
  const [showAll, setShowAll] = useState(false);
  const [selectedSkaterId, setSelectedSkaterId] = useState<number | null>(null);
  const [selectedScoreId, setSelectedScoreId] = useState<number | null>(null);

  // Get club name from app config
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  // Fetch skaters — filter by club unless "Tous les patineurs" is checked
  const { data: skaters } = useQuery({
    queryKey: ["skaters", showAll ? "all" : "club"],
    queryFn: () => api.skaters.list(showAll ? {} : { club: config?.club_short }),
    enabled: showAll || !!config?.club_short,
  });

  // Fetch scores for selected skater
  const { data: scores } = useQuery({
    queryKey: ["skater-scores", selectedSkaterId],
    queryFn: () => api.skaters.scores(selectedSkaterId!),
    enabled: selectedSkaterId != null,
  });

  // Group scores by competition for display
  const scoreOptions = (scores ?? [])
    .filter(s => s.elements && s.elements.length > 0)
    .sort((a, b) => {
      const dateA = a.competition_date ?? "";
      const dateB = b.competition_date ?? "";
      return dateB.localeCompare(dateA);
    });

  function handleLoad() {
    if (!selectedScoreId || !scores) return;
    const score = scores.find(s => s.id === selectedScoreId);
    if (!score?.elements) return;

    const elements = score.elements.map(el => ({
      code: el.name,
      markers: (el.markers ?? []).filter(m => m !== "+" && m !== "F"),
    }));
    onLoad(elements);
  }

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 bg-surface-container-low/50 rounded-xl">
      <div className="flex-1 min-w-[160px]">
        <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
          Patineur
        </label>
        <select
          value={selectedSkaterId ?? ""}
          onChange={e => {
            setSelectedSkaterId(e.target.value ? Number(e.target.value) : null);
            setSelectedScoreId(null);
          }}
          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Sélectionner...</option>
          {(skaters ?? []).map(s => (
            <option key={s.id} value={s.id}>
              {s.last_name} {s.first_name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer mt-1.5">
          <input
            type="checkbox"
            checked={showAll}
            onChange={e => {
              setShowAll(e.target.checked);
              setSelectedSkaterId(null);
              setSelectedScoreId(null);
            }}
            className="rounded"
          />
          Tous les patineurs
        </label>
      </div>

      <div className="flex-1 min-w-[200px]">
        <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
          Score
        </label>
        <select
          value={selectedScoreId ?? ""}
          onChange={e => setSelectedScoreId(e.target.value ? Number(e.target.value) : null)}
          disabled={!selectedSkaterId}
          className="w-full px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
        >
          <option value="">Sélectionner...</option>
          {scoreOptions.map(s => (
            <option key={s.id} value={s.id}>
              {s.competition_name} — {s.segment?.toUpperCase()} {s.category ? `(${s.category})` : ""}
              {s.competition_date ? ` · ${s.competition_date.slice(0, 10)}` : ""}
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={handleLoad}
        disabled={!selectedScoreId}
        className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
      >
        Charger
      </button>
    </div>
  );
}
