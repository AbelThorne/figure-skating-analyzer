import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import { WeeklyReview, TrainingIncident } from "../api/client";

const INCIDENT_COLORS: Record<string, string> = {
  injury: "#ba1a1a",
  behavior: "#ea580c",
  other: "#6b7280",
};

const INCIDENT_LABELS: Record<string, string> = {
  injury: "Blessure",
  behavior: "Comportement",
  other: "Autre",
};

interface Props {
  reviews: WeeklyReview[];
  incidents: TrainingIncident[];
}

export default function TrainingEvolutionChart({ reviews, incidents }: Props) {
  // Sort reviews by date ascending
  const sorted = [...reviews].sort((a, b) => a.week_start.localeCompare(b.week_start));

  const data = sorted.map((r) => ({
    week: new Date(r.week_start).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }),
    week_start: r.week_start,
    engagement: r.engagement,
    progression: r.progression,
    attitude: r.attitude,
  }));

  // Map incidents to their nearest week for overlay
  const incidentMarkers = incidents.map((i) => {
    const closest = sorted.reduce((prev, curr) =>
      Math.abs(new Date(curr.week_start).getTime() - new Date(i.date).getTime()) <
      Math.abs(new Date(prev.week_start).getTime() - new Date(i.date).getTime())
        ? curr
        : prev
    , sorted[0]);
    return {
      week: closest
        ? new Date(closest.week_start).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" })
        : "",
      incident: i,
    };
  });

  if (data.length === 0) {
    return (
      <p className="text-sm text-on-surface-variant text-center py-10">
        Pas encore assez de données pour afficher l'évolution.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Main chart */}
      <div>
        <h4 className="font-headline font-bold text-on-surface text-sm mb-3">Évolution des notes</h4>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data}>
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
            />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Line type="monotone" dataKey="engagement" name="Engagement" stroke="#2e6385" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="progression" name="Progression" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="attitude" name="Attitude" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
            {/* Incident markers */}
            {incidentMarkers.map((m, idx) => (
              <ReferenceDot
                key={idx}
                x={m.week}
                y={0.3}
                r={6}
                fill={INCIDENT_COLORS[m.incident.incident_type] ?? "#6b7280"}
                stroke="white"
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Incident legend */}
      {incidents.length > 0 && (
        <div>
          <h4 className="font-headline font-bold text-on-surface text-sm mb-2">Incidents</h4>
          <div className="space-y-1">
            {incidents.map((i) => (
              <div key={i.id} className="flex items-center gap-2 text-sm">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: INCIDENT_COLORS[i.incident_type] }}
                />
                <span className="text-on-surface-variant">
                  {new Date(i.date).toLocaleDateString("fr-FR")} —{" "}
                  {INCIDENT_LABELS[i.incident_type]}: {i.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
