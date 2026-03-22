const BASE = "/api";

let _accessToken: string | null = null;
let _refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

async function _tryRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    _accessToken = data.access_token;
    return _accessToken;
  } catch {
    return null;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  let res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // On 401, try silent refresh once
  if (res.status === 401 && _accessToken) {
    if (!_refreshPromise) {
      _refreshPromise = _tryRefresh();
    }
    const newToken = await _refreshPromise;
    _refreshPromise = null;

    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${BASE}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    }
  }

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

export interface ScoreElement {
  number: number;
  name: string;                 // clean element code, markers stripped (e.g. "3Lz")
  markers: string[];            // ISU markers: "<", "<<", "q", "e", "!", "*", "x"
  base_value: number;           // base value (×1.10 already applied when "x" present)
  judge_goe: number[];          // per-judge GOE scores (−5 to +5), length 3–9
  goe: number;                  // panel GOE (trimmed mean)
  score: number;                // final element score (base_value + goe)
  info_flag: string | null;     // reserved
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
  elements: ScoreElement[] | null;
}

export interface CategoryResult {
  id: number;
  competition_id: number;
  competition_name: string | null;
  competition_date: string | null;
  skater_id: number;
  skater_name: string | null;
  skater_nationality: string | null;
  skater_club: string | null;
  category: string;
  overall_rank: number | null;
  combined_total: number | null;
  segment_count: number;
  sp_rank: number | null;
  fs_rank: number | null;
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
  category_results_imported: number;
  category_results_skipped: number;
  errors: { skater: string; error: string }[];
}

export interface EnrichResult {
  competition_id: number;
  pdfs_downloaded: number;
  scores_enriched: number;
  unmatched: string[];
  errors: { file: string; error: string }[];
}

export interface NeverImported {
  status: "never_imported";
}

export type ImportStatus = ImportResult | NeverImported;

export interface DashboardMedal {
  skater_name: string;
  rank: number;
  competition_name: string;
  category: string | null;
  combined_total: number | null;
  segment_count: number;
}

export interface DashboardTopScore {
  skater_id: number;
  skater_name: string;
  tss: number;
  competition_name: string;
  competition_date: string | null;
  category: string | null;
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
  markers: string[];
}

export interface ClubConfig {
  club_name: string;
  club_short: string;
  logo_url: string;
}

// --- Auth Types ---

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader";
}

export interface LoginResponse {
  access_token: string;
  user: AuthUser;
}

export interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader";
  is_active: boolean;
  google_oauth_enabled: boolean;
}

export interface AllowedDomainRecord {
  id: string;
  domain: string;
  created_at: string;
}

export interface ConfigResponse {
  setup_required: boolean;
  club_name?: string;
  club_short?: string;
  logo_url?: string;
  current_season?: string;
  google_client_id?: string;
}

export interface BulkImportResult {
  lot_name: string;
  results: {
    url: string;
    name?: string;
    status: string;
    competition_id: number | null;
    error: string | null;
    import_result: { scores_imported: number; scores_skipped: number; errors_count: number } | null;
    enrich_result: { scores_enriched: number; pdfs_downloaded: number; error?: string } | null;
  }[];
  total: number;
  succeeded: number;
  failed: number;
}

// --- API Functions ---

export const api = {
  config: {
    get: () => request<ConfigResponse>("/config/"),
    update: (data: { club_name?: string; club_short?: string; current_season?: string }) =>
      request<ConfigResponse>("/config/", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    uploadLogo: async (file: File): Promise<{ logo_url: string }> => {
      const form = new FormData();
      form.append("data", file);
      const headers: Record<string, string> = {};
      if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;
      const res = await fetch(`${BASE}/config/logo`, {
        method: "POST",
        headers,
        body: form,
        credentials: "include",
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    },
  },

  auth: {
    login: (email: string, password: string) =>
      request<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    loginWithGoogle: (credential: string) =>
      request<LoginResponse>("/auth/google", {
        method: "POST",
        body: JSON.stringify({ credential }),
      }),
    refresh: () =>
      request<LoginResponse>("/auth/refresh", { method: "POST" }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    setup: (data: {
      email: string;
      password: string;
      display_name: string;
      club_name: string;
      club_short: string;
    }) =>
      request<LoginResponse>("/auth/setup", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  users: {
    list: () => request<UserRecord[]>("/users/"),
    create: (data: {
      email: string;
      display_name: string;
      role: string;
      password?: string;
    }) =>
      request<UserRecord>("/users/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Partial<UserRecord>) =>
      request<UserRecord>(`/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/users/${id}`, { method: "DELETE" }),
  },

  domains: {
    list: () => request<AllowedDomainRecord[]>("/domains/"),
    create: (domain: string) =>
      request<AllowedDomainRecord>("/domains/", {
        method: "POST",
        body: JSON.stringify({ domain }),
      }),
    delete: (id: string) =>
      request<void>(`/domains/${id}`, { method: "DELETE" }),
  },

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
    enrich: (id: number) =>
      request<EnrichResult>(`/competitions/${id}/enrich`, { method: "POST" }),
    importStatus: (id: number) =>
      request<ImportStatus>(`/competitions/${id}/import-status`),
    bulkImport: (data: { lot_name: string; urls: string[]; enrich: boolean; season?: string; discipline?: string }) =>
      request<BulkImportResult>("/competitions/bulk-import", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  skaters: {
    list: (club?: string) => {
      const qs = club ? `?club=${encodeURIComponent(club)}` : "";
      return request<Skater[]>(`/skaters/${qs}`);
    },
    get: (id: number) => request<Skater>(`/skaters/${id}`),
    scores: (id: number) => request<Score[]>(`/skaters/${id}/scores`),
    categoryResults: (id: number) =>
      request<CategoryResult[]>(`/skaters/${id}/category-results`),
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
    categoryResults: (params?: {
      competition_id?: number;
      skater_id?: number;
    }) => {
      const qs = new URLSearchParams();
      if (params?.competition_id !== undefined)
        qs.set("competition_id", String(params.competition_id));
      if (params?.skater_id !== undefined)
        qs.set("skater_id", String(params.skater_id));
      const query = qs.toString() ? `?${qs}` : "";
      return request<CategoryResult[]>(`/scores/category-results${query}`);
    },
  },

  dashboard: {
    get: (season?: string) => {
      const qs = season ? `?season=${encodeURIComponent(season)}` : "";
      return request<Dashboard>(`/dashboard/${qs}`);
    },
  },
};
