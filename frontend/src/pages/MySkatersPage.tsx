import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function MySkatersPage() {
  const { data: skaters, isLoading } = useQuery({
    queryKey: ["me", "skaters"],
    queryFn: api.me.skaters,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  if (!skaters || skaters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <span className="material-symbols-outlined text-on-surface-variant text-5xl">
          person_off
        </span>
        <p className="text-on-surface-variant text-sm">
          Aucun patineur associé à votre compte. Contactez l'administrateur.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {skaters.map((s) => (
          <Link
            key={s.id}
            to={`/patineurs/${s.id}/analyse`}
            className="bg-surface-container rounded-xl p-5 hover:bg-surface-container-high transition-colors group"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-2xl">
                ice_skating
              </span>
              <div>
                <p className="font-headline font-bold text-on-surface group-hover:text-primary transition-colors">
                  {s.first_name} {s.last_name}
                </p>
                {s.club && (
                  <p className="text-xs text-on-surface-variant mt-0.5">{s.club}</p>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
