import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function SetupPage() {
  const { setup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    club_name: "",
    club_short: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }
    setLoading(true);
    try {
      await setup(form);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err.message || "Erreur lors de la configuration");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="material-symbols-outlined text-primary text-5xl">
            sports_score
          </span>
          <h1 className="font-headline font-bold text-on-surface text-xl mt-2">
            Configuration initiale
          </h1>
          <p className="text-on-surface-variant text-sm mt-1">
            Créez le compte administrateur et configurez votre club
          </p>
        </div>

        <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
          <form onSubmit={handleSubmit} className="space-y-4">
            <h2 className="font-headline font-bold text-on-surface text-sm">
              Compte administrateur
            </h2>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Email
              </label>
              <input
                type="email"
                required
                value={form.email}
                onChange={set("email")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Mot de passe
              </label>
              <input
                type="password"
                required
                value={form.password}
                onChange={set("password")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="8 caractères minimum"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Nom affiché
              </label>
              <input
                type="text"
                required
                value={form.display_name}
                onChange={set("display_name")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Coach Dupont"
              />
            </div>

            <h2 className="font-headline font-bold text-on-surface text-sm pt-2">
              Club
            </h2>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Nom du club
              </label>
              <input
                type="text"
                required
                value={form.club_name}
                onChange={set("club_name")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Toulouse Club Patinage"
              />
            </div>
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1">
                Abréviation
              </label>
              <input
                type="text"
                required
                value={form.club_short}
                onChange={set("club_short")}
                className="w-full px-3 py-2 bg-surface-container-low rounded-xl text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="TOUCP"
              />
            </div>

            {error && (
              <p className="text-error text-xs font-medium">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-primary text-on-primary rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Configuration..." : "Démarrer"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
