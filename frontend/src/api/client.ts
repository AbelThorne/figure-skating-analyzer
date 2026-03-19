const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Types ---

export interface Competition {
  id: number;
  name: string;
  url: string;
  date: string | null;
  season: string | null;
  discipline: string | null;
}

export interface CreateCompetitionPayload {
  name: string;
  url: string;
  date?: string;
  season?: string;
  discipline?: string;
}

export interface Score {
  id: number;
  competition_id: number;
  competition_name: string | null;
  competition_date: string | null;
  skater_id: number;
  skater_name: string | null;
  skater_nationality: string | null;
  skater_club: string | null;
  segment: string;
  category: string | null;
  starting_number: number | null;
  rank: number | null;
  total_score: number | null;
  technical_score: number | null;
  component_score: number | null;
  deductions: number | null;
}

export interface Skater {
  id: number;
  name: string;
  nationality: string | null;
  club: string | null;
  birth_year: number | null;
}

export interface ImportResult {
  competition_id: number;
  site_competitors_found: number;
  pdfs_downloaded: number;
  scores_imported: number;
  errors: { file: string; error: string }[];
}

// --- API Functions ---

export const api = {
  competitions: {
    list: () => request<Competition[]>("/competitions/"),
    get: (id: number) => request<Competition>(`/competitions/${id}`),
    create: (data: CreateCompetitionPayload) =>
      request<Competition>("/competitions/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/competitions/${id}`, { method: "DELETE" }),
    import: (id: number) =>
      request<ImportResult>(`/competitions/${id}/import`, { method: "POST" }),
  },

  skaters: {
    list: () => request<Skater[]>("/skaters/"),
    get: (id: number) => request<Skater>(`/skaters/${id}`),
    scores: (id: number) => request<Score[]>(`/skaters/${id}/scores`),
  },

  scores: {
    list: (params?: {
      competition_id?: number;
      skater_id?: number;
      segment?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.competition_id !== undefined)
        qs.set("competition_id", String(params.competition_id));
      if (params?.skater_id !== undefined)
        qs.set("skater_id", String(params.skater_id));
      if (params?.segment) qs.set("segment", params.segment);
      const query = qs.toString() ? `?${qs}` : "";
      return request<Score[]>(`/scores/${query}`);
    },
  },
};
