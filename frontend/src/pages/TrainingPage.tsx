import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Skater, WeeklyReview } from "../api/client";

function SkaterCard({ skater, lastReview }: { skater: Skater; lastReview?: WeeklyReview }) {
  const avgScore = lastReview
    ? ((lastReview.engagement + lastReview.progression + lastReview.attitude) / 3).toFixed(1)
    : null;

  return (
    <Link
      to={`/entrainement/patineurs/${skater.id}`}
      className="bg-surface-container-low rounded-2xl p-5 hover:bg-surface-container transition-colors"
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-headline font-bold text-on-surface">
            {skater.first_name} {skater.last_name}
          </h3>
          {skater.club && (
            <p className="text-xs text-on-surface-variant mt-0.5">{skater.club}</p>
          )}
        </div>
        {avgScore && (
          <div className="text-right">
            <span className="font-mono text-lg font-bold text-primary">{avgScore}</span>
            <p className="text-[10px] text-on-surface-variant uppercase">Moy.</p>
          </div>
        )}
      </div>
      {lastReview && (
        <p className="text-xs text-on-surface-variant mt-2">
          Dernier retour : semaine du {new Date(lastReview.week_start).toLocaleDateString("fr-FR")}
        </p>
      )}
    </Link>
  );
}

export default function TrainingPage() {
  const { data: skaters, isLoading: skatersLoading } = useQuery({
    queryKey: ["skaters", "training_tracked"],
    queryFn: () => api.skaters.list({ training_tracked: true }),
  });

  const { data: reviews } = useQuery({
    queryKey: ["training", "reviews", "latest"],
    queryFn: () => api.training.reviews.list(),
  });

  if (skatersLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  // Build map of latest review per skater
  const latestReview: Record<number, WeeklyReview> = {};
  if (reviews) {
    for (const r of reviews) {
      if (!latestReview[r.skater_id] || r.week_start > latestReview[r.skater_id].week_start) {
        latestReview[r.skater_id] = r;
      }
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-on-surface-variant text-sm">
        {skaters?.length ?? 0} patineur{(skaters?.length ?? 0) > 1 ? "s" : ""}
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {skaters?.map((s) => (
          <SkaterCard key={s.id} skater={s} lastReview={latestReview[s.id]} />
        ))}
      </div>
    </div>
  );
}
