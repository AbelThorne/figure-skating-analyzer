import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type TeamScoresResponse, type TeamClubResult, type TeamSkaterEntry } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import MediansModal from "./MediansModal";

function SkaterRow({ s }: { s: TeamSkaterEntry }) {
  return (
    <tr className={`border-t border-gray-100 ${s.is_remplacant ? "opacity-50" : ""}`}>
      <td className="px-3 py-1.5">
        <Link
          to={`/patineurs/${s.skater_id}/analyse`}
          className="hover:text-primary transition-colors"
        >
          {s.skater_name}
        </Link>
        {s.is_remplacant && (
          <span className="ml-2 text-[10px] font-bold uppercase tracking-wider bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full">
            Rempl.
          </span>
        )}
      </td>
      <td className="px-3 py-1.5 text-gray-500 text-xs max-w-[160px] truncate">{s.category ?? "—"}</td>
      <td className="px-3 py-1.5 text-right font-mono">{s.total_score?.toFixed(2) ?? "—"}</td>
      <td className="px-3 py-1.5 text-right font-mono text-gray-400 text-xs">
        {s.median_value?.toFixed(2) ?? "—"}
      </td>
      <td className="px-3 py-1.5 text-right font-mono font-bold">
        {s.is_remplacant ? (
          <span className="text-gray-400">—</span>
        ) : (
          s.points?.toFixed(2) ?? "—"
        )}
      </td>
    </tr>
  );
}

function ClubCard({ club }: { club: TeamClubResult }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
      >
        <span className={`w-8 h-8 flex items-center justify-center rounded-full font-bold text-sm ${
          club.rank === 1 ? "bg-amber-100 text-amber-800" :
          club.rank === 2 ? "bg-gray-200 text-gray-700" :
          club.rank === 3 ? "bg-orange-100 text-orange-800" :
          "bg-gray-100 text-gray-600"
        }`}>
          {club.rank}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-on-surface truncate">{club.club}</p>
          <p className="text-xs text-on-surface-variant">
            {club.skater_count} patineur{club.skater_count > 1 ? "s" : ""} comptabilise{club.skater_count > 1 ? "s" : ""}
          </p>
        </div>
        <span className="font-mono font-bold text-lg text-primary">
          {club.total_points.toFixed(2)}
        </span>
        <span className="material-symbols-outlined text-gray-400 transition-transform" style={{
          transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
        }}>
          expand_more
        </span>
      </button>

      {expanded && (
        <div className="border-t overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2">Patineur</th>
                <th className="px-3 py-2">Categorie</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Mediane</th>
                <th className="px-3 py-2 text-right">Points</th>
              </tr>
            </thead>
            <tbody>
              {club.skaters.map((s) => (
                <SkaterRow key={s.score_id} s={s} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function TeamScoresTab({ competitionId }: { competitionId: number }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";
  const [showMedians, setShowMedians] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["team-scores", competitionId],
    queryFn: () => api.competitions.teamScores(competitionId),
  });

  const saveMedians = useMutation({
    mutationFn: (medians: Record<string, Record<string, number>>) =>
      api.competitions.updateTeamMedians(competitionId, medians),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-scores", competitionId] });
      setShowMedians(false);
    },
  });

  if (isLoading) return <p className="text-gray-500 py-4">Chargement...</p>;
  if (error) return <p className="text-red-600 py-4">Erreur lors du chargement des scores.</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Classement par club</h2>
          <p className="text-xs text-on-surface-variant">
            Medianes : {data.medians_source === "competition" ? "specifiques a cette competition" : "valeurs par defaut de la saison"}
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowMedians(true)}
            className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-xl bg-surface-container hover:bg-surface-container-high transition-colors text-on-surface-variant"
          >
            <span className="material-symbols-outlined text-base">tune</span>
            Medianes
          </button>
        )}
      </div>

      {/* Unmapped categories warning */}
      {data.unmapped.length > 0 && (
        <div className="bg-amber-50 text-amber-800 text-sm px-4 py-3 rounded-xl">
          <p className="font-semibold mb-1">Categories sans mediane associee :</p>
          <ul className="list-disc list-inside text-xs">
            {data.unmapped.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Club rankings */}
      {data.clubs.length === 0 ? (
        <p className="text-gray-500">Aucun resultat disponible.</p>
      ) : (
        <div className="space-y-3">
          {data.clubs.map((club) => (
            <ClubCard key={club.club} club={club} />
          ))}
        </div>
      )}

      {/* Category breakdown */}
      {data.categories.length > 0 && (
        <div>
          <h3 className="text-md font-semibold mb-3 mt-8">Detail par categorie</h3>
          <div className="space-y-4">
            {data.categories.map((cat) => (
              <div key={cat.category} className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                  <span className="font-medium text-sm">{cat.category}</span>
                  <span className="text-xs text-gray-500">
                    {cat.division && `${cat.division} · `}
                    Mediane : {cat.median_value?.toFixed(2) ?? "—"}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs text-gray-500 uppercase tracking-wider">
                      <tr>
                        <th className="px-3 py-2">Rang</th>
                        <th className="px-3 py-2">Patineur</th>
                        <th className="px-3 py-2">Club</th>
                        <th className="px-3 py-2 text-right">Score</th>
                        <th className="px-3 py-2 text-right">Points</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cat.skaters
                        .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
                        .map((s) => (
                          <tr key={s.score_id} className={`border-t border-gray-100 ${s.is_remplacant ? "opacity-50" : ""}`}>
                            <td className="px-3 py-1.5">{s.rank ?? "—"}</td>
                            <td className="px-3 py-1.5">
                              <Link
                                to={`/patineurs/${s.skater_id}/analyse`}
                                className="hover:text-primary transition-colors"
                              >
                                {s.skater_name}
                              </Link>
                              {s.is_remplacant && (
                                <span className="ml-2 text-[10px] font-bold uppercase tracking-wider bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full">
                                  Rempl.
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-1.5 text-gray-600 max-w-[160px] truncate">{s.club}</td>
                            <td className="px-3 py-1.5 text-right font-mono">{s.total_score?.toFixed(2) ?? "—"}</td>
                            <td className="px-3 py-1.5 text-right font-mono font-bold">
                              {s.is_remplacant ? "—" : (s.points?.toFixed(2) ?? "—")}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Medians modal */}
      {showMedians && (
        <MediansModal
          medians={data.medians}
          onSave={(m) => saveMedians.mutate(m)}
          onClose={() => setShowMedians(false)}
          saving={saveMedians.isPending}
          title="Medianes de la competition"
        />
      )}
    </div>
  );
}
