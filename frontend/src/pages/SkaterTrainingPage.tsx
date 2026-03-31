import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Skater, WeeklyReview, TrainingIncident, TrainingChallenge, TimelineEntry } from "../api/client";
import TrainingEvolutionChart from "../components/TrainingEvolutionChart";
import { seasonDateRange, currentSeason } from "../utils/season";

const TABS = [
  { key: "reviews", label: "Retours", icon: "rate_review" },
  { key: "challenges", label: "Défis", icon: "flag" },
  { key: "incidents", label: "Incidents", icon: "warning" },
  { key: "evolution", label: "Évolution", icon: "trending_up" },
  { key: "journal", label: "Journal", icon: "auto_stories" },
] as const;

type Tab = typeof TABS[number]["key"];

const RATING_TOOLTIPS: Record<string, string> = {
  engagement: "Implication et motivation lors des entraînements : concentration, volonté de progresser, participation active aux exercices.",
  progression: "Évolution technique constatée : acquisition de nouveaux éléments, amélioration de la qualité d'exécution.",
  attitude: "Comportement général : respect des consignes, esprit d'équipe, ponctualité, relation avec les autres patineurs.",
};

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

function RatingLabel({ field }: { field: string }) {
  const tooltip = RATING_TOOLTIPS[field];
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-[10px] uppercase tracking-wider text-on-surface-variant capitalize">{field}</span>
      {tooltip && (
        <span className="material-symbols-outlined text-on-surface-variant text-xs cursor-help" title={tooltip}>
          info
        </span>
      )}
    </span>
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

/* ── Cards (used for latest / featured items above the tabs) ── */

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
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {(["engagement", "progression", "attitude"] as const).map((field) => (
          <div key={field}>
            <RatingLabel field={field} />
            <RatingDots value={review[field]} />
          </div>
        ))}
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

function ChallengeCard({ challenge, onEdit }: { challenge: TrainingChallenge; onEdit?: () => void }) {
  const targetDate = new Date(challenge.target_date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="bg-surface-container-low rounded-2xl p-5 space-y-3 ring-1 ring-primary/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary">flag</span>
          <span className="text-[10px] uppercase tracking-wider font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
            En cours
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-on-surface-variant">Échéance : {targetDate}</span>
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
      </div>
      <p className="text-sm text-on-surface">{challenge.objective}</p>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Atteinte</p>
        <ScoreDots value={challenge.score} />
      </div>
    </div>
  );
}

/* ── Detail modals (opened from compact rows) ── */

function ReviewDetailModal({ review, onClose, onEdit }: { review: WeeklyReview; onClose: () => void; onEdit?: () => void }) {
  const weekDate = new Date(review.week_start).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-headline font-bold text-on-surface text-lg">
            Semaine du {weekDate}
          </h3>
          <div className="flex items-center gap-2">
            {!review.visible_to_skater && (
              <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
                visibility_off
              </span>
            )}
            {onEdit && (
              <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
                <span className="material-symbols-outlined text-lg">edit</span>
              </button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {(["engagement", "progression", "attitude"] as const).map((field) => (
            <div key={field}>
              <RatingLabel field={field} />
              <RatingDots value={review[field]} />
            </div>
          ))}
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
        <div className="flex justify-end pt-2">
          <button onClick={onClose} className="py-2 px-4 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}

function ChallengeDetailModal({ challenge, onClose, onEdit }: { challenge: TrainingChallenge; onClose: () => void; onEdit?: () => void }) {
  const isActive = challenge.target_date >= new Date().toISOString().split("T")[0];
  const targetDate = new Date(challenge.target_date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`material-symbols-outlined text-lg ${isActive ? "text-primary" : "text-on-surface-variant"}`}>flag</span>
            <h3 className="font-headline font-bold text-on-surface text-lg">Défi</h3>
            {isActive && (
              <span className="text-[10px] uppercase tracking-wider font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
                En cours
              </span>
            )}
          </div>
          {onEdit && (
            <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          )}
        </div>
        <p className="text-sm text-on-surface">{challenge.objective}</p>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-1">Atteinte</p>
            <ScoreDots value={challenge.score} />
          </div>
          <span className="text-xs text-on-surface-variant">Échéance : {targetDate}</span>
        </div>
        <div className="flex justify-end pt-2">
          <button onClick={onClose} className="py-2 px-4 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}

function IncidentDetailModal({ incident, onClose, onEdit }: { incident: TrainingIncident; onClose: () => void; onEdit?: () => void }) {
  const meta = INCIDENT_TYPE_LABELS[incident.incident_type] ?? INCIDENT_TYPE_LABELS.other;
  const dateStr = new Date(incident.date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="fixed inset-0 bg-scrim/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface rounded-3xl p-6 w-full max-w-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`material-symbols-outlined text-lg ${meta.color}`}>{meta.icon}</span>
            <h3 className="font-headline font-bold text-on-surface text-lg">{meta.label}</h3>
          </div>
          <div className="flex items-center gap-2">
            {!incident.visible_to_skater && (
              <span className="material-symbols-outlined text-on-surface-variant text-sm" title="Non visible par le patineur">
                visibility_off
              </span>
            )}
            {onEdit && (
              <button onClick={onEdit} className="text-on-surface-variant hover:text-primary transition-colors">
                <span className="material-symbols-outlined text-lg">edit</span>
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-on-surface-variant">{dateStr}</p>
        <p className="text-sm text-on-surface">{incident.description}</p>
        <div className="flex justify-end pt-2">
          <button onClick={onClose} className="py-2 px-4 rounded-xl text-sm font-bold text-on-surface-variant hover:bg-surface-container transition-colors">
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Compact rows ── */

function ReviewRow({ review, onClick }: { review: WeeklyReview; onClick: () => void }) {
  const weekDate = new Date(review.week_start).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
  });
  const avg = ((review.engagement + review.progression + review.attitude) / 3).toFixed(1);
  const hasText = !!(review.strengths || review.improvements);

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-surface-container-low transition-colors text-left"
    >
      <span className="text-xs text-on-surface-variant w-16 shrink-0">{weekDate}</span>
      <div className="flex gap-2 shrink-0">
        {(["engagement", "progression", "attitude"] as const).map((field) => (
          <div key={field} className="flex gap-0.5">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className={`w-1.5 h-1.5 rounded-full ${i < review[field] ? "bg-primary" : "bg-surface-container"}`} />
            ))}
          </div>
        ))}
      </div>
      <span className="font-mono text-xs text-primary font-bold w-8 shrink-0">{avg}</span>
      {hasText && (
        <p className="text-xs text-on-surface-variant truncate flex-1 min-w-0">
          {review.strengths || review.improvements}
        </p>
      )}
      {!review.visible_to_skater && (
        <span className="material-symbols-outlined text-on-surface-variant text-sm shrink-0" title="Non visible par le patineur">
          visibility_off
        </span>
      )}
    </button>
  );
}

function ChallengeRow({ challenge, onClick }: { challenge: TrainingChallenge; onClick: () => void }) {
  const isActive = challenge.target_date >= new Date().toISOString().split("T")[0];
  const targetDate = new Date(challenge.target_date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
  });

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-surface-container-low transition-colors text-left"
    >
      <span className={`material-symbols-outlined text-sm ${isActive ? "text-primary" : "text-on-surface-variant"}`}>flag</span>
      <span className="text-xs text-on-surface-variant w-16 shrink-0">{targetDate}</span>
      <div className="flex gap-0.5 shrink-0">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={`w-1.5 h-1.5 rounded-full ${i < challenge.score ? "bg-primary" : "bg-surface-container"}`} />
        ))}
      </div>
      <p className="text-xs text-on-surface truncate flex-1 min-w-0">{challenge.objective}</p>
    </button>
  );
}

