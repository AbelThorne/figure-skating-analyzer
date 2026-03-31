import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, TrainingMood } from "../api/client";

const EMOJIS = [
  { value: 1, emoji: "\u{1F61E}" },
  { value: 2, emoji: "\u{1F615}" },
  { value: 3, emoji: "\u{1F610}" },
  { value: 4, emoji: "\u{1F642}" },
  { value: 5, emoji: "\u{1F604}" },
];

interface Props {
  skaterId: number;
  today: string;
}

export default function MoodInput({ skaterId, today }: Props) {
  const queryClient = useQueryClient();

  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, today],
    queryFn: () =>
      api.training.moods.list({ skater_id: skaterId, from: today, to: today }),
  });

  const todayMood = moods?.[0] as TrainingMood | undefined;

  const createMutation = useMutation({
    mutationFn: (rating: number) =>
      api.training.moods.create({ skater_id: skaterId, date: today, rating }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["moods", skaterId] }),
  });

  const updateMutation = useMutation({
    mutationFn: (rating: number) =>
      api.training.moods.update(todayMood!.id, { rating }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["moods", skaterId] }),
  });

  const handleClick = (rating: number) => {
    if (todayMood) {
      updateMutation.mutate(rating);
    } else {
      createMutation.mutate(rating);
    }
  };

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
            Comment s'est passe l'entrainement ?
          </p>
          <div className="flex gap-3">
            {EMOJIS.map(({ value, emoji }) => (
              <button
                key={value}
                onClick={() => handleClick(value)}
                className={`text-[28px] transition-all cursor-pointer rounded-xl px-1.5 py-0.5 ${
                  todayMood?.rating === value
                    ? "bg-primary-container scale-110"
                    : "opacity-30 grayscale hover:opacity-60 hover:grayscale-0"
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>
        <p className="text-[10px] text-outline flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">visibility</span>
          Visible par vos coachs
        </p>
      </div>
    </div>
  );
}
