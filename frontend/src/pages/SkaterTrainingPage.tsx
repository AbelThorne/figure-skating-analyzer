import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Skater, WeeklyReview, TrainingIncident, TrainingChallenge } from "../api/client";
import TrainingEvolutionChart from "../components/TrainingEvolutionChart";

const TABS = [
  { key: "reviews", label: "Retours", icon: "rate_review" },
  { key: "incidents", label: "Incidents", icon: "warning" },
  { key: "challenges", label: "Défis", icon: "flag" },
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

function ReviewFormModal({
  skaterId,
  existing,
  onClose,
}: {
  skaterId: number;
  existing?: WeeklyReview;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    week_start: existing?.week_start ?? new Date().toISOString().split("T")[0],
    attendance: existing?.attendance ?? "",
    engagement: existing?.engagement ?? 3,
    progression: existing?.progression ?? 3,
    attitude: existing?.attitude ?? 3,
    strengths: existing?.strengths ?? "",
    improvements: existing?.improvements ?? "",
    visible_to_skater: existing?.visible_to_skater ?? true,
  });

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? api.training.reviews.update(existing.id, form)
        : api.training.reviews.create({ ...form, skater_id: skaterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training", "reviews"] });
      onClose();
    },
  });

  function RatingSelect({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
    return (
      <div>
        <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">{label}</label>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              className={`w-8 h-8 rounded-lg font-mono text-sm font-bold transition-colors ${
                n <= value
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-headline font-bold text-on-surface text-lg">
          {existing ? "Modifier le retour" : "Nouveau retour"}
        </h3>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Semaine du</label>
          <input
            type="date"
            value={form.week_start}
            onChange={(e) => setForm({ ...form, week_start: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Assiduité</label>
          <input
            type="text"
            placeholder="ex: 3/4"
            value={form.attendance}
            onChange={(e) => setForm({ ...form, attendance: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <RatingSelect label="Engagement" value={form.engagement} onChange={(v) => setForm({ ...form, engagement: v })} />
          <RatingSelect label="Progression" value={form.progression} onChange={(v) => setForm({ ...form, progression: v })} />
          <RatingSelect label="Attitude" value={form.attitude} onChange={(v) => setForm({ ...form, attitude: v })} />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Points forts</label>
          <textarea
            value={form.strengths}
            onChange={(e) => setForm({ ...form, strengths: e.target.value })}
            rows={3}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Axes d'amélioration</label>
          <textarea
            value={form.improvements}
            onChange={(e) => setForm({ ...form, improvements: e.target.value })}
            rows={3}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.visible_to_skater}
            onChange={(e) => setForm({ ...form, visible_to_skater: e.target.checked })}
            className="accent-primary"
          />
          <span className="text-sm text-on-surface">Visible par le patineur/parent</span>
        </label>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

function IncidentFormModal({
  skaterId,
  existing,
  onClose,
}: {
  skaterId: number;
  existing?: TrainingIncident;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    date: existing?.date ?? new Date().toISOString().split("T")[0],
    incident_type: (existing?.incident_type ?? "other") as "injury" | "behavior" | "other",
    description: existing?.description ?? "",
    visible_to_skater: existing?.visible_to_skater ?? false,
  });

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? api.training.incidents.update(existing.id, form)
        : api.training.incidents.create({ ...form, skater_id: skaterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training", "incidents"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-headline font-bold text-on-surface text-lg">
          {existing ? "Modifier l'incident" : "Signaler un incident"}
        </h3>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Date</label>
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Type</label>
          <select
            value={form.incident_type}
            onChange={(e) => setForm({ ...form, incident_type: e.target.value as "injury" | "behavior" | "other" })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="injury">Blessure</option>
            <option value="behavior">Comportement</option>
            <option value="other">Autre</option>
          </select>
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={4}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.visible_to_skater}
            onChange={(e) => setForm({ ...form, visible_to_skater: e.target.checked })}
            className="accent-primary"
          />
          <span className="text-sm text-on-surface">Visible par le patineur/parent</span>
        </label>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ScoreDots({ value, max = 5 }: { value: number; max?: number }) {
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

function ChallengeCard({ challenge, onEdit }: { challenge: TrainingChallenge; onEdit?: () => void }) {
  const isActive = challenge.target_date >= new Date().toISOString().split("T")[0];
  const targetDate = new Date(challenge.target_date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const createdDate = challenge.created_at
    ? new Date(challenge.created_at).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div className={`bg-surface-container-low rounded-2xl p-5 space-y-3 ${isActive ? "ring-1 ring-primary/20" : ""}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`material-symbols-outlined text-lg ${isActive ? "text-primary" : "text-on-surface-variant"}`}>
            flag
          </span>
          {isActive && (
            <span className="text-[10px] uppercase tracking-wider font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
              En cours
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-on-surface-variant">
            Échéance : {targetDate}
          </span>
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
      </div>
      <p className="text-sm text-on-surface">{challenge.objective}</p>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Atteinte</p>
          <ScoreDots value={challenge.score} />
        </div>
        {createdDate && (
          <p className="text-[10px] text-on-surface-variant">Créé le {createdDate}</p>
        )}
      </div>
    </div>
  );
}

function ChallengeFormModal({
  skaterId,
  existing,
  onClose,
}: {
  skaterId: number;
  existing?: TrainingChallenge;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    objective: existing?.objective ?? "",
    target_date: existing?.target_date ?? "",
    score: existing?.score ?? 0,
  });

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? api.training.challenges.update(existing.id, form)
        : api.training.challenges.create({ ...form, skater_id: skaterId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training", "challenges"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-headline font-bold text-on-surface text-lg">
          {existing ? "Modifier le défi" : "Nouveau défi"}
        </h3>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Objectif</label>
          <textarea
            value={form.objective}
            onChange={(e) => setForm({ ...form, objective: e.target.value })}
            rows={3}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary resize-none"
            placeholder="Décrivez l'objectif du défi..."
          />
        </div>

        <div>
          <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Date cible</label>
          <input
            type="date"
            value={form.target_date}
            onChange={(e) => setForm({ ...form, target_date: e.target.value })}
            className="w-full bg-surface-container rounded-xl px-4 py-2.5 text-sm text-on-surface outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {existing && (
          <div>
            <label className="text-[10px] uppercase tracking-wider text-on-surface-variant block mb-1">Atteinte</label>
            <div className="flex gap-1">
              {[0, 1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setForm({ ...form, score: n })}
                  className={`w-8 h-8 rounded-lg font-mono text-sm font-bold transition-colors ${
                    n <= form.score && form.score > 0
                      ? "bg-primary text-white"
                      : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.objective.trim() || !form.target_date || mutation.isPending}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SkaterTrainingPage() {
  const { id } = useParams<{ id: string }>();
  const skaterId = Number(id);
  const [activeTab, setActiveTab] = useState<Tab>("reviews");
  const [editingReview, setEditingReview] = useState<WeeklyReview | undefined>();
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [editingIncident, setEditingIncident] = useState<TrainingIncident | undefined>();
  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [editingChallenge, setEditingChallenge] = useState<TrainingChallenge | undefined>();
  const [showChallengeForm, setShowChallengeForm] = useState(false);

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

  const { data: challenges } = useQuery({
    queryKey: ["training", "challenges", skaterId],
    queryFn: () => api.training.challenges.list({ skater_id: skaterId }),
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
      <div className="flex gap-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 text-sm font-semibold transition-colors border-b-2 ${
              activeTab === tab.key
                ? "text-primary border-primary"
                : "text-on-surface-variant border-transparent hover:text-on-surface"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "reviews" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={() => { setEditingReview(undefined); setShowReviewForm(true); }}
              className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Nouveau retour
            </button>
          </div>
          {(reviews ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun retour pour le moment</p>
          ) : (
            reviews?.map((r) => <ReviewCard key={r.id} review={r} onEdit={() => { setEditingReview(r); setShowReviewForm(true); }} />)
          )}
        </div>
      )}

      {activeTab === "incidents" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={() => { setEditingIncident(undefined); setShowIncidentForm(true); }}
              className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Nouvel incident
            </button>
          </div>
          {(incidents ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun incident signalé</p>
          ) : (
            incidents?.map((i) => <IncidentCard key={i.id} incident={i} onEdit={() => { setEditingIncident(i); setShowIncidentForm(true); }} />)
          )}
        </div>
      )}

      {activeTab === "challenges" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={() => { setEditingChallenge(undefined); setShowChallengeForm(true); }}
              className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Nouveau défi
            </button>
          </div>
          {(challenges ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun défi pour le moment</p>
          ) : (
            challenges?.map((c) => <ChallengeCard key={c.id} challenge={c} onEdit={() => { setEditingChallenge(c); setShowChallengeForm(true); }} />)
          )}
        </div>
      )}

      {activeTab === "evolution" && (
        <TrainingEvolutionChart
          reviews={reviews ?? []}
          incidents={incidents ?? []}
        />
      )}

      {showReviewForm && <ReviewFormModal skaterId={skaterId} existing={editingReview} onClose={() => setShowReviewForm(false)} />}
      {showIncidentForm && <IncidentFormModal skaterId={skaterId} existing={editingIncident} onClose={() => setShowIncidentForm(false)} />}
      {showChallengeForm && <ChallengeFormModal skaterId={skaterId} existing={editingChallenge} onClose={() => setShowChallengeForm(false)} />}
    </div>
  );
}
