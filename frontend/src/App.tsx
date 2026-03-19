import { Routes, Route, NavLink } from "react-router-dom";
import HomePage from "./pages/HomePage";
import CompetitionPage from "./pages/CompetitionPage";
import StatsPage from "./pages/StatsPage";

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-blue-700 text-white px-6 py-3 flex items-center gap-6 shadow">
        <span className="font-bold text-lg tracking-tight">Figure Skating Analyzer</span>
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "underline font-medium" : "hover:underline"
          }
        >
          Competitions
        </NavLink>
        <NavLink
          to="/stats"
          className={({ isActive }) =>
            isActive ? "underline font-medium" : "hover:underline"
          }
        >
          Statistics
        </NavLink>
      </nav>
      <main className="flex-1 container mx-auto px-4 py-6 max-w-5xl">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/competitions/:id" element={<CompetitionPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </main>
    </div>
  );
}
