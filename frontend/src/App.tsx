import { useState } from "react";
import { Routes, Route, NavLink, Link, useLocation, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { JobProvider } from "./contexts/JobContext";
import HomePage from "./pages/HomePage";
import CompetitionPage from "./pages/CompetitionPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import SkaterBrowserPage from "./pages/SkaterBrowserPage";
import SkaterAnalyticsPage from "./pages/SkaterAnalyticsPage";
import StatsPage from "./pages/StatsPage";
import ClubCompetitionPage from "./pages/ClubCompetitionPage";
import LoginPage from "./pages/LoginPage";
import SetupPage from "./pages/SetupPage";
import SettingsPage from "./pages/SettingsPage";
import ProfilePage from "./pages/ProfilePage";

const navLinks = [
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/club", label: "CLUB", icon: "bar_chart", end: false },
];

function getPageTitle(pathname: string): string {
  if (pathname === "/") return "Tableau de bord";
  if (pathname === "/competitions") return "Compétitions";
  if (pathname.startsWith("/competitions/")) return "Détail compétition";
  if (pathname === "/patineurs") return "Patineurs";
  if (pathname.startsWith("/patineurs/")) return "Analyse patineur";
  if (pathname.startsWith("/club")) return "Club";
  if (pathname === "/stats") return "Club";
  if (pathname === "/settings") return "Paramètres";
  if (pathname === "/profil") return "Mon compte";
  return "";
}

function AuthenticatedLayout() {
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: config, dataUpdatedAt } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });
  const logoSrc = config?.logo_url ? `${config.logo_url}?v=${dataUpdatedAt}` : "";

  function closeSidebar() {
    setSidebarOpen(false);
  }

  return (
    <JobProvider>
    <div className="flex min-h-screen">
      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-scrim/50 z-30 lg:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside className={`w-64 fixed left-0 top-0 h-screen bg-surface-container-low flex flex-col z-40 transition-transform duration-300 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`}>
        {/* Club header */}
        <div className="px-6 py-5 flex items-center gap-3">
          {logoSrc ? (
            <img src={logoSrc} alt="" className="w-10 h-10 object-contain" />
          ) : (
            <span className="material-symbols-outlined text-primary text-2xl">sports_score</span>
          )}
          <div className="min-w-0">
            <span className="font-headline font-bold text-on-surface text-xs leading-tight block">
              {config?.club_name ?? "SkateLab"}
            </span>
            <p className="text-[10px] uppercase tracking-widest text-on-surface-variant mt-0.5">
              Patinage artistique
            </p>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-2">
          {navLinks.map(({ to, label, icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={closeSidebar}
              className={({ isActive }) =>
                isActive
                  ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
                  : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
              }
            >
              <span className="material-symbols-outlined text-xl">{icon}</span>
              <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom section: settings + user */}
        <div className="mt-auto border-t border-outline-variant/30 px-2 py-3 space-y-1">
          {user?.role === "admin" && (
            <NavLink
              to="/settings"
              onClick={closeSidebar}
              className={({ isActive }) =>
                isActive
                  ? "bg-white text-primary shadow-sm rounded-xl px-4 py-2.5 font-bold flex items-center gap-3"
                  : "text-on-surface-variant hover:bg-surface-container rounded-xl px-4 py-2.5 flex items-center gap-3 transition-colors"
              }
            >
              <span className="material-symbols-outlined text-xl">settings</span>
              <span className="text-[11px] font-bold uppercase tracking-wider">PARAMÈTRES</span>
            </NavLink>
          )}
          <div className="flex items-center gap-2 px-4 py-2">
            <span className="material-symbols-outlined text-on-surface-variant text-xl">account_circle</span>
            <Link
              to="/profil"
              onClick={closeSidebar}
              className="text-xs text-on-surface-variant hover:text-on-surface truncate flex-1 transition-colors"
            >
              {user?.display_name || user?.email}
            </Link>
            <button
              onClick={logout}
              className="text-on-surface-variant hover:text-error transition-colors shrink-0"
              title="Déconnexion"
            >
              <span className="material-symbols-outlined text-lg">logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:ml-64 min-h-screen bg-surface flex-1 min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 bg-surface/70 backdrop-blur-xl z-30 shadow-sm flex items-center gap-3 px-4 lg:px-8 py-4">
          <button
            className="lg:hidden text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
            onClick={() => setSidebarOpen(true)}
            aria-label="Ouvrir le menu"
          >
            <span className="material-symbols-outlined text-2xl">menu</span>
          </button>
          <h1 className="font-headline font-bold text-on-surface text-xl truncate">{pageTitle}</h1>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-8 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/competitions/:id" element={<CompetitionPage />} />
            <Route path="/competitions" element={<CompetitionsPage />} />
            <Route path="/patineurs" element={<SkaterBrowserPage />} />
            <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
            <Route path="/club/saison" element={<StatsPage />} />
            <Route path="/club/competition" element={<ClubCompetitionPage />} />
            <Route path="/club" element={<Navigate to="/club/saison" replace />} />
            <Route path="/stats" element={<Navigate to="/club/saison" replace />} />
            <Route
              path="/settings"
              element={
                <ProtectedRoute requiredRole="admin">
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route path="/profil" element={<ProfilePage />} />
          </Routes>
        </main>
      </div>
    </div>
    </JobProvider>
  );
}

export default function App() {
  const { data: config, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/setup"
        element={
          config?.setup_required ? <SetupPage /> : <Navigate to="/" replace />
        }
      />
      <Route
        path="/*"
        element={
          config?.setup_required ? (
            <Navigate to="/setup" replace />
          ) : (
            <ProtectedRoute>
              <AuthenticatedLayout />
            </ProtectedRoute>
          )
        }
      />
    </Routes>
  );
}
