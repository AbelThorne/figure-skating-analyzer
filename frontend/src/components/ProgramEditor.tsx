import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

interface Props {
  skaterId: number;
  readOnly?: boolean;
}

export default function ProgramEditor({ skaterId, readOnly = false }: Props) {
  const queryClient = useQueryClient();
  const [activeSegment, setActiveSegment] = useState<"SP" | "FS">("SP");
  const [newElement, setNewElement] = useState("");

  const { data: programs } = useQuery({
    queryKey: ["programs", skaterId],
    queryFn: () => api.training.programs.list(skaterId),
  });

  const activeProgram = programs?.find((p) => p.segment === activeSegment);

  const upsertMutation = useMutation({
    mutationFn: (elements: string[]) =>
      api.training.programs.upsert({
        skater_id: skaterId,
        segment: activeSegment,
        elements,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["programs", skaterId] }),
  });

  const handleAdd = () => {
    const trimmed = newElement.trim();
    if (!trimmed) return;
    const current = activeProgram?.elements ?? [];
    upsertMutation.mutate([...current, trimmed]);
    setNewElement("");
  };

  const handleRemove = (index: number) => {
    const current = activeProgram?.elements ?? [];
    upsertMutation.mutate(current.filter((_, i) => i !== index));
  };

  const elements = activeProgram?.elements ?? [];

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-5">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
        Mon programme
      </p>
      <div className="flex gap-2 mb-3">
        {(["SP", "FS"] as const).map((seg) => (
          <button
            key={seg}
            onClick={() => setActiveSegment(seg)}
            className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase transition-colors ${
              activeSegment === seg
                ? "bg-primary-container text-on-primary-container"
                : "bg-surface-container text-on-surface-variant"
            }`}
          >
            {seg === "SP" ? "PC" : "PL"}
          </button>
        ))}
      </div>
      <div className="space-y-1">
        {elements.map((el, i) => (
          <div
            key={i}
            className="flex items-center justify-between text-sm text-on-surface-variant"
          >
            <span>{el}</span>
            {!readOnly && (
              <button
                onClick={() => handleRemove(i)}
                className="text-outline-variant hover:text-error text-xs"
              >
                <span className="material-symbols-outlined text-sm">
                  close
                </span>
              </button>
            )}
          </div>
        ))}
        {elements.length === 0 && (
          <p className="text-xs text-outline">Aucun element enregistre</p>
        )}
      </div>
      {!readOnly && (
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            value={newElement}
            onChange={(e) => setNewElement(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Ex: 3Lz"
            className="bg-surface-container rounded-lg px-3 py-1.5 text-xs flex-1 outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={handleAdd}
            className="text-primary text-xs font-semibold"
          >
            + Ajouter
          </button>
        </div>
      )}
    </div>
  );
}
