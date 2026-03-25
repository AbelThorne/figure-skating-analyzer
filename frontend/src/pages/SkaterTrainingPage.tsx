import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Skater, WeeklyReview, TrainingIncident } from "../api/client";

const TABS = [
  { key: "reviews", label: "Retours", icon: "rate_review" },
  { key: "incidents", label: "Incidents", icon: "warning" },
  { key: "evolution", label: "Évolution", icon: "trending_up" },
] as const;

type Tab = typeof TABS[number]["key"];

function RatingDots({ value, max = 5 }: { value: number; max?: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }, (_, i) => (
        <div
          key={i}
          className={`w-2.5 h-2.5 rounded-full ${
            i < value ? "bg-primary" : "bg-surface-container"
          }`}
        />
      ))}
    </div>
  );
}

function ReviewCard({ review, onEdit }: { review: WeeklyReview; onEdit?: () => void }) {
  const weekDate = new Date(review.week_start).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="bg-surface-container-low rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-headline font-bold text-on-surface text-sm">
          Semaine du {weekDate}
        </h4>
        <div className="flex items-center gap-2">
          {!review.visible_to_skater && (
            <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
              visibility_off
            </span>
          )}
          <span className="font-mono text-xs text-on-surface-variant">{review.attendance}</span>
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Engagement</p>
          <RatingDots value={review.engagement} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Progression</p>
          <RatingDots value={review.progression} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Attitude</p>
          <RatingDots value={review.attitude} />
        </div>
      </div>
      {review.strengths && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Points forts</p>
          <p className="text-sm text-on-surface">{review.strengths}</p>
        </div>
      )}
      {review.improvements && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">Axes d'amélioration</p>
          <p className="text-sm text-on-surface">{review.improvements}</p>
        </div>
      )}
    </div>
  );
}

const INCIDENT_TYPE_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  injury: { label: "Blessure", color: "text-error", icon: "healing" },
  behavior: { label: "Comportement", color: "text-orange-600", icon: "report" },
  other: { label: "Autre", color: "text-on-surface-variant", icon: "info" },
};

function IncidentCard({ incident, onEdit }: { incident: TrainingIncident; onEdit?: () => void }) {
  const meta = INCIDENT_TYPE_LABELS[incident.incident_type] ?? INCIDENT_TYPE_LABELS.other;
  return (
    <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`material-symbols-outlined text-lg ${meta.color}`}>{meta.icon}</span>
          <span className={`text-sm font-bold ${meta.color}`}>{meta.label}</span>
        </div>
        <div className="flex items-center gap-2">
          {!incident.visible_to_skater && (
            <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
              visibility_off
            </span>
          )}
          <span className="text-xs text-on-surface-variant">
            {new Date(incident.date).toLocaleDateString("fr-FR")}
          </span>
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
      </div>
      <p className="text-sm text-on-surface">{incident.description}</p>
    </div>
  );
}

export default function SkaterTrainingPage() {
  const { id } = useParams<{ id: string }>();
  const skaterId = Number(id);
  const [activeTab, setActiveTab] = useState<Tab>("reviews");

  const { data: skater } = useQuery({
    queryKey: ["skater", skaterId],
    queryFn: () => api.skaters.get(skaterId),
  });

  const { data: reviews } = useQuery({
    queryKey: ["training", "reviews", skaterId],
    queryFn: () => api.training.reviews.list({ skater_id: skaterId }),
  });

  const { data: incidents } = useQuery({
    queryKey: ["training", "incidents", skaterId],
    queryFn: () => api.training.incidents.list({ skater_id: skaterId }),
  });

  if (!skater) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  // Averages over last 4 weeks
  const recentReviews = (reviews ?? []).slice(0, 4);
  const avg = (field: "engagement" | "progression" | "attitude") =>
    recentReviews.length
      ? (recentReviews.reduce((s, r) => s + r[field], 0) / recentReviews.length).toFixed(1)
      : "—";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline font-bold text-on-surface text-xl">
            {skater.first_name} {skater.last_name}
          </h2>
          {skater.club && (
            <p className="text-sm text-on-surface-variant">{skater.club}</p>
          )}
        </div>
        <div className="flex gap-4">
          {(["engagement", "progression", "attitude"] as const).map((field) => (
            <div key={field} className="text-center">
              <span className="font-mono text-lg font-bold text-primary">{avg(field)}</span>
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant capitalize">
                {field}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-container rounded-xl p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${
              activeTab === tab.key
                ? "bg-white text-primary shadow-sm"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-lg">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "reviews" && (
        <div className="space-y-3">
          {(reviews ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun retour pour le moment</p>
          ) : (
            reviews?.map((r) => <ReviewCard key={r.id} review={r} />)
          )}
        </div>
      )}

      {activeTab === "incidents" && (
        <div className="space-y-3">
          {(incidents ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun incident signalé</p>
          ) : (
            incidents?.map((i) => <IncidentCard key={i.id} incident={i} />)
          )}
        </div>
      )}

      {activeTab === "evolution" && (
        <div className="text-sm text-on-surface-variant text-center py-10">
          Les graphiques d'évolution seront ajoutés dans la prochaine tâche.
        </div>
      )}
    </div>
  );
}
