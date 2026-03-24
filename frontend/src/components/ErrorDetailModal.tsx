import { useEffect } from "react";
import type { ImportResult, EnrichResult } from "../api/client";
import type { FailedJobError } from "../contexts/JobContext";

interface ErrorDetailModalProps {
  competitionName: string;
  importResult?: ImportResult;
  enrichResult?: EnrichResult;
  failedError?: FailedJobError;
  onClose: () => void;
}

const JOB_TYPE_LABELS: Record<string, string> = {
  import: "Importation",
  reimport: "Réimportation",
  enrich: "Enrichissement PDF",
};

export default function ErrorDetailModal({
  competitionName,
  importResult,
  enrichResult,
  failedError,
  onClose,
}: ErrorDetailModalProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const importErrors = importResult?.errors ?? [];
  const enrichErrors = enrichResult?.errors ?? [];
  const hasPartialErrors = importErrors.length > 0 || enrichErrors.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-container-lowest rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4">
          <div>
            <h2 className="font-headline font-bold text-on-surface text-base">
              Détails des erreurs
            </h2>
            <p className="text-xs text-on-surface-variant mt-0.5">
              {competitionName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface transition-colors p-1 rounded-lg hover:bg-surface-container"
            aria-label="Fermer"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto px-6 pb-6 space-y-5">
          {/* Partial import errors */}
          {importErrors.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-2">
                Erreurs d'importation ({importErrors.length})
              </h3>
              <div className="bg-error-container/20 rounded-xl overflow-x-auto">
                <table className="w-full min-w-[400px] text-xs">
                  <thead>
                    <tr className="text-left text-on-surface-variant">
                      <th className="px-4 py-2 font-semibold">Patineur</th>
                      <th className="px-4 py-2 font-semibold">Erreur</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importErrors.map((e, i) => (
                      <tr
                        key={i}
                        className="border-t border-error/10"
                      >
                        <td className="px-4 py-2 text-on-surface font-medium whitespace-nowrap">
                          {e.skater}
                        </td>
                        <td className="px-4 py-2 text-error/80 break-all">
                          {e.error}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Partial enrich errors */}
          {enrichErrors.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-2">
                Erreurs d'enrichissement ({enrichErrors.length})
              </h3>
              <div className="bg-error-container/20 rounded-xl overflow-x-auto">
                <table className="w-full min-w-[400px] text-xs">
                  <thead>
                    <tr className="text-left text-on-surface-variant">
                      <th className="px-4 py-2 font-semibold">Fichier</th>
                      <th className="px-4 py-2 font-semibold">Erreur</th>
                    </tr>
                  </thead>
                  <tbody>
                    {enrichErrors.map((e, i) => (
                      <tr
                        key={i}
                        className="border-t border-error/10"
                      >
                        <td className="px-4 py-2 text-on-surface font-medium whitespace-nowrap">
                          {e.file}
                        </td>
                        <td className="px-4 py-2 text-error/80 break-all">
                          {e.error}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Full failure error */}
          {failedError && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-2">
                Échec complet — {JOB_TYPE_LABELS[failedError.type] ?? failedError.type}
              </h3>
              <div className="bg-error-container/20 rounded-xl p-4">
                <pre className="text-xs text-error/90 font-mono whitespace-pre-wrap break-all">
                  {failedError.error}
                </pre>
              </div>
            </section>
          )}

          {/* Edge case: nothing to show */}
          {!hasPartialErrors && !failedError && (
            <p className="text-sm text-on-surface-variant">
              Aucune erreur détaillée disponible.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
