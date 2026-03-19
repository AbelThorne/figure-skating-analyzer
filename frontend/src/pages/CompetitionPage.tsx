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

  if (loadingComp || loadingScores) return <p className="text-gray-500">Loading...</p>;
  if (!competition) return <p className="text-red-600">Competition not found.</p>;

  // Group by category + segment for a clearer layout
  const groups = groupByCategory(scores ?? []);

  return (
    <div>
      <Link to="/" className="text-blue-600 hover:underline text-sm">
        ← Back
      </Link>
      <h1 className="text-2xl font-bold mt-2">{competition.name}</h1>
      <div className="text-sm text-gray-500 mb-4">
        {[competition.discipline, competition.season, competition.date]
          .filter(Boolean)
          .join(" · ")}
      </div>

      {(!scores || scores.length === 0) && (
        <p className="text-gray-500">
          No scores yet. Use the Import button on the home page to download score sheets.
        </p>
      )}

      {groups.map(({ category, segment, scores: groupScores }) => (
        <div key={`${category}-${segment}`} className="mt-8">
          <div className="flex items-baseline gap-3 mb-2">
            <h2 className="text-lg font-semibold">{category ?? segment}</h2>
            {category && (
              <span className="text-sm text-gray-500 font-medium">{segment}</span>
            )}
          </div>
          <ScoreChart scores={groupScores} />
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm border rounded bg-white shadow-sm">
              <thead className="bg-gray-100 text-left">
                <tr>
                  <th className="px-3 py-2">Rank</th>
                  <th className="px-3 py-2">N°</th>
                  <th className="px-3 py-2">Skater</th>
                  <th className="px-3 py-2">Club</th>
                  <th className="px-3 py-2">Nat.</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">TES</th>
                  <th className="px-3 py-2 text-right">PCS</th>
                  <th className="px-3 py-2 text-right">Ded.</th>
                </tr>
              </thead>
              <tbody>
                {groupScores.map((s: Score) => (
                  <tr key={s.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2">{s.rank ?? "-"}</td>
                    <td className="px-3 py-2 text-gray-400">{s.starting_number ?? "-"}</td>
                    <td className="px-3 py-2 font-medium">{s.skater_name ?? "-"}</td>
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
      ))}
    </div>
  );
}
