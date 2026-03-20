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
  components: Record<string, number> | null;
  elements: Array<Record<string, unknown>> | null;
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
  status: "success" | "partial" | "error";
  events_found: number;
  scores_imported: number;
  scores_skipped: number;
  errors: { skater: string; error: string }[];
}

export interface NeverImported {
  status: "never_imported";
}

export type ImportStatus = ImportResult | NeverImported;

export interface DashboardMedal {
  skater_name: string;
  rank: number;
  competition_name: string;
  segment: string;
  category: string | null;
}

export interface DashboardTopScore {
  skater_name: string;
  tss: number;
  competition_name: string;
  competition_date: string | null;
  segment: string;
}

export interface DashboardMostImproved {
  skater_name: string;
  skater_id: number;
  tss_gain: number;
  first_tss: number;
  last_tss: number;
}

export interface DashboardRecentCompetition {
  id: number;
  name: string;
  date: string | null;
  season: string | null;
  discipline: string | null;
}

export interface Dashboard {
  club_name: string;
  season: string;
  active_skaters: number;
  competitions_tracked: number;
  total_programs: number;
  medals: DashboardMedal[];
  top_scores: DashboardTopScore[];
  most_improved: DashboardMostImproved[];
  recent_competitions: DashboardRecentCompetition[];
}

export interface Element {
  score_id: number;
  competition_id: number;
  competition_name: string | null;
  competition_date: string | null;
  segment: string;
  category: string | null;
  element_name: string;
  base_value: number | null;
  goe: number | null;
  judges: number[] | null;
  total: number | null;
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
    reimport: (id: number) =>
      request<ImportResult>(`/competitions/${id}/import?force=true`, { method: "POST" }),
    importStatus: (id: number) =>
      request<ImportStatus>(`/competitions/${id}/import-status`),
  },

  skaters: {
    list: () => request<Skater[]>("/skaters/"),
    get: (id: number) => request<Skater>(`/skaters/${id}`),
    scores: (id: number) => request<Score[]>(`/skaters/${id}/scores`),
    elements: (id: number, elementType?: string) => {
      const qs = elementType ? `?element_type=${encodeURIComponent(elementType)}` : "";
      return request<Element[]>(`/skaters/${id}/elements${qs}`);
    },
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
    elements: (id: number) => request<Element[]>(`/scores/${id}/elements`),
  },

  dashboard: {
    get: (season?: string) => {
      const qs = season ? `?season=${encodeURIComponent(season)}` : "";
      return request<Dashboard>(`/dashboard/${qs}`);
    },
  },
};
