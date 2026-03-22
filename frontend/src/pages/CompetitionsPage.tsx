import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Competition, CreateCompetitionPayload, ImportResult, EnrichResult } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const inputClass =
  "bg-surface-container rounded-lg px-4 py-3 w-full focus:outline-none focus:ring-2 focus:ring-primary text-sm text-on-surface placeholder:text-on-surface-variant";

export default function CompetitionsPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const { data: competitions, isLoading, error } = useQuery({
    queryKey: ["competitions"],
    queryFn: api.competitions.list,
  });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateCompetitionPayload>({
    name: "",
    url: "",
    season: "",
    discipline: "",
  });

  const [importResults, setImportResults] = useState<Record<number, ImportResult>>({});
  const [enrichResults, setEnrichResults] = useState<Record<number, EnrichResult>>({});
  const [importingId, setImportingId] = useState<number | null>(null);
  const [enrichingId, setEnrichingId] = useState<number | null>(null);
  const [dismissedResults, setDismissedResults] = useState<Set<number>>(new Set());
  const [dismissedEnrich, setDismissedEnrich] = useState<Set<number>>(new Set());

  const createMutation = useMutation({
    mutationFn: api.competitions.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      setShowForm(false);
      setForm({ name: "", url: "", season: "", discipline: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.competitions.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["competitions"] }),
  });

  const importMutation = useMutation({
    mutationFn: (id: number) => {
      setImportingId(id);
      return api.competitions.import(id);
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      qc.invalidateQueries({ queryKey: ["scores"] });
      setImportResults((prev) => ({ ...prev, [result.competition_id]: result }));
      setDismissedResults((prev) => {
        const next = new Set(prev);
        next.delete(result.competition_id);
        return next;
      });
      setImportingId(null);
    },
    onError: () => {
      setImportingId(null);
    },
  });

  const reimportMutation = useMutation({
    mutationFn: (id: number) => {
      setImportingId(id);
      return api.competitions.reimport(id);
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      qc.invalidateQueries({ queryKey: ["scores"] });
      setImportResults((prev) => ({ ...prev, [result.competition_id]: result }));
      setDismissedResults((prev) => {
        const next = new Set(prev);
        next.delete(result.competition_id);
        return next;
      });
      setImportingId(null);
    },
    onError: () => {
      setImportingId(null);
    },
  });

  const enrichMutation = useMutation({
    mutationFn: (id: number) => {
      setEnrichingId(id);
      return api.competitions.enrich(id);
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["scores"] });
      setEnrichResults((prev) => ({ ...prev, [result.competition_id]: result }));
      setDismissedEnrich((prev) => {
        const next = new Set(prev);
        next.delete(result.competition_id);
        return next;
      });
      setEnrichingId(null);
    },
    onError: () => {
      setEnrichingId(null);
    },
  });

  return (
    <div>
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface">
            Compétitions
          </h1>
          <p className="text-sm text-on-surface-variant mt-0.5">
            Gérez vos compétitions et importez les résultats
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className="bg-primary text-on-primary rounded-lg py-2 px-4 text-xs font-bold active:scale-95 transition-all"
          >
            + Ajouter
          </button>
        )}
      </div>

      {/* Add competition form */}
      {showForm && (
        <form
          className="bg-surface-container-lowest rounded-xl shadow-sm p-6 mb-6"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate(form);
          }}
        >
          <h2 className="font-headline font-bold text-on-surface text-base mb-4">
            Nouvelle compétition
          </h2>
          <div className="space-y-3">
            <input
              className={inputClass}
              placeholder="Nom de la compétition"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <input
              className={inputClass}
              placeholder="URL du site de résultats"
              required
              type="url"
              value={form.url}
              onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
            />
            <div className="flex gap-3">
              <input
                className={inputClass}
                placeholder="Saison (ex: 2024-25)"
                value={form.season ?? ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, season: e.target.value }))
                }
              />
              <input
                className={inputClass}
                placeholder="Discipline (ex: Dames, Messieurs)"
                value={form.discipline ?? ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, discipline: e.target.value }))
                }
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-primary text-on-primary rounded-lg py-2 px-4 text-xs font-bold active:scale-95 transition-all disabled:opacity-50"
            >
              {createMutation.isPending ? "Enregistrement..." : "Enregistrer"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="border border-outline-variant text-on-surface-variant rounded-lg py-2 px-4 text-xs font-bold"
            >
              Annuler
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-error text-sm mt-3">
              {String(createMutation.error)}
            </p>
          )}
        </form>
      )}

      {/* Loading / error states */}
      {isLoading && (
        <p className="text-sm text-on-surface-variant">Chargement...</p>
      )}
      {error && (
        <p className="text-sm text-error">{String(error)}</p>
      )}

      {/* Empty state */}
      {competitions && competitions.length === 0 && (
        <p className="text-sm text-on-surface-variant">
          Aucune compétition. Ajoutez-en une pour commencer.
        </p>
      )}

      {/* Competition list */}
      <div className="space-y-3">
        {competitions?.map((c: Competition) => {
          const isImporting = importingId === c.id;
          const isEnriching = enrichingId === c.id;
          const result = importResults[c.id];
          const isDismissed = dismissedResults.has(c.id);
          const enrichResult = enrichResults[c.id];
          const isEnrichDismissed = dismissedEnrich.has(c.id);

          return (
            <div key={c.id}>
              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 flex items-center justify-between">
                {/* Left: name + meta */}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <Link
                      to={`/competitions/${c.id}`}
                      className="font-bold font-headline text-on-surface hover:text-primary transition-colors"
                    >
                      {c.name}
                    </Link>
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-on-surface-variant hover:text-primary transition-colors"
                      title="Ouvrir les résultats"
                    >
                      <span className="material-symbols-outlined text-[16px] leading-none">open_in_new</span>
                    </a>
                  </div>
                  <p className="text-xs text-on-surface-variant mt-1">
                    {[c.discipline, c.season, c.date].filter(Boolean).join(" · ")}
                  </p>
                </div>

                {/* Right: action buttons (admin only) */}
                {isAdmin && (
                  <div className="flex gap-2 ml-4 shrink-0">
                    <button
                      onClick={() => importMutation.mutate(c.id)}
                      disabled={isImporting}
                      className="bg-primary text-on-primary rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        download
                      </span>
                      {isImporting ? "Importation..." : "Importer"}
                    </button>
                    <button
                      onClick={() => {
                        if (
                          confirm(`Réimporter ${c.name} ? Les données existantes seront remplacées.`)
                        ) {
                          reimportMutation.mutate(c.id);
                        }
                      }}
                      disabled={isImporting}
                      className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        refresh
                      </span>
                      Réimporter
                    </button>
                    <button
                      onClick={() => enrichMutation.mutate(c.id)}
                      disabled={isEnriching || isImporting}
                      className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        description
                      </span>
                      {isEnriching ? "Enrichissement..." : "Enrichir PDF"}
                    </button>
                    <button
                      onClick={() => {
                        if (
                          confirm(`Supprimer "${c.name}" ?`)
                        ) {
                          deleteMutation.mutate(c.id);
                        }
                      }}
                      className="bg-error-container/50 text-on-error-container rounded-lg py-1.5 px-3 text-xs font-bold flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        delete
                      </span>
                      Supprimer
                    </button>
                  </div>
                )}
              </div>

              {/* Inline import result notification */}
              {result && !isDismissed && (
                <div className="px-5 pt-2">
                  {result.errors.length > 0 ? (
                    <div className="border-l-4 border-error pl-3 py-1">
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-2 h-2 rounded-full bg-error shrink-0" />
                        <p className="text-xs text-error font-medium">
                          Importé {result.scores_imported}/{result.scores_imported + result.errors.length} événements · {result.errors.length} erreur(s)
                        </p>
                        <button
                          onClick={() =>
                            setDismissedResults((prev) => new Set(prev).add(c.id))
                          }
                          className="text-on-surface-variant hover:text-on-surface transition-colors ml-auto"
                          aria-label="Fermer"
                        >
                          <span className="material-symbols-outlined text-sm leading-none">
                            close
                          </span>
                        </button>
                      </div>
                      <ul className="mt-1 space-y-0.5">
                        {result.errors.map((e, i) => (
                          <li key={i} className="text-xs text-error/80">
                            {e.skater} : {e.error}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-2 h-2 rounded-full bg-primary shrink-0" />
                      <p className="text-xs text-primary font-medium">
                        {result.events_found} événements · {result.scores_imported} scores importés · {result.scores_skipped} ignorés
                      </p>
                      <button
                        onClick={() =>
                          setDismissedResults((prev) => new Set(prev).add(c.id))
                        }
                        className="text-on-surface-variant hover:text-on-surface transition-colors"
                        aria-label="Fermer"
                      >
                        <span className="material-symbols-outlined text-sm leading-none">
                          close
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Inline enrich result notification */}
              {enrichResult && !isEnrichDismissed && (
                <div className="px-5 pt-2">
                  {enrichResult.errors.length > 0 ? (
                    <div className="border-l-4 border-error pl-3 py-1">
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-2 h-2 rounded-full bg-error shrink-0" />
                        <p className="text-xs text-error font-medium">
                          {enrichResult.pdfs_downloaded} PDF téléchargés · {enrichResult.scores_enriched} scores enrichis · {enrichResult.errors.length} erreur(s)
                        </p>
                        <button
                          onClick={() =>
                            setDismissedEnrich((prev) => new Set(prev).add(c.id))
                          }
                          className="text-on-surface-variant hover:text-on-surface transition-colors ml-auto"
                          aria-label="Fermer"
                        >
                          <span className="material-symbols-outlined text-sm leading-none">close</span>
                        </button>
                      </div>
                      <ul className="mt-1 space-y-0.5">
                        {enrichResult.errors.map((e, i) => (
                          <li key={i} className="text-xs text-error/80">
                            {e.file} : {e.error}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="inline-block w-2 h-2 rounded-full bg-primary shrink-0" />
                      <p className="text-xs text-primary font-medium">
                        {enrichResult.pdfs_downloaded} PDF téléchargés · {enrichResult.scores_enriched} scores enrichis
                      </p>
                      <button
                        onClick={() =>
                          setDismissedEnrich((prev) => new Set(prev).add(c.id))
                        }
                        className="text-on-surface-variant hover:text-on-surface transition-colors"
                        aria-label="Fermer"
                      >
                        <span className="material-symbols-outlined text-sm leading-none">close</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
