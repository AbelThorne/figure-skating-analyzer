import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, Score, CategoryResult } from "../api/client";
import ScoreChart from "../components/ScoreChart";

// --- Grouping helpers ---

interface CategoryGroup {
  category: string | null;
  segmentCount: number;
  /** For multi-segment categories: overall standings from CAT page */
  categoryResults: CategoryResult[];
  /** Segment-level scores grouped by segment name */
  segments: { segment: string; scores: Score[] }[];
}

function buildCategoryGroups(
  scores: Score[],
  catResults: CategoryResult[]
): CategoryGroup[] {
  // Group scores by category
  const catScoreMap = new Map<string, Score[]>();
  for (const s of scores) {
    const key = s.category ?? "";
    if (!catScoreMap.has(key)) catScoreMap.set(key, []);
    catScoreMap.get(key)!.push(s);
  }

  // Group category results by category
  const catResultMap = new Map<string, CategoryResult[]>();
  for (const cr of catResults) {
    const key = cr.category ?? "";
    if (!catResultMap.has(key)) catResultMap.set(key, []);
    catResultMap.get(key)!.push(cr);
  }

  // Build groups for each known category
  const allCategories = new Set([...catScoreMap.keys(), ...catResultMap.keys()]);
  const groups: CategoryGroup[] = [];

  for (const cat of allCategories) {
    const catScores = catScoreMap.get(cat) ?? [];
    const results = catResultMap.get(cat) ?? [];

    // Determine segment count from category results or from distinct segments in scores
    const distinctSegments = [...new Set(catScores.map((s) => s.segment))].sort();
    const segmentCount = results.length > 0 ? results[0].segment_count : distinctSegments.length;

    // Build segment sub-groups
    const segMap = new Map<string, Score[]>();
    for (const s of catScores) {
      if (!segMap.has(s.segment)) segMap.set(s.segment, []);
      segMap.get(s.segment)!.push(s);
    }
    const segments = [...segMap.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([segment, segScores]) => ({
        segment,
        scores: segScores.sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999)),
      }));

    // Sort category results by overall rank
    results.sort((a, b) => (a.overall_rank ?? 999) - (b.overall_rank ?? 999));

    groups.push({
      category: cat || null,
      segmentCount,
      categoryResults: results,
      segments,
    });
  }

  return groups.sort((a, b) => (a.category ?? "").localeCompare(b.category ?? ""));
}

// --- Components ---

