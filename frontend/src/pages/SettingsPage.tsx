import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type UserRecord } from "../api/client";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
  });
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
    </div>
  );
}
