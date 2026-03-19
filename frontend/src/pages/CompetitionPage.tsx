import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Score } from "../api/client";
import ScoreChart from "../components/ScoreChart";

type SortKey = "rank" | "skater_name" | "total_score" | "technical_score" | "component_score";

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

  const segments = [...new Set(scores?.map((s) => s.segment) ?? [])].sort();

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

      {segments.map((segment) => {
        const segScores = (scores ?? [])
          .filter((s) => s.segment === segment)
          .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
        return (
          <div key={segment} className="mt-6">
            <h2 className="text-lg font-semibold mb-2">{segment}</h2>
            <ScoreChart scores={segScores} />
            <div className="overflow-x-auto mt-4">
              <table className="w-full text-sm border rounded bg-white shadow-sm">
                <thead className="bg-gray-100 text-left">
                  <tr>
                    <th className="px-3 py-2">Rank</th>
                    <th className="px-3 py-2">Skater</th>
                    <th className="px-3 py-2">Nat.</th>
                    <th className="px-3 py-2 text-right">Total</th>
                    <th className="px-3 py-2 text-right">TES</th>
                    <th className="px-3 py-2 text-right">PCS</th>
                    <th className="px-3 py-2 text-right">Ded.</th>
                  </tr>
                </thead>
                <tbody>
                  {segScores.map((s: Score) => (
                    <tr key={s.id} className="border-t hover:bg-gray-50">
                      <td className="px-3 py-2">{s.rank ?? "-"}</td>
                      <td className="px-3 py-2 font-medium">{s.skater_name ?? "-"}</td>
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
