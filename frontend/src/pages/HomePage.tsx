import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Competition, CreateCompetitionPayload } from "../api/client";

export default function HomePage() {
  const qc = useQueryClient();
  const { data: competitions, isLoading, error } = useQuery({
    queryKey: ["competitions"],
    queryFn: api.competitions.list,
  });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateCompetitionPayload>({
    name: "",
    url: "",
    season: "",
    discipline: "",
  });

  const createMutation = useMutation({
    mutationFn: api.competitions.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      setShowForm(false);
      setForm({ name: "", url: "", season: "", discipline: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.competitions.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["competitions"] }),
  });

  const importMutation = useMutation({
    mutationFn: api.competitions.import,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["competitions"] });
      qc.invalidateQueries({ queryKey: ["scores"] });
      alert(
        `Import done:\n• ${result.events_found} events found\n• ${result.scores_imported} scores imported\n• ${result.scores_skipped} skipped` +
          (result.errors.length ? `\n• ${result.errors.length} errors` : "")
      );
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Competitions</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          + Add competition
        </button>
      </div>

      {showForm && (
        <form
          className="mb-6 bg-white border rounded p-4 space-y-3 shadow-sm"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate(form);
          }}
        >
          <h2 className="font-semibold text-lg">New competition</h2>
          <input
            className="w-full border rounded px-3 py-2"
            placeholder="Name"
            required
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
          <input
            className="w-full border rounded px-3 py-2"
            placeholder="Results website URL"
            required
            type="url"
            value={form.url}
            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
          />
          <div className="flex gap-3">
            <input
              className="flex-1 border rounded px-3 py-2"
              placeholder="Season (e.g. 2024-25)"
              value={form.season ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, season: e.target.value }))}
            />
            <input
              className="flex-1 border rounded px-3 py-2"
              placeholder="Discipline (e.g. Men, Ladies)"
              value={form.discipline ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, discipline: e.target.value }))
              }
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded border hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-red-600 text-sm">{String(createMutation.error)}</p>
          )}
        </form>
      )}

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-600">{String(error)}</p>}

      {competitions && competitions.length === 0 && (
        <p className="text-gray-500">No competitions yet. Add one to get started.</p>
      )}

      <div className="space-y-3">
        {competitions?.map((c: Competition) => (
          <div
            key={c.id}
            className="bg-white border rounded p-4 shadow-sm flex items-center justify-between"
          >
            <div>
              <Link
                to={`/competitions/${c.id}`}
                className="font-semibold text-blue-700 hover:underline"
              >
                {c.name}
              </Link>
              <div className="text-sm text-gray-500 mt-0.5">
                {[c.discipline, c.season, c.date].filter(Boolean).join(" · ")}
              </div>
              <div className="text-xs text-gray-400 mt-0.5 truncate max-w-md">
                {c.url}
              </div>
            </div>
            <div className="flex gap-2 ml-4 shrink-0">
              <button
                onClick={() => importMutation.mutate(c.id)}
                disabled={importMutation.isPending}
                className="text-sm bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 disabled:opacity-50"
              >
                Import
              </button>
              <button
                onClick={() => {
                  if (confirm(`Delete "${c.name}"?`)) deleteMutation.mutate(c.id);
                }}
                className="text-sm bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
