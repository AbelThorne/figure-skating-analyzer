import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Competition, CreateCompetitionPayload, JobInfo, COMPETITION_TYPES } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useJobs } from "../contexts/JobContext";

const inputClass =
  "bg-surface-container rounded-lg px-4 py-3 w-full focus:outline-none focus:ring-2 focus:ring-primary text-sm text-on-surface placeholder:text-on-surface-variant";

export default function CompetitionsPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const {
    activeJobs,
    trackJob,
    importResults,
    enrichResults,
    dismissedResults,
    dismissedEnrich,
    dismissImportResult,
    dismissEnrichResult,
  } = useJobs();

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

  const [filterSeason, setFilterSeason] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("date-desc");
  const [showUnconfirmedOnly, setShowUnconfirmedOnly] = useState(false);

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
    mutationFn: (id: number) => api.competitions.import(id),
    onSuccess: (job: JobInfo) => trackJob(job),
  });

  const reimportMutation = useMutation({
    mutationFn: (id: number) => api.competitions.reimport(id),
    onSuccess: (job: JobInfo) => trackJob(job),
  });

  const enrichMutation = useMutation({
    mutationFn: (id: number) => api.competitions.enrich(id),
    onSuccess: (job: JobInfo) => trackJob(job),
  });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<{
    city: string;
    country: string;
    competition_type: string;
    season: string;
  }>({ city: "", country: "", competition_type: "", season: "" });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, string> }) =>
      api.competitions.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      setEditingId(null);
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (id: number) => api.competitions.confirmMetadata(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["competitions"] }),
  });

  // Maps competition_id → list of active job IDs
  const competitionJobs: Record<number, string[]> = {};
  for (const [jobId, job] of Object.entries(activeJobs)) {
    if (job.status === "queued" || job.status === "running") {
      if (!competitionJobs[job.competition_id]) {
        competitionJobs[job.competition_id] = [];
      }
      competitionJobs[job.competition_id].push(jobId);
    }
  }

  const seasons = Array.from(
    new Set(competitions?.map((c) => c.season).filter(Boolean) as string[])
  ).sort().reverse();

  const filteredCompetitions = (competitions ?? [])
    .filter((c) => filterSeason === "all" || c.season === filterSeason)
    .filter((c) => filterType === "all" || c.competition_type === filterType)
    .filter((c) => !showUnconfirmedOnly || !c.metadata_confirmed)
    .sort((a, b) => {
      switch (sortBy) {
        case "date-asc":
          return (a.date ?? "").localeCompare(b.date ?? "");
        case "date-desc":
          return (b.date ?? "").localeCompare(a.date ?? "");
        case "city-asc":
          return (a.city ?? "").localeCompare(b.city ?? "");
        case "city-desc":
          return (b.city ?? "").localeCompare(a.city ?? "");
        case "country-asc":
          return (a.country ?? "").localeCompare(b.country ?? "");
        default:
          return (b.date ?? "").localeCompare(a.date ?? "");
      }
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

      {/* Filter bar */}
      {competitions && competitions.length > 0 && (
        <div className="bg-surface-container-lowest rounded-xl shadow-sm p-4 mb-4 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Saison</span>
            <select
              value={filterSeason}
              onChange={(e) => setFilterSeason(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">Toutes</option>
              {seasons.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Type</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">Tous</option>
              {Object.entries(COMPETITION_TYPES).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">Trier par</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-1.5 text-sm text-on-surface border-none focus:ring-2 focus:ring-primary"
            >
              <option value="date-desc">Date ↓</option>
              <option value="date-asc">Date ↑</option>
              <option value="city-asc">Ville A→Z</option>
              <option value="city-desc">Ville Z→A</option>
              <option value="country-asc">Pays A→Z</option>
            </select>
          </div>
          <label className="ml-auto flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer">
            <input
              type="checkbox"
              checked={showUnconfirmedOnly}
              onChange={(e) => setShowUnconfirmedOnly(e.target.checked)}
              className="accent-error"
            />
            À vérifier uniquement
          </label>
        </div>
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
        {filteredCompetitions.map((c: Competition) => {
          const compJobs = competitionJobs[c.id] || [];
          const activeJobTypes = compJobs.map((jid) => activeJobs[jid]?.type);
          const isImporting = activeJobTypes.includes("import") || activeJobTypes.includes("reimport");
          const isEnriching = activeJobTypes.includes("enrich");

          const importJobStatus = compJobs
            .map((jid) => activeJobs[jid])
            .find((j) => j?.type === "import" || j?.type === "reimport")?.status;
          const enrichJobStatus = compJobs
            .map((jid) => activeJobs[jid])
            .find((j) => j?.type === "enrich")?.status;

          const result = importResults[c.id];
          const isDismissed = dismissedResults.has(c.id);
          const enrichResult = enrichResults[c.id];
          const isEnrichDismissed = dismissedEnrich.has(c.id);

          return (
            <div key={c.id}>
              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 flex items-center justify-between">
                {/* Left: name + meta */}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
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
                    {c.competition_type && (
                      <span className="bg-surface-container text-on-surface-variant text-[10px] font-semibold px-2 py-0.5 rounded-full">
                        {COMPETITION_TYPES[c.competition_type] ?? c.competition_type}
                      </span>
                    )}
                    {!c.metadata_confirmed && (
                      <span className="bg-error-container/50 text-on-error-container text-[10px] font-semibold px-2 py-0.5 rounded-full">
                        À vérifier
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-on-surface-variant mt-1">
                    {[
                      c.city && c.country ? `${c.city}, ${c.country}` : c.city || c.country,
                      c.date ? new Date(c.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }) : null,
                      c.season,
                    ].filter(Boolean).join(" · ")}
                  </p>
                </div>

                {/* Right: action buttons (admin only) */}
                {isAdmin && (
                  <div className="flex gap-2 ml-4 shrink-0">
                    {!c.metadata_confirmed && (
                      <button
                        onClick={() => confirmMutation.mutate(c.id)}
                        className="bg-primary text-on-primary rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-base leading-none">check</span>
                        Valider
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setEditingId(editingId === c.id ? null : c.id);
                        setEditForm({
                          city: c.city ?? "",
                          country: c.country ?? "",
                          competition_type: c.competition_type ?? "",
                          season: c.season ?? "",
                        });
                      }}
                      className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">edit</span>
                      Modifier
                    </button>
                    <button
                      onClick={() => importMutation.mutate(c.id)}
                      disabled={isImporting}
                      className="bg-primary text-on-primary rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        download
                      </span>
                      {importJobStatus === "queued"
                        ? "En file d'attente"
                        : importJobStatus === "running"
                          ? "Importation..."
                          : "Importer"}
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
                      disabled={isEnriching}
                      className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-3 text-xs font-bold active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-base leading-none">
                        description
                      </span>
                      {enrichJobStatus === "queued"
                        ? "En file d'attente"
                        : enrichJobStatus === "running"
                          ? "Enrichissement..."
                          : "Enrichir PDF"}
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

              {/* Inline metadata editor */}
              {editingId === c.id && (
                <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 mt-1 border-l-[3px] border-primary">
                  <div className="flex gap-3 flex-wrap">
                    <div className="flex-1 min-w-[150px]">
                      <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Type</label>
                      <select
                        value={editForm.competition_type}
                        onChange={(e) => setEditForm((f) => ({ ...f, competition_type: e.target.value }))}
                        className={inputClass}
                      >
                        <option value="">—</option>
                        {Object.entries(COMPETITION_TYPES).map(([code, label]) => (
                          <option key={code} value={code}>{label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex-1 min-w-[150px]">
                      <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Ville</label>
                      <input
                        value={editForm.city}
                        onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value }))}
                        className={inputClass}
                        placeholder="Ville"
                      />
                    </div>
                    <div className="flex-1 min-w-[150px]">
                      <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Pays</label>
                      <input
                        value={editForm.country}
                        onChange={(e) => setEditForm((f) => ({ ...f, country: e.target.value }))}
                        className={inputClass}
                        placeholder="Pays"
                      />
                    </div>
                    <div className="flex-1 min-w-[120px]">
                      <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Saison</label>
                      <input
                        value={editForm.season}
                        onChange={(e) => setEditForm((f) => ({ ...f, season: e.target.value }))}
                        className={inputClass}
                        placeholder="2025-2026"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3 justify-end">
                    <button
                      onClick={() => setEditingId(null)}
                      className="bg-surface-container text-on-surface-variant rounded-lg py-1.5 px-4 text-xs font-bold"
                    >
                      Annuler
                    </button>
                    <button
                      onClick={() => updateMutation.mutate({ id: c.id, data: editForm })}
                      disabled={updateMutation.isPending}
                      className="bg-primary text-on-primary rounded-lg py-1.5 px-4 text-xs font-bold active:scale-95 transition-all disabled:opacity-50"
                    >
                      {updateMutation.isPending ? "Enregistrement..." : "Enregistrer"}
                    </button>
                  </div>
                </div>
              )}

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
                            dismissImportResult(c.id)
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
                          dismissImportResult(c.id)
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
                            dismissEnrichResult(c.id)
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
                          dismissEnrichResult(c.id)
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
