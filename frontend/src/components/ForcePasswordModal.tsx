import { useState, useEffect } from "react";
import { api, setAccessToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface Props {
  onClose: () => void;
}

export default function ForcePasswordModal({ onClose }: Props) {
  const { user, updateUser } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  if (!user) return null;

  // OAuth-only users: just show info and close button
  if (!user.has_password) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <div className="absolute inset-0 bg-on-surface/40" />
        <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
          <h2 className="font-headline font-bold text-on-surface text-base mb-2">
            Changement de mot de passe requis
          </h2>
          <p className="text-sm text-on-surface-variant mb-4">
            Vous utilisez Google pour vous connecter. La modification du mot de passe n'est pas disponible.
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
          >
            Fermer
          </button>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

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
      onClose();
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-on-surface/40" />
      <div className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-headline font-bold text-on-surface text-base">
            Changement de mot de passe requis
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>
        <p className="text-sm text-on-surface-variant mb-4">
          Un administrateur a demandé que vous changiez votre mot de passe.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            placeholder="Mot de passe actuel"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />
          <input
            type="password"
            placeholder="Nouveau mot de passe"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />
          <input
            type="password"
            placeholder="Confirmer le nouveau mot de passe"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="bg-surface-container rounded-lg px-3 py-2 w-full text-sm text-on-surface focus:ring-2 focus:ring-primary focus:outline-none"
            required
          />

          {error && <p className="text-xs text-error">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold disabled:opacity-50"
          >
            {loading ? "..." : "Changer le mot de passe"}
          </button>
        </form>
      </div>
    </div>
  );
}
