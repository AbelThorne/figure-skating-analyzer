import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Competition, CreateCompetitionPayload, ImportResult } from "../api/client";

const inputClass =
  "bg-surface-container rounded-lg px-4 py-3 w-full focus:outline-none focus:ring-2 focus:ring-primary text-sm text-on-surface placeholder:text-on-surface-variant";

export default function CompetitionsPage() {
  const qc = useQueryClient();

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
  const [importingId, setImportingId] = useState<number | null>(null);
  const [dismissedResults, setDismissedResults] = useState<Set<number>>(new Set());

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
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-primary text-on-primary rounded-lg py-2 px-4 text-xs font-bold active:scale-95 transition-all"
        >
          + Ajouter
        </button>
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
          const result = importResults[c.id];
          const isDismissed = dismissedResults.has(c.id);

          return (
            <div key={c.id}>
              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5 flex items-center justify-between">
                {/* Left: name + meta */}
                <div className="min-w-0">
                  <Link
                    to={`/competitions/${c.id}`}
                    className="font-bold font-headline text-on-surface hover:text-primary transition-colors"
                  >
                    {c.name}
                  </Link>
                  <p className="text-xs text-on-surface-variant mt-1">
                    {[c.discipline, c.season, c.date].filter(Boolean).join(" · ")}
                  </p>
                </div>

                {/* Right: action buttons */}
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
              </div>

              {/* Inline import result notification */}
              {result && !isDismissed && (
                <div className="flex items-center gap-2 px-5 pt-2">
                  <p className="text-xs text-primary font-medium">
                    {result.scores_imported} scores importés · {result.scores_skipped} ignorés
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
          );
        })}
      </div>
    </div>
  );
}
