import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
import HomePage from "./pages/HomePage";
import CompetitionPage from "./pages/CompetitionPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import SkaterBrowserPage from "./pages/SkaterBrowserPage";
import SkaterAnalyticsPage from "./pages/SkaterAnalyticsPage";
import StatsPage from "./pages/StatsPage";

const navLinks = [
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/stats", label: "STATISTIQUES", icon: "bar_chart", end: false },
];

function getPageTitle(pathname: string): string {
  if (pathname === "/") return "Tableau de bord";
  if (pathname === "/competitions") return "Compétitions";
  if (pathname.startsWith("/competitions/")) return "Détail compétition";
  if (pathname === "/patineurs") return "Patineurs";
  if (pathname.startsWith("/patineurs/")) return "Analyse patineur";
  if (pathname === "/stats") return "Statistiques";
  return "";
}

export default function App() {
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: api.config.get,
    staleTime: Infinity,
  });

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 fixed left-0 top-0 h-screen bg-surface-container-low flex flex-col">
        {/* Club header */}
        <div className="px-6 py-5 flex items-center gap-3">
          {config?.logo_url ? (
            <img src={config.logo_url} alt="" className="w-10 h-10 object-contain" />
          ) : (
            <span className="material-symbols-outlined text-primary text-2xl">sports_score</span>
          )}
          <div className="min-w-0">
            <span className="font-headline font-bold text-on-surface text-xs leading-tight block">
              {config?.club_name ?? "Analyse Patinage"}
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
      </aside>

      {/* Main content */}
      <div className="ml-64 min-h-screen bg-surface flex-1">
        {/* Top bar */}
        <header className="sticky top-0 bg-surface/70 backdrop-blur-xl z-30 shadow-sm flex justify-between items-center px-8 py-4">
          <h1 className="font-headline font-bold text-on-surface text-xl">{pageTitle}</h1>
          <div />
        </header>

        {/* Page content */}
        <main className="p-8 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/competitions/:id" element={<CompetitionPage />} />
            <Route path="/competitions" element={<CompetitionsPage />} />
            <Route path="/patineurs" element={<SkaterBrowserPage />} />
            <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
            <Route path="/stats" element={<StatsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
