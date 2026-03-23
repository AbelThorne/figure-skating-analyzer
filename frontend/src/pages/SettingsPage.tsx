import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import yaml from "js-yaml";
import { api, type UserRecord, type JobInfo } from "../api/client";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: config, dataUpdatedAt } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
  });
  const logoSrc = config?.logo_url ? `${config.logo_url}?v=${dataUpdatedAt}` : "";
  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: api.users.list,
  });
  const { data: domains = [] } = useQuery({
    queryKey: ["domains"],
    queryFn: api.domains.list,
  });

  // --- Club settings ---
  const [clubName, setClubName] = useState("");
  const [clubShort, setClubShort] = useState("");
  const [clubSaved, setClubSaved] = useState(false);

  useEffect(() => {
    if (config) {
      setClubName(config.club_name || "");
      setClubShort(config.club_short || "");
    }
  }, [config]);

  const updateConfig = useMutation({
    mutationFn: () =>
      api.config.update({ club_name: clubName, club_short: clubShort }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
      setClubSaved(true);
      setTimeout(() => setClubSaved(false), 2000);
    },
  });

  // --- Logo upload ---
  const fileRef = useRef<HTMLInputElement>(null);
  const uploadLogo = useMutation({
    mutationFn: (file: File) => api.config.uploadLogo(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config"] });
    },
  });

  // --- Users ---
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({
    email: "",
    display_name: "",
    role: "reader",
    password: "",
  });

  const createUser = useMutation({
    mutationFn: () => api.users.create(newUser),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowAddUser(false);
      setNewUser({ email: "", display_name: "", role: "reader", password: "" });
    },
  });

  const toggleActive = useMutation({
    mutationFn: (user: UserRecord) =>
      api.users.update(user.id, { is_active: !user.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const deleteUser = useMutation({
    mutationFn: (id: string) => api.users.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  // --- Domains ---
  const [newDomain, setNewDomain] = useState("");

  const addDomain = useMutation({
    mutationFn: () => api.domains.create(newDomain),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["domains"] });
      setNewDomain("");
    },
  });

  const removeDomain = useMutation({
    mutationFn: (id: string) => api.domains.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["domains"] }),
  });

  // --- Bulk import ---
  interface Lot {
    name: string;
    urls: string[];
    season?: string;
    discipline?: string;
  }
  const [lots, setLots] = useState<Lot[]>([]);
  const [bulkJobs, setBulkJobs] = useState<Record<string, JobInfo>>({});
  // Track which lot names have active jobs
  const [lotJobIds, setLotJobIds] = useState<Record<string, string[]>>({});
  const yamlRef = useRef<HTMLInputElement>(null);

  const handleYamlUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = yaml.load(e.target?.result as string) as Record<string, unknown>[];
        const newLots: Lot[] = parsed.map((item: Record<string, unknown>) => ({
          name: (item.name as string) || "Sans nom",
          urls: (item.urls as string[]) || [],
          season: item.season as string | undefined,
          discipline: item.discipline as string | undefined,
        }));
        setLots(newLots);
        setBulkJobs({});
        setLotJobIds({});
      } catch {
        alert("Fichier YAML invalide");
      }
    };
    reader.readAsText(file);
  };

  const bulkImportMutation = useMutation({
    mutationFn: (params: { lot: Lot; enrich: boolean }) =>
      api.competitions.bulkImport({
        lot_name: params.lot.name,
        urls: params.lot.urls,
        enrich: params.enrich,
        season: params.lot.season,
        discipline: params.lot.discipline,
      }),
    onSuccess: (result, variables) => {
      // Store job IDs for this lot and seed them as queued
      setLotJobIds((prev) => ({ ...prev, [variables.lot.name]: result.job_ids }));
      const newJobs: Record<string, JobInfo> = {};
      for (const jid of result.job_ids) {
        newJobs[jid] = { id: jid, type: "import", competition_id: 0, status: "queued", result: null, error: null, created_at: "" };
      }
      setBulkJobs((prev) => ({ ...prev, ...newJobs }));
    },
  });

  // Poll bulk jobs
  const bulkPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bulkJobsRef = useRef(bulkJobs);
  bulkJobsRef.current = bulkJobs;

  const pollBulkJobs = useCallback(async () => {
    const current = bulkJobsRef.current;
    const activeIds = Object.entries(current)
      .filter(([, j]) => j.status === "queued" || j.status === "running")
      .map(([id]) => id);

    if (activeIds.length === 0) return;

    const updates: Record<string, JobInfo> = {};
    let anyChanged = false;
    for (const jobId of activeIds) {
      try {
        const job = await api.jobs.get(jobId);
        updates[jobId] = job;
        if (job.status !== current[jobId]?.status) anyChanged = true;
        if (job.status === "completed" || job.status === "failed") {
          anyChanged = true;
          qc.invalidateQueries({ queryKey: ["competitions"] });
          qc.invalidateQueries({ queryKey: ["scores"] });
        }
      } catch {
        updates[jobId] = { ...current[jobId], status: "failed", error: "Perdu le contact" };
        anyChanged = true;
      }
    }
    if (anyChanged) {
      setBulkJobs((prev) => ({ ...prev, ...updates }));
    }
  }, [qc]);

  useEffect(() => {
    const hasActive = Object.values(bulkJobs).some(
      (j) => j.status === "queued" || j.status === "running"
    );
    if (!hasActive) {
      if (bulkPollRef.current) {
        clearInterval(bulkPollRef.current);
        bulkPollRef.current = null;
      }
      return;
    }
    if (!bulkPollRef.current) {
      bulkPollRef.current = setInterval(pollBulkJobs, 2000);
    }
    return () => {
      if (bulkPollRef.current) {
        clearInterval(bulkPollRef.current);
        bulkPollRef.current = null;
      }
    };
  }, [bulkJobs, pollBulkJobs]);

  // Helper: submit all lots
  const importAllLots = (enrich: boolean) => {
    for (const lot of lots) {
      bulkImportMutation.mutate({ lot, enrich });
    }
  };

  const inputCls =
    "w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary";

  return (
    <div className="space-y-8">
      {/* Club settings */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-4">
          Paramètres du club
        </h2>
        <div className="grid grid-cols-2 gap-4 max-w-lg">
          <div>
            <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
              Nom du club
            </label>
            <input
              value={clubName}
              onChange={(e) => setClubName(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
              Abréviation
            </label>
            <input
              value={clubShort}
              onChange={(e) => setClubShort(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>
        <button
          onClick={() => updateConfig.mutate()}
          className="mt-4 px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
        >
          {clubSaved ? "Enregistré ✓" : "Enregistrer"}
        </button>

        {/* Logo upload */}
        <div className="mt-6 pt-5 border-t border-outline-variant/30">
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-2">
            Logo du club
          </label>
          <div className="flex items-center gap-4">
            {logoSrc ? (
              <img
                src={logoSrc}
                alt="Logo"
                className="w-12 h-12 object-contain rounded-lg bg-surface-container-low p-1"
              />
            ) : (
              <div className="w-12 h-12 rounded-lg bg-surface-container-low flex items-center justify-center">
                <span className="material-symbols-outlined text-on-surface-variant">image</span>
              </div>
            )}
            <div>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadLogo.mutate(file);
                }}
              />
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploadLogo.isPending}
                className="px-3 py-1.5 bg-surface-container text-on-surface-variant rounded-xl text-xs font-bold hover:bg-surface-container-high transition-colors disabled:opacity-50"
              >
                {uploadLogo.isPending ? "Envoi..." : "Changer le logo"}
              </button>
              {uploadLogo.isError && (
                <p className="text-error text-xs mt-1">{String(uploadLogo.error)}</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Users */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-headline font-bold text-on-surface text-lg">
            Utilisateurs
          </h2>
          <button
            onClick={() => setShowAddUser(true)}
            className="px-3 py-1.5 bg-primary text-on-primary rounded-xl text-xs font-bold hover:bg-primary/90 transition-colors flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            Ajouter
          </button>
        </div>

        <div className="space-y-2">
          {users.map((u) => (
            <div
              key={u.id}
              className="flex items-center justify-between p-3 bg-surface-container-low rounded-xl"
            >
              <div>
                <span className="font-medium text-on-surface text-sm">
                  {u.display_name}
                </span>
                <span className="text-on-surface-variant text-xs ml-2">
                  {u.email}
                </span>
                <span
                  className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                    u.role === "admin"
                      ? "bg-primary-container text-on-primary-container"
                      : "bg-surface-container text-on-surface-variant"
                  }`}
                >
                  {u.role === "admin" ? "Admin" : "Lecteur"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleActive.mutate(u)}
                  className={`text-xs px-2 py-1 rounded-lg ${
                    u.is_active ? "text-primary" : "text-error"
                  }`}
                >
                  {u.is_active ? "Actif" : "Désactivé"}
                </button>
                <button
                  onClick={() => {
                    if (confirm("Supprimer cet utilisateur ?"))
                      deleteUser.mutate(u.id);
                  }}
                  className="text-error text-xs hover:bg-error-container rounded-lg px-2 py-1"
                >
                  <span className="material-symbols-outlined text-sm">
                    delete
                  </span>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add user form */}
        {showAddUser && (
          <div className="mt-4 p-4 bg-surface-container rounded-xl space-y-3">
            <input
              placeholder="Email"
              value={newUser.email}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, email: e.target.value }))
              }
              className={inputCls}
            />
            <input
              placeholder="Nom affiché"
              value={newUser.display_name}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, display_name: e.target.value }))
              }
              className={inputCls}
            />
            <select
              value={newUser.role}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, role: e.target.value }))
              }
              className={inputCls}
            >
              <option value="reader">Lecteur</option>
              <option value="admin">Administrateur</option>
            </select>
            <input
              type="password"
              placeholder="Mot de passe (optionnel pour OAuth)"
              value={newUser.password}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, password: e.target.value }))
              }
              className={inputCls}
            />
            <div className="flex gap-2">
              <button
                onClick={() => createUser.mutate()}
                className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
              >
                Créer
              </button>
              <button
                onClick={() => setShowAddUser(false)}
                className="px-4 py-2 text-on-surface-variant text-sm"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Domains */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-4">
          Domaines autorisés
        </h2>
        <p className="text-on-surface-variant text-xs mb-3">
          Les utilisateurs avec un email correspondant à ces domaines peuvent se
          connecter via Google et seront automatiquement créés en tant que
          lecteurs.
        </p>
        <div className="space-y-2 mb-4">
          {domains.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between p-2 bg-surface-container-low rounded-xl"
            >
              <span className="text-on-surface text-sm font-mono">
                @{d.domain}
              </span>
              <button
                onClick={() => removeDomain.mutate(d.id)}
                className="text-error text-xs hover:bg-error-container rounded-lg px-2 py-1"
              >
                <span className="material-symbols-outlined text-sm">
                  delete
                </span>
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            placeholder="exemple.fr"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            className={inputCls + " max-w-xs"}
          />
          <button
            onClick={() => addDomain.mutate()}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
          >
            Ajouter
          </button>
        </div>
      </section>

      {/* Bulk import */}
      <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
        <h2 className="font-headline font-bold text-on-surface text-lg mb-4">
          Import par lots
        </h2>
        <p className="text-on-surface-variant text-xs mb-3">
          Chargez un fichier YAML contenant des lots de compétitions à importer.
          Format attendu :
        </p>
        <pre className="text-xs text-on-surface-variant bg-surface-container-low rounded-xl p-3 mb-4 font-mono overflow-x-auto">
{`- name: "CSNPA Automne 2025"
  season: "2025-2026"
  urls:
    - https://example.com/comp1/index.htm
    - https://example.com/comp2/index.htm

- name: "Coupes régionales 2026"
  urls:
    - https://example.com/comp3/index.htm`}
        </pre>

        <div className="mb-4">
          <input
            ref={yamlRef}
            type="file"
            accept=".yaml,.yml"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleYamlUpload(file);
            }}
          />
          <button
            onClick={() => yamlRef.current?.click()}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-sm">upload_file</span>
            Charger un fichier YAML
          </button>
        </div>

        {lots.length > 0 && (
          <div className="space-y-3">
            {/* Global actions */}
            <div className="flex gap-2 mb-2">
              <button
                onClick={() => importAllLots(false)}
                disabled={bulkImportMutation.isPending}
                className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-sm">download</span>
                Tout importer
              </button>
              <button
                onClick={() => importAllLots(true)}
                disabled={bulkImportMutation.isPending}
                className="px-4 py-2 bg-surface-container text-on-surface-variant rounded-xl text-sm font-bold hover:bg-surface-container-high transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-sm">description</span>
                Tout importer + PDF
              </button>
            </div>

            {lots.map((lot) => {
              const jobIds = lotJobIds[lot.name] || [];
              const jobs = jobIds.map((jid) => bulkJobs[jid]).filter(Boolean);
              const hasActiveJobs = jobs.some((j) => j.status === "queued" || j.status === "running");
              const completedJobs = jobs.filter((j) => j.status === "completed" || j.status === "failed");
              const failedJobs = jobs.filter((j) => j.status === "failed");

              return (
                <div
                  key={lot.name}
                  className="p-4 bg-surface-container-low rounded-xl"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-on-surface text-sm">
                        {lot.name}
                      </span>
                      <span className="text-on-surface-variant text-xs ml-2">
                        {lot.urls.length} compétition{lot.urls.length > 1 ? "s" : ""}
                        {lot.season && ` · ${lot.season}`}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => bulkImportMutation.mutate({ lot, enrich: false })}
                        disabled={hasActiveJobs}
                        className="px-3 py-1.5 bg-primary text-on-primary rounded-xl text-xs font-bold hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-sm">download</span>
                        {hasActiveJobs ? "En cours..." : "Importer"}
                      </button>
                      <button
                        onClick={() => bulkImportMutation.mutate({ lot, enrich: true })}
                        disabled={hasActiveJobs}
                        className="px-3 py-1.5 bg-surface-container text-on-surface-variant rounded-xl text-xs font-bold hover:bg-surface-container-high transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-sm">description</span>
                        {hasActiveJobs ? "En cours..." : "Importer + PDF"}
                      </button>
                    </div>
                  </div>

                  {/* Progress / Result */}
                  {jobs.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-outline-variant/30">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-block w-2 h-2 rounded-full ${
                            hasActiveJobs
                              ? "bg-on-surface-variant animate-pulse"
                              : failedJobs.length > 0
                                ? "bg-error"
                                : "bg-primary"
                          }`}
                        />
                        <span className="text-xs font-medium text-on-surface">
                          {hasActiveJobs
                            ? `${completedJobs.length}/${jobs.length} tâches terminées`
                            : failedJobs.length > 0
                              ? `${completedJobs.length - failedJobs.length}/${jobs.length} réussies · ${failedJobs.length} erreur(s)`
                              : `${completedJobs.length}/${jobs.length} tâches terminées`}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
