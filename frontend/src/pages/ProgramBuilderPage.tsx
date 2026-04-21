import { useState } from "react";
import { useSovData } from "../hooks/useSovData";
import { useProgramRules } from "../hooks/useProgramRules";
import { useProgramBuilder } from "../hooks/useProgramBuilder";
import ElementPicker from "../components/program-builder/ElementPicker";
import ProgramTable from "../components/program-builder/ProgramTable";
import CompetitionLoader from "../components/program-builder/CompetitionLoader";
import CategoryPanel from "../components/program-builder/CategoryPanel";

export default function ProgramBuilderPage() {
  const { data: sov, isLoading: sovLoading } = useSovData();
  const { data: rules, isLoading: rulesLoading } = useProgramRules();
  const [includePairs, setIncludePairs] = useState(false);

  const {
    elements,
    addElement,
    updateMarkers,
    updateComboJumpMarkers,
    addComboJump,
    replaceElement,
    deleteElement,
    loadFromScore,
    clearProgram,
  } = useProgramBuilder(sov);

  if (sovLoading || rulesLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <span className="material-symbols-outlined animate-spin text-primary text-3xl">
          progress_activity
        </span>
      </div>
    );
  }

  if (!sov) {
    return (
      <div className="text-center text-on-surface-variant py-12">
        Erreur de chargement des données SOV.
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left column — main content */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* Competition loader */}
        <CompetitionLoader onLoad={loadFromScore} />

        {/* Element picker + controls */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <ElementPicker
              sov={sov}
              includePairs={includePairs}
              onSelect={addElement}
              placeholder="Ajouter un élément..."
            />
          </div>

          <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={includePairs}
              onChange={e => setIncludePairs(e.target.checked)}
              className="rounded"
            />
            Éléments couples
          </label>

          {elements.length > 0 && (
            <button
              onClick={clearProgram}
              className="text-xs text-on-surface-variant hover:text-error transition-colors shrink-0"
            >
              Tout effacer
            </button>
          )}
        </div>

        {/* Program table */}
        <ProgramTable
          sov={sov}
          elements={elements}
          includePairs={includePairs}
          onUpdateMarkers={updateMarkers}
          onUpdateComboJumpMarkers={updateComboJumpMarkers}
          onAddComboJump={addComboJump}
          onReplaceElement={replaceElement}
          onDeleteElement={deleteElement}
        />
      </div>

      {/* Right column — category panel (stacks below on mobile) */}
      <div className="lg:w-80 shrink-0">
        <div className="lg:sticky lg:top-20">
          <CategoryPanel elements={elements} rulesData={rules} />
        </div>
      </div>
    </div>
  );
}