function OverallResultsTable({ group }: { group: CategoryGroup }) {
  const hasMultipleSegments = group.segmentCount > 1;

  return (
    <div className="overflow-x-auto mt-3">
      <table className="w-full text-sm border rounded bg-white shadow-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="px-3 py-2">Rang</th>
            <th className="px-3 py-2">Patineur</th>
            <th className="px-3 py-2">Club</th>
            <th className="px-3 py-2">Nat.</th>
            <th className="px-3 py-2 text-right">Total</th>
            {hasMultipleSegments && (
              <>
                <th className="px-3 py-2 text-right">Rg SP</th>
                <th className="px-3 py-2 text-right">Rg PL</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {group.categoryResults.map((cr) => (
            <tr key={cr.id} className="border-t hover:bg-gray-50">
              <td className="px-3 py-2">
                {cr.overall_rank != null ? (
                  cr.overall_rank <= 3 ? (
                    <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-1 rounded-full">
                      {cr.overall_rank}
                    </span>
                  ) : (
                    cr.overall_rank
                  )
                ) : (
                  "-"
                )}
              </td>
              <td className="px-3 py-2">
                <Link
                  to={`/patineurs/${cr.skater_id}/analyse`}
                  className="font-medium hover:text-primary transition-colors"
                >
                  {cr.skater_first_name ? `${cr.skater_first_name} ${cr.skater_last_name}` : (cr.skater_last_name || "-")}
                </Link>
              </td>
              <td className="px-3 py-2 text-gray-600 max-w-[180px] truncate">
                {cr.skater_club ?? "-"}
              </td>
              <td className="px-3 py-2 text-gray-500">{cr.skater_nationality ?? "-"}</td>
              <td className="px-3 py-2 text-right font-mono font-bold">
                {cr.combined_total?.toFixed(2) ?? "-"}
              </td>
              {hasMultipleSegments && (
                <>
                  <td className="px-3 py-2 text-right font-mono text-gray-500">
                    {cr.sp_rank ?? "-"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-500">
                    {cr.fs_rank ?? "-"}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SegmentScoresTable({ scores }: { scores: Score[] }) {
  return (
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
          {scores.map((s: Score) => (
            <tr key={s.id} className="border-t hover:bg-gray-50">
              <td className="px-3 py-2">{s.rank ?? "-"}</td>
              <td className="px-3 py-2 text-gray-400">{s.starting_number ?? "-"}</td>
              <td className="px-3 py-2">
                <Link
                  to={`/patineurs/${s.skater_id}/analyse`}
                  className="font-medium hover:text-primary transition-colors"
                >
                  {s.skater_first_name ? `${s.skater_first_name} ${s.skater_last_name}` : (s.skater_last_name || "-")}
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
  );
}

// --- Main page ---

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

  const { data: catResults, isLoading: loadingCatResults } = useQuery({
    queryKey: ["category-results", { competition_id: competitionId }],
    queryFn: () => api.scores.categoryResults({ competition_id: competitionId }),
  });

  if (loadingComp || loadingScores || loadingCatResults)
    return <p className="text-gray-500">Chargement...</p>;
  if (!competition)
    return <p className="text-red-600">Compétition introuvable.</p>;

  const groups = buildCategoryGroups(scores ?? [], catResults ?? []);

  return (
    <div>
      <Link
        to="/competitions"
        className="text-primary text-xs font-bold uppercase tracking-wider hover:underline flex items-center gap-1"
      >
        <span className="material-symbols-outlined text-base">arrow_back</span>{" "}
        Retour
      </Link>
      <h1 className="text-2xl font-bold mt-2 flex items-center gap-2">
        {competition.name}
        {competition.url && (
          <a
            href={competition.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-on-surface-variant hover:text-primary transition-colors"
            title="Ouvrir les résultats"
          >
            <span className="material-symbols-outlined text-xl">open_in_new</span>
          </a>
        )}
      </h1>
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

      {/* Category navigation */}
      {groups.length > 1 && (
        <nav className="flex flex-wrap gap-2 mb-6">
          {groups.map(({ category }) => {
            const anchor = (category ?? "").replace(/\s+/g, "-");
            return (
              <a
                key={anchor}
                href={`#${anchor}`}
                className="text-sm px-3 py-1 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200"
              >
                {category ?? "—"}
              </a>
            );
          })}
        </nav>
      )}

      {groups.map((group) => {
        const anchor = (group.category ?? "").replace(/\s+/g, "-");
        const hasOverallResults = group.categoryResults.length > 0;
        const isMultiSegment = group.segmentCount > 1;

        return (
          <div key={anchor} id={anchor} className="mt-8 scroll-mt-16">
            {/* Category title */}
            <div className="mb-2">
              {group.category && (
                <h2 className="text-lg font-semibold">{group.category}</h2>
              )}
              {isMultiSegment && (
                <p className="text-xs text-gray-400">
                  {group.segmentCount} programmes (SP + PL)
                </p>
              )}
            </div>

            {/* Overall results table for this category */}
            {hasOverallResults && <OverallResultsTable group={group} />}

            {/* Segment detail tables */}
            {group.segments.map(({ segment, scores: segScores }) => (
              <div key={segment} className="mt-6">
                <div className="mb-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                    {segment}
                  </p>
                </div>
                <ScoreChart scores={segScores} />
                <SegmentScoresTable scores={segScores} />
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
