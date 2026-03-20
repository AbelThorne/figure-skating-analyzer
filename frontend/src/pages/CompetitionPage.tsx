import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Score } from "../api/client";
import ScoreChart from "../components/ScoreChart";

interface ScoreGroup {
  category: string | null;
  segment: string;
  scores: Score[];
}

function groupByCategory(scores: Score[]): ScoreGroup[] {
  const map = new Map<string, ScoreGroup>();
  for (const s of scores) {
    const key = `${s.category ?? ""}__${s.segment}`;
    if (!map.has(key)) {
      map.set(key, { category: s.category, segment: s.segment, scores: [] });
    }
    map.get(key)!.scores.push(s);
  }
  for (const g of map.values()) {
    g.scores.sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
  }
  return [...map.values()].sort((a, b) => {
    const catCmp = (a.category ?? "").localeCompare(b.category ?? "");
    return catCmp !== 0 ? catCmp : a.segment.localeCompare(b.segment);
  });
}

export default function CompetitionPage() {
  const { id } = useParams<{ id: string }>();
  const competitionId = Number(id);

  const { data: competition, isLoading: loadingComp } = useQuery({
    queryKey: ["competition", competitionId],
    queryFn: () => api.competitions.get(competitionId),
  });

  const { data: scores, isLoading: loadingScores } = useQuery({
    queryKey: ["scores", { competition_id: competitionId }],
    queryFn: () => api.scores.list({ competition_id: competitionId }),
  });

  if (loadingComp || loadingScores) return <p className="text-gray-500">Chargement...</p>;
  if (!competition) return <p className="text-red-600">Compétition introuvable.</p>;

  // Group by category + segment for a clearer layout
  const groups = groupByCategory(scores ?? []);

  return (
    <div>
      <Link to="/competitions" className="text-primary text-xs font-bold uppercase tracking-wider hover:underline flex items-center gap-1">
        <span className="material-symbols-outlined text-base">arrow_back</span> Retour
      </Link>
      <h1 className="text-2xl font-bold mt-2">{competition.name}</h1>
      <div className="text-sm text-gray-500 mb-4">
        {[competition.discipline, competition.season, competition.date]
          .filter(Boolean)
          .join(" · ")}
      </div>

      {(!scores || scores.length === 0) && (
        <p className="text-gray-500">
          Aucun résultat. Utilisez le bouton Importer sur la page Compétitions.
        </p>
      )}

      {groups.length > 1 && (
        <nav className="flex flex-wrap gap-2 mb-6">
          {groups.map(({ category, segment }) => {
            const anchor = `${category ?? ""}-${segment}`.replace(/\s+/g, "-");
            return (
              <a
                key={anchor}
                href={`#${anchor}`}
                className="text-sm px-3 py-1 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200"
              >
                {category ? `${category} · ${segment}` : segment}
              </a>
            );
          })}
        </nav>
      )}

      {groups.map(({ category, segment, scores: groupScores }) => {
        const anchor = `${category ?? ""}-${segment}`.replace(/\s+/g, "-");
        return (
        <div key={`${category}-${segment}`} id={anchor} className="mt-8 scroll-mt-16">
          <div className="mb-2">
            {category && <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{category}</p>}
            <h2 className="text-lg font-semibold">{segment}</h2>
          </div>
          <ScoreChart scores={groupScores} />
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm border rounded bg-white shadow-sm">
              <thead className="bg-gray-100 text-left">
                <tr>
                  <th className="px-3 py-2">Rang</th>
                  <th className="px-3 py-2">N°</th>
                  <th className="px-3 py-2">Patineur</th>
                  <th className="px-3 py-2">Club</th>
                  <th className="px-3 py-2">Nat.</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">TES</th>
                  <th className="px-3 py-2 text-right">PCS</th>
                  <th className="px-3 py-2 text-right">Pénal.</th>
                </tr>
              </thead>
              <tbody>
                {groupScores.map((s: Score) => (
                  <tr key={s.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2">{s.rank ?? "-"}</td>
                    <td className="px-3 py-2 text-gray-400">{s.starting_number ?? "-"}</td>
                    <td className="px-3 py-2">
                      <Link to={`/patineurs/${s.skater_id}/analyse`} className="font-medium hover:text-primary transition-colors">
                        {s.skater_name ?? "-"}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-gray-600 max-w-[180px] truncate">
                      {s.skater_club ?? "-"}
                    </td>
                    <td className="px-3 py-2 text-gray-500">{s.skater_nationality ?? "-"}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {s.total_score?.toFixed(2) ?? "-"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {s.technical_score?.toFixed(2) ?? "-"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {s.component_score?.toFixed(2) ?? "-"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-red-600">
                      {s.deductions != null && s.deductions !== 0
                        ? `-${s.deductions.toFixed(2)}`
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        );
      })}
    </div>
  );
}