const INCIDENT_TYPE_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  injury: { label: "Blessure", color: "text-error", icon: "healing" },
  behavior: { label: "Comportement", color: "text-orange-600", icon: "report" },
  other: { label: "Autre", color: "text-on-surface-variant", icon: "info" },
};

function IncidentRow({ incident, onClick }: { incident: TrainingIncident; onClick: () => void }) {
  const meta = INCIDENT_TYPE_LABELS[incident.incident_type] ?? INCIDENT_TYPE_LABELS.other;
  const dateStr = new Date(incident.date).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
  });

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-surface-container-low transition-colors text-left"
    >
      <span className={`material-symbols-outlined text-sm ${meta.color}`}>{meta.icon}</span>
      <span className="text-xs text-on-surface-variant w-16 shrink-0">{dateStr}</span>
      <span className={`text-xs font-bold shrink-0 ${meta.color}`}>{meta.label}</span>
      <p className="text-xs text-on-surface-variant truncate flex-1 min-w-0">{incident.description}</p>
      {!incident.visible_to_skater && (
        <span className="material-symbols-outlined text-on-surface-variant text-sm shrink-0" title="Non visible par le patineur">
          visibility_off
        </span>
      )}
    </button>
  );
}

/* ── Form modals ── */

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

  function RatingSelect({ value, onChange, field }: { value: number; onChange: (v: number) => void; field: string }) {
    return (
      <div>
        <div className="mb-1">
          <RatingLabel field={field} />
        </div>
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

        <div className="grid grid-cols-3 gap-4">
          <RatingSelect field="engagement" value={form.engagement} onChange={(v) => setForm({ ...form, engagement: v })} />
          <RatingSelect field="progression" value={form.progression} onChange={(v) => setForm({ ...form, progression: v })} />
          <RatingSelect field="attitude" value={form.attitude} onChange={(v) => setForm({ ...form, attitude: v })} />
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

/* ── Main page ── */

export default function SkaterTrainingPage() {
  const { id } = useParams<{ id: string }>();
  const skaterId = Number(id);
  const [selectedSeason, setSelectedSeason] = useState<string>(currentSeason());
  const [activeTab, setActiveTab] = useState<Tab>("reviews");
  const [editingReview, setEditingReview] = useState<WeeklyReview | undefined>();
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [viewingReview, setViewingReview] = useState<WeeklyReview | undefined>();
  const [editingIncident, setEditingIncident] = useState<TrainingIncident | undefined>();
  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [viewingIncident, setViewingIncident] = useState<TrainingIncident | undefined>();
  const [editingChallenge, setEditingChallenge] = useState<TrainingChallenge | undefined>();
  const [showChallengeForm, setShowChallengeForm] = useState(false);
  const [viewingChallenge, setViewingChallenge] = useState<TrainingChallenge | undefined>();

  const seasonRange = selectedSeason ? seasonDateRange(selectedSeason) : undefined;

  const { data: skater } = useQuery({
    queryKey: ["skater", skaterId],
    queryFn: () => api.skaters.get(skaterId),
  });

  const { data: seasons } = useQuery({
    queryKey: ["skater-seasons", skaterId],
    queryFn: () => api.skaters.seasons(skaterId),
  });

  // Build the season list: merge competition seasons with a set of training-relevant seasons
  const seasonOptions = (() => {
    const current = currentSeason();
    const set = new Set(seasons ?? []);
    set.add(current);
    return [...set].sort().reverse();
  })();

  const { data: reviews } = useQuery({
    queryKey: ["training", "reviews", skaterId, selectedSeason],
    queryFn: () => api.training.reviews.list({
      skater_id: skaterId,
      ...(seasonRange ? { from: seasonRange.from, to: seasonRange.to } : {}),
    }),
  });

  const { data: incidents } = useQuery({
    queryKey: ["training", "incidents", skaterId, selectedSeason],
    queryFn: () => api.training.incidents.list({
      skater_id: skaterId,
      ...(seasonRange ? { from: seasonRange.from, to: seasonRange.to } : {}),
    }),
  });

  const { data: challenges } = useQuery({
    queryKey: ["training", "challenges", skaterId, selectedSeason],
    queryFn: () => api.training.challenges.list({
      skater_id: skaterId,
      ...(seasonRange ? { from: seasonRange.from, to: seasonRange.to } : {}),
    }),
  });

  const { data: timeline } = useQuery({
    queryKey: ["timeline", skaterId, selectedSeason],
    queryFn: () => api.training.timeline({
      skater_id: skaterId,
      ...(seasonRange ? { from: seasonRange.from, to: seasonRange.to } : {}),
    }),
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

  const latestReview = reviews?.[0];
  const allReviews = reviews ?? [];

  const today = new Date().toISOString().split("T")[0];
  const activeChallenges = (challenges ?? []).filter((c) => c.target_date >= today);
  const allChallenges = challenges ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="font-headline font-bold text-on-surface text-xl">
            {skater.first_name} {skater.last_name}
          </h2>
          <select
            value={selectedSeason}
            onChange={(e) => setSelectedSeason(e.target.value)}
            className="bg-surface-container-high rounded-xl px-4 py-2 text-sm font-bold text-on-surface font-headline appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {seasonOptions.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
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

      {/* Featured cards: latest review + active challenges */}
      {(latestReview || activeChallenges.length > 0) && (
        <div className="space-y-3">
          {latestReview && (
            <ReviewCard review={latestReview} onEdit={() => { setEditingReview(latestReview); setShowReviewForm(true); }} />
          )}
          {activeChallenges.map((c) => (
            <ChallengeCard key={c.id} challenge={c} onEdit={() => { setEditingChallenge(c); setShowChallengeForm(true); }} />
          ))}
        </div>
      )}

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
          {allReviews.length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun retour pour le moment</p>
          ) : (
            <div className="divide-y divide-outline-variant/20">
              {allReviews.map((r) => (
                <ReviewRow key={r.id} review={r} onClick={() => setViewingReview(r)} />
              ))}
            </div>
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
          {allChallenges.length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucun défi pour le moment</p>
          ) : (
            <div className="divide-y divide-outline-variant/20">
              {allChallenges.map((c) => (
                <ChallengeRow key={c.id} challenge={c} onClick={() => setViewingChallenge(c)} />
              ))}
            </div>
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
            <div className="divide-y divide-outline-variant/20">
              {incidents?.map((i) => (
                <IncidentRow key={i.id} incident={i} onClick={() => setViewingIncident(i)} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "evolution" && (
        <TrainingEvolutionChart
          reviews={reviews ?? []}
          incidents={incidents ?? []}
        />
      )}

      {activeTab === "journal" && (
        <div className="space-y-3">
          {(timeline ?? []).length === 0 ? (
            <p className="text-sm text-on-surface-variant text-center py-10">Aucune entree dans le journal</p>
          ) : (
            <div className="space-y-3">
              {(timeline ?? []).map((entry, idx) => (
                <div key={`${entry.type}-${idx}`}>
                  {entry.type === "review" && (
                    <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
                      <h4 className="font-headline font-bold text-on-surface text-sm">
                        Retour - Semaine du{" "}
                        {new Date(entry.week_start + "T00:00:00").toLocaleDateString("fr-FR", {
                          day: "numeric",
                          month: "long",
                        })}
                      </h4>
                      <div className="grid grid-cols-3 gap-4">
                        {(["engagement", "progression", "attitude"] as const).map((field) => (
                          <div key={field}>
                            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant capitalize">{field}</span>
                            <div className="flex gap-0.5">
                              {Array.from({ length: 5 }, (_, i) => (
                                <div key={i} className={`w-2.5 h-2.5 rounded-full ${i < entry[field] ? "bg-primary" : "bg-surface-container"}`} />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {entry.type === "incident" && (
                    <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
                      <h4 className="font-headline font-bold text-on-surface text-sm">
                        Incident du{" "}
                        {new Date(entry.date + "T00:00:00").toLocaleDateString("fr-FR", {
                          day: "numeric",
                          month: "long",
                        })}
                      </h4>
                      <p className="text-sm text-on-surface-variant">{entry.description}</p>
                    </div>
                  )}
                  {entry.type === "self_evaluation" && (
                    <div className="bg-surface-container-low rounded-2xl p-5 space-y-2">
                      <div className="flex items-center gap-2">
                        <h4 className="font-headline font-bold text-on-surface text-sm">
                          Auto-evaluation du{" "}
                          {new Date(entry.date + "T00:00:00").toLocaleDateString("fr-FR", {
                            day: "numeric",
                            month: "long",
                          })}
                        </h4>
                        {entry.shared && (
                          <span className="bg-primary-container text-on-primary-container text-[9px] font-bold px-2 py-0.5 rounded-full">
                            Partage
                          </span>
                        )}
                      </div>
                      {entry.notes && (
                        <p className="text-sm text-on-surface-variant">{entry.notes}</p>
                      )}
                      {entry.element_ratings && entry.element_ratings.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                          {entry.element_ratings.map((er: { name: string; rating: number }, i: number) => (
                            <span key={i} className="bg-surface-container text-[10px] px-2 py-1 rounded-lg font-semibold">
                              {er.name} <span className="text-primary">{er.rating}/5</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showReviewForm && <ReviewFormModal skaterId={skaterId} existing={editingReview} onClose={() => setShowReviewForm(false)} />}
      {showIncidentForm && <IncidentFormModal skaterId={skaterId} existing={editingIncident} onClose={() => setShowIncidentForm(false)} />}
      {showChallengeForm && <ChallengeFormModal skaterId={skaterId} existing={editingChallenge} onClose={() => setShowChallengeForm(false)} />}
      {viewingReview && (
        <ReviewDetailModal
          review={viewingReview}
          onClose={() => setViewingReview(undefined)}
          onEdit={() => {
            setViewingReview(undefined);
            setEditingReview(viewingReview);
            setShowReviewForm(true);
          }}
        />
      )}
      {viewingChallenge && (
        <ChallengeDetailModal
          challenge={viewingChallenge}
          onClose={() => setViewingChallenge(undefined)}
          onEdit={() => {
            setViewingChallenge(undefined);
            setEditingChallenge(viewingChallenge);
            setShowChallengeForm(true);
          }}
        />
      )}
      {viewingIncident && (
        <IncidentDetailModal
          incident={viewingIncident}
          onClose={() => setViewingIncident(undefined)}
          onEdit={() => {
            setViewingIncident(undefined);
            setEditingIncident(viewingIncident);
            setShowIncidentForm(true);
          }}
        />
      )}
    </div>
  );
}
