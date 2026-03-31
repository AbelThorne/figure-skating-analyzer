import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

interface Props {
  skaterId: number;
  readOnly?: boolean;
}

function SortableElement({
  id,
  name,
  readOnly,
  onRemove,
}: {
  id: string;
  name: string;
  readOnly: boolean;
  onRemove: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center justify-between text-sm text-on-surface-variant"
    >
      <div className="flex items-center gap-1.5">
        {!readOnly && (
          <span
            className="material-symbols-outlined text-outline-variant text-sm cursor-grab active:cursor-grabbing"
            {...attributes}
            {...listeners}
          >
            drag_indicator
          </span>
        )}
        <span>{name}</span>
      </div>
      {!readOnly && (
        <button
          onClick={onRemove}
          className="text-outline-variant hover:text-error text-xs"
        >
          <span className="material-symbols-outlined text-sm">close</span>
        </button>
      )}
    </div>
  );
}

export default function ProgramEditor({ skaterId, readOnly = false }: Props) {
  const queryClient = useQueryClient();
  const [activeSegment, setActiveSegment] = useState<"SP" | "FS">("FS");
  const [inputValue, setInputValue] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const { data: programs } = useQuery({
    queryKey: ["programs", skaterId],
    queryFn: () => api.training.programs.list(skaterId),
  });

  const { data: knownElements } = useQuery({
    queryKey: ["elementNames", skaterId],
    queryFn: () => api.skaters.elementNames(skaterId),
  });

  const activeProgram = programs?.find((p) => p.segment === activeSegment);
  const elements = activeProgram?.elements ?? [];

  const filteredSuggestions =
    inputValue.trim().length > 0
      ? (knownElements ?? []).filter(
          (name) =>
            name.toLowerCase().includes(inputValue.toLowerCase()) &&
            !elements.includes(name)
        )
      : [];

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const upsertMutation = useMutation({
    mutationFn: (newElements: string[]) =>
      api.training.programs.upsert({
        skater_id: skaterId,
        segment: activeSegment,
        elements: newElements,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["programs", skaterId] }),
  });

  const handleAdd = (value?: string) => {
    const trimmed = (value ?? inputValue).trim();
    if (!trimmed || elements.includes(trimmed)) return;
    upsertMutation.mutate([...elements, trimmed]);
    setInputValue("");
    setShowSuggestions(false);
    setHighlightedIndex(-1);
  };

  const handleRemove = (index: number) => {
    upsertMutation.mutate(elements.filter((_, i) => i !== index));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = elements.indexOf(active.id as string);
    const newIndex = elements.indexOf(over.id as string);
    if (oldIndex === -1 || newIndex === -1) return;
    upsertMutation.mutate(arrayMove(elements, oldIndex, newIndex));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) =>
        prev < filteredSuggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && filteredSuggestions[highlightedIndex]) {
        handleAdd(filteredSuggestions[highlightedIndex]);
      } else {
        handleAdd();
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
      setHighlightedIndex(-1);
    }
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Generate unique sortable IDs — use element name since elements are unique within a program
  const sortableIds = elements.map((el) => el);

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
        {elements.length === 0 && (
          <p className="text-xs text-outline">Aucun element enregistre</p>
        )}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={sortableIds}
            strategy={verticalListSortingStrategy}
          >
            {elements.map((el, i) => (
              <SortableElement
                key={el}
                id={el}
                name={el}
                readOnly={readOnly}
                onRemove={() => handleRemove(i)}
              />
            ))}
          </SortableContext>
        </DndContext>
      </div>
      {!readOnly && (
        <div className="mt-2 relative">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setShowSuggestions(true);
                setHighlightedIndex(-1);
              }}
              onFocus={() => setShowSuggestions(true)}
              onKeyDown={handleKeyDown}
              placeholder="Ex: 3Lz"
              className="bg-surface-container rounded-lg px-3 py-1.5 text-xs flex-1 outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={() => handleAdd()}
              className="text-primary text-xs font-semibold"
            >
              + Ajouter
            </button>
          </div>
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div
              ref={suggestionsRef}
              className="absolute left-0 right-12 mt-1 bg-surface-container-lowest rounded-lg shadow-arctic z-10 max-h-40 overflow-y-auto"
            >
              {filteredSuggestions.map((name, i) => (
                <button
                  key={name}
                  onClick={() => handleAdd(name)}
                  className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                    i === highlightedIndex
                      ? "bg-primary-container text-on-primary-container"
                      : "text-on-surface hover:bg-surface-container"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
