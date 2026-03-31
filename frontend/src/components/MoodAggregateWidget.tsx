import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

const EMOJI_MAP: Record<number, string> = {
  1: "\u{1F61E}",
  2: "\u{1F615}",
  3: "\u{1F610}",
  4: "\u{1F642}",
  5: "\u{1F604}",
};

function averageEmoji(avg: number): string {
  return EMOJI_MAP[Math.round(avg)] ?? "\u{1F610}";
}

interface Props {
  currentWeekStart: string;
  currentWeekEnd: string;
  previousWeekStart: string;
  previousWeekEnd: string;
}

export default function MoodAggregateWidget({
  currentWeekStart,
  currentWeekEnd,
  previousWeekStart,
  previousWeekEnd,
}: Props) {
  const { data: current } = useQuery({
    queryKey: ["moodSummary", currentWeekStart, currentWeekEnd],
    queryFn: () =>
      api.training.moods.weeklySummary({
        from: currentWeekStart,
        to: currentWeekEnd,
      }),
  });

  const { data: previous } = useQuery({
    queryKey: ["moodSummary", previousWeekStart, previousWeekEnd],
    queryFn: () =>
      api.training.moods.weeklySummary({
        from: previousWeekStart,
        to: previousWeekEnd,
      }),
  });

  if (!current) return null;

  const maxDist = Math.max(...(current.distribution ?? [1]));
  const trend =
    current.average != null && previous?.average != null
      ? +(current.average - previous.average).toFixed(1)
      : null;

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
          Humeur du groupe
        </p>
        <p className="text-[10px] text-outline">
          Semaine du{" "}
          {new Date(currentWeekStart + "T00:00:00").toLocaleDateString(
            "fr-FR",
            {
              day: "numeric",
              month: "long",
            }
          )}
        </p>
      </div>

      <div className="flex gap-5 items-start">
        <div className="text-center min-w-[80px]">
          <div className="text-[40px] mb-1">
            {current.average != null
              ? averageEmoji(current.average)
              : "\u{1F636}"}
          </div>
          <div className="font-headline text-[28px] font-extrabold text-on-surface">
            {current.average ?? "\u2014"}
          </div>
          <div className="text-[10px] text-outline">sur 5</div>
        </div>

        <div className="flex-1">
          <div className="flex items-end gap-2 h-[60px] mb-2">
            {current.distribution.map((count, i) => (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div className="text-[9px] text-outline mb-0.5">{count}</div>
                <div
                  className={`w-full rounded-t ${i >= 3 ? "bg-primary" : "bg-primary-container"}`}
                  style={{
                    height: `${maxDist > 0 ? (count / maxDist) * 50 : 4}px`,
                    minHeight: "4px",
                  }}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((v) => (
              <div key={v} className="flex-1 text-center text-sm">
                {EMOJI_MAP[v]}
              </div>
            ))}
          </div>
        </div>

        {trend !== null && (
          <div className="text-center min-w-[70px] pt-2">
            <p className="text-[10px] font-black uppercase tracking-wider text-on-surface-variant mb-1">
              Tendance
            </p>
            <div className="flex items-center justify-center gap-1">
              <span
                className={`text-lg ${trend >= 0 ? "text-primary" : "text-error"}`}
              >
                {trend >= 0 ? "\u25B2" : "\u25BC"}
              </span>
              <span
                className={`font-headline text-base font-bold ${trend >= 0 ? "text-primary" : "text-error"}`}
              >
                {trend >= 0 ? "+" : ""}
                {trend}
              </span>
            </div>
            <p className="text-[9px] text-outline">vs semaine prec.</p>
          </div>
        )}
      </div>

      <div className="mt-3 pt-2.5 border-t border-surface-container-low flex items-center gap-1.5">
        <span className="text-[10px] text-outline">
          {current.count} evaluations cette semaine
        </span>
        <span className="text-[10px] text-outline">&middot;</span>
        <span className="text-[10px] text-outline">Donnees anonymes</span>
      </div>
    </div>
  );
}
