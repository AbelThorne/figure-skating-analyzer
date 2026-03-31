import { useQuery } from "@tanstack/react-query";
import { api, TrainingMood, SelfEvaluation } from "../api/client";

const EMOJI_MAP: Record<number, string> = {
  1: "\u{1F61E}",
  2: "\u{1F615}",
  3: "\u{1F610}",
  4: "\u{1F642}",
  5: "\u{1F604}",
};

const DAY_NAMES = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

interface Props {
  skaterId: number;
  weekStart: string;
  weekEnd: string;
  onEditEval?: (ev: SelfEvaluation) => void;
}

export default function TrainingJournal({
  skaterId,
  weekStart,
  weekEnd,
  onEditEval,
}: Props) {
  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, weekStart, weekEnd],
    queryFn: () =>
      api.training.moods.list({
        skater_id: skaterId,
        from: weekStart,
        to: weekEnd,
      }),
  });

  // Fetch ALL evaluations (no date filter) for the full history
  const { data: evals } = useQuery({
    queryKey: ["selfEvaluations", skaterId],
    queryFn: () =>
      api.training.selfEvaluations.list({
        skater_id: skaterId,
      }),
  });

  const moodByDate: Record<string, TrainingMood> = {};
  moods?.forEach((m) => {
    moodByDate[m.date] = m;
  });

  const weekDays: string[] = [];
  const start = new Date(weekStart + "T00:00:00");
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    weekDays.push(d.toISOString().slice(0, 10));
  }

  const formatDate = (iso: string) =>
    new Date(iso + "T00:00:00").toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });

  // Sort evals by date descending, then by id descending (newest first)
  const sortedEvals = [...(evals ?? [])].sort((a, b) =>
    a.date > b.date ? -1 : a.date < b.date ? 1 : b.id - a.id
  );

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-4">
        Journal
      </p>

      {/* Weekly mood board */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        {weekDays.map((day) => {
          const mood = moodByDate[day];
          const dayOfWeek = DAY_NAMES[new Date(day + "T00:00:00").getDay()];
          return (
            <div key={day} className="text-center min-w-[44px]">
              <div className="text-[9px] text-outline mb-0.5">{dayOfWeek}</div>
              <div className={`text-xl ${mood ? "" : "opacity-20"}`}>
                {mood ? EMOJI_MAP[mood.rating] : "\u{1F636}"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Full evaluation history */}
      {sortedEvals.length > 0 && (
        <div className="border-t border-surface-container-low pt-3 space-y-3">
          {sortedEvals.map((ev) => {
            const mood = moodByDate[ev.date];
            return (
              <div
                key={ev.id}
                className={`flex items-start gap-3 pb-3 border-b border-surface-container-low last:border-b-0${onEditEval ? " cursor-pointer hover:bg-surface-container-low/50 rounded-lg -mx-1 px-1 transition-colors" : ""}`}
                onClick={onEditEval ? () => onEditEval(ev) : undefined}
              >
                <div className="text-xl">
                  {mood ? EMOJI_MAP[mood.rating] : "\u{1F636}"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-on-surface capitalize">
                      {formatDate(ev.date)}
                    </span>
                    {ev.shared && (
                      <span className="bg-primary-container text-on-primary-container text-[9px] font-bold px-2 py-0.5 rounded-full">
                        Partage
                      </span>
                    )}
                    {onEditEval && (
                      <span className="material-symbols-outlined text-on-surface-variant text-sm">edit</span>
                    )}
                  </div>
                  {ev.notes && (
                    <p className="text-xs text-on-surface-variant leading-relaxed mb-2">
                      {ev.notes}
                    </p>
                  )}
                  {ev.element_ratings && ev.element_ratings.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap">
                      {ev.element_ratings.map((er, i) => (
                        <span
                          key={i}
                          className="bg-surface-container-low text-[10px] px-2 py-1 rounded-lg font-semibold"
                        >
                          {er.name}{" "}
                          <span className="text-primary">{er.rating}/5</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {sortedEvals.length === 0 && (
        <p className="text-xs text-outline text-center py-4">
          Aucune evaluation pour le moment
        </p>
      )}
    </div>
  );
}
