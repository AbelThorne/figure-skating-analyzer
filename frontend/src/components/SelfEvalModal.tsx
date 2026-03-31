import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ElementRating, SelfEvaluation } from "../api/client";

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
  existingEval?: SelfEvaluation;
  onClose: () => void;
}

export default function SelfEvalModal({
  skaterId,
  today,
  existingEval,
  onClose,
}: Props) {
  const queryClient = useQueryClient();
  const [evalDate, setEvalDate] = useState(existingEval?.date ?? today);
  const [moodRating, setMoodRating] = useState<number | null>(null);
  const [notes, setNotes] = useState(existingEval?.notes ?? "");
  const [elementRatings, setElementRatings] = useState<ElementRating[]>(
    existingEval?.element_ratings ?? []
  );
  const [shared, setShared] = useState(existingEval?.shared ?? false);
  const [newElement, setNewElement] = useState("");

  const { data: programs } = useQuery({
    queryKey: ["programs", skaterId],
    queryFn: () => api.training.programs.list(skaterId),
  });

  useEffect(() => {
    if (!existingEval && programs && elementRatings.length === 0) {
      const allElements: ElementRating[] = [];
      for (const p of programs) {
        for (const el of p.elements) {
          if (!allElements.find((e) => e.name === el)) {
            allElements.push({ name: el, rating: 0 });
          }
        }
      }
      if (allElements.length > 0) setElementRatings(allElements);
    }
  }, [programs, existingEval, elementRatings.length]);

  const { data: moods } = useQuery({
    queryKey: ["moods", skaterId, evalDate],
    queryFn: () =>
      api.training.moods.list({
        skater_id: skaterId,
        from: evalDate,
        to: evalDate,
      }),
  });

  useEffect(() => {
    if (moods?.[0]) setMoodRating(moods[0].rating);
  }, [moods]);

  const moodMutation = useMutation({
    mutationFn: (rating: number) => {
      if (moods?.[0])
        return api.training.moods.update(moods[0].id, { rating });
      return api.training.moods.create({
        skater_id: skaterId,
        date: evalDate,
        rating,
      });
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["moods"] }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.training.selfEvaluations.create({
        skater_id: skaterId,
        date: evalDate,
        notes: notes || undefined,
        element_ratings: elementRatings.filter((e) => e.rating > 0),
        shared,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["selfEvaluations"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api.training.selfEvaluations.update(existingEval!.id, {
        notes: notes || undefined,
        element_ratings: elementRatings.filter((e) => e.rating > 0),
        shared,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["selfEvaluations"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.training.selfEvaluations.delete(existingEval!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["selfEvaluations"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      onClose();
    },
  });

  const handleDelete = () => {
    if (confirm("Supprimer cette evaluation ?")) {
      deleteMutation.mutate();
    }
  };

  const handleSave = () => {
    if (moodRating) moodMutation.mutate(moodRating);
    if (existingEval) updateMutation.mutate();
    else createMutation.mutate();
  };

  const setRating = (index: number, rating: number) => {
    setElementRatings((prev) =>
      prev.map((e, i) => (i === index ? { ...e, rating } : e))
    );
  };

  const addElement = () => {
    const trimmed = newElement.trim();
    if (!trimmed || elementRatings.find((e) => e.name === trimmed)) return;
    setElementRatings((prev) => [...prev, { name: trimmed, rating: 0 }]);
    setNewElement("");
  };

  const removeElement = (index: number) => {
    setElementRatings((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-on-surface/30" />
      <div
        className="relative bg-surface-container-lowest rounded-2xl shadow-arctic p-6 w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-headline font-bold text-on-surface">
            Evaluer ma seance
          </h3>
          <button
            onClick={onClose}
            className="text-outline hover:text-on-surface"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Date
          </label>
          <input
            type="date"
            value={evalDate}
            onChange={(e) => setEvalDate(e.target.value)}
            disabled={!!existingEval}
            className="bg-surface-container-low rounded-lg px-3 py-2.5 text-sm w-full outline-none"
          />
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Humeur
          </label>
          <div className="flex gap-2.5">
            {EMOJIS.map(({ value, emoji }) => (
              <button
                key={value}
                onClick={() => setMoodRating(value)}
                className={`text-2xl rounded-xl px-1 py-0.5 transition-all ${
                  moodRating === value
                    ? "bg-primary-container"
                    : "opacity-30 hover:opacity-60"
                }`}
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-1.5">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Comment s'est passee la seance..."
            rows={3}
            className="bg-surface-container-low rounded-lg px-3 py-2.5 text-sm w-full outline-none resize-none"
          />
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant block mb-2">
            Elements techniques
          </label>
          <div className="space-y-2">
            {elementRatings.map((el, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-1.5 border-b border-surface-container-low"
              >
                <span className="text-sm font-semibold min-w-[70px]">
                  {el.name}
                </span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((v) => (
                    <button
                      key={v}
                      onClick={() => setRating(i, v)}
                      className={`w-7 h-7 rounded-full text-[11px] font-bold flex items-center justify-center transition-colors ${
                        v <= el.rating
                          ? "bg-primary text-on-primary"
                          : "bg-surface-container text-outline"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => removeElement(i)}
                  className="text-outline-variant hover:text-error ml-2"
                >
                  <span className="material-symbols-outlined text-sm">
                    close
                  </span>
                </button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <input
              type="text"
              value={newElement}
              onChange={(e) => setNewElement(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addElement()}
              placeholder="Ajouter un element"
              className="bg-surface-container rounded-lg px-3 py-1.5 text-xs flex-1 outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={addElement}
              className="text-primary text-xs font-semibold"
            >
              + Ajouter
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between py-3 border-t border-surface-container-low">
          <div>
            <p className="text-sm font-semibold">Partager avec les coachs</p>
            <p className="text-[10px] text-outline">
              Votre evaluation sera visible par l'equipe
            </p>
          </div>
          <button
            onClick={() => setShared(!shared)}
            className={`w-10 h-[22px] rounded-full relative transition-colors ${
              shared ? "bg-primary" : "bg-surface-container"
            }`}
          >
            <div
              className={`w-[18px] h-[18px] bg-surface-container-lowest rounded-full absolute top-[2px] shadow-sm transition-transform ${
                shared ? "translate-x-[20px]" : "translate-x-[2px]"
              }`}
            />
          </button>
        </div>

        <div className="flex gap-2 mt-3">
          {existingEval && (
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="px-4 py-3 rounded-lg text-sm font-bold text-error hover:bg-error/10 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-sm">delete</span>
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={createMutation.isPending || updateMutation.isPending}
            className="flex-1 bg-primary text-on-primary rounded-lg py-3 text-sm font-bold active:scale-95 transition-all disabled:opacity-50"
          >
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  );
}
