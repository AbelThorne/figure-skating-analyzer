import { useState } from "react";
import { api, setAccessToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function ProfilePage() {
  const { user, updateUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!user) return null;

  if (!user.has_password) {
    return (
      <div>
        <h1 className="font-headline text-2xl font-bold text-on-surface mb-4">
          Mon compte
        </h1>
        <p className="text-sm text-on-surface-variant">
          Vous utilisez Google pour vous connecter. La modification du mot de passe n'est pas disponible.
        </p>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    if (newPassword.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }

    setLoading(true);
    try {
      const resp = await api.auth.changePassword(currentPassword, newPassword);
      setAccessToken(resp.access_token);
      updateUser(resp.user);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("401")) {
        setError("Mot de passe actuel incorrect");
      } else {
        setError("Une erreur est survenue");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="font-headline text-2xl font-bold text-on-surface mb-6">
        Mon compte
      </h1>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6 max-w-md">
        <h2 className="font-headline font-bold text-on-surface text-sm mb-4">
          Changer le mot de passe
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Mot de passe actuel
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Nouveau mot de passe
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-on-surface-variant mb-1">
              Confirmer le nouveau mot de passe
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
              required
            />
          </div>

          {error && (
            <p className="text-xs text-error">{error}</p>
          )}
          {success && (
            <p className="text-xs text-primary font-semibold">
              Mot de passe modifié avec succès
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold disabled:opacity-50"
          >
            {loading ? "..." : "Changer le mot de passe"}
          </button>
        </form>
      </div>
    </div>
  );
}
