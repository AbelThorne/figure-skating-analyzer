const BASE = import.meta.env.VITE_API_URL || "/api";

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

export async function downloadPdf(path: string, filename?: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  let res = await fetch(`${BASE}${path}`, { headers, credentials: "include" });

  if (res.status === 401 && _accessToken) {
    if (!_refreshPromise) _refreshPromise = _tryRefresh();
    const newToken = await _refreshPromise;
    _refreshPromise = null;
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${BASE}${path}`, { headers, credentials: "include" });
    }
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || res.headers.get("content-disposition")?.match(/filename="?(.+?)"?$/)?.[1] || "rapport.pdf";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- Types ---

export interface Competition {
  id: number;
  name: string;
  url: string;
  date: string | null;
  season: string | null;
  discipline: string | null;
  city: string | null;
  country: string | null;
  rink: string | null;
  competition_type: string | null;
  metadata_confirmed: boolean;
}

export const COMPETITION_TYPES: Record<string, string> = {
  cr: "Compétition Régionale",
  tf: "Trophée Fédéral",
  tdf: "Tournoi de France",
  masters: "Masters",
  nationales_autres: "Nationales Autres",
  championnats_france: "Championnats de France",
  france_clubs: "France Clubs",
  grand_prix: "Grand Prix",
  championnats_europe: "Championnats d'Europe",
  championnats_monde: "Championnats du Monde",
  championnats_monde_junior: "Championnats du Monde Junior",
  jeux_olympiques: "Jeux Olympiques",
  autre: "Autre",
};

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
  skater_first_name: string | null;
  skater_last_name: string | null;
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
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
  pdf_url: string | null;
}

export interface CategoryResult {
  id: number;
  competition_id: number;
  competition_name: string | null;
  competition_date: string | null;
  skater_id: number;
  skater_first_name: string | null;
  skater_last_name: string | null;
  skater_nationality: string | null;
  skater_club: string | null;
  category: string;
  overall_rank: number | null;
  combined_total: number | null;
  segment_count: number;
  sp_rank: number | null;
  fs_rank: number | null;
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
}

export interface Skater {
  id: number;
  first_name: string;
  last_name: string;
  nationality: string | null;
  club: string | null;
  birth_year: number | null;
  training_tracked: boolean;
  manual_create: boolean;
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
  role: "admin" | "reader" | "skater" | "coach";
  must_change_password: boolean;
  has_password: boolean;
}

export interface LoginResponse {
  access_token: string;
  user: AuthUser;
}

export interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "reader" | "skater" | "coach";
  is_active: boolean;
  google_oauth_enabled: boolean;
  skater_ids: number[];
  last_login_at: string | null;
}

export interface MySkater {
  id: number;
  first_name: string;
  last_name: string;
  club: string;
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
  job_ids: string[];
  total: number;
}

export interface JobInfo {
  id: string;
  type: "import" | "reimport" | "enrich";
  competition_id: number;
  status: "queued" | "running" | "completed" | "failed";
  result: ImportResult | EnrichResult | null;
  error: string | null;
  created_at: string;
}

export interface ProgressionRankingEntry {
  skater_id: number;
  skater_name: string;
  skating_level: string | null;
  age_group: string | null;
  gender: string | null;
  first_tss: number;
  last_tss: number;
  tss_gain: number;
  competitions_count: number;
  sparkline: { date: string | null; value: number }[];
}

export interface BenchmarkData {
  skating_level: string;
  age_group: string;
  gender: string;
  data_points: number;
  min: number | null;
  max: number | null;
  median: number | null;
  p25: number | null;
  p75: number | null;
}

// --- Training Tracking Types ---

export interface WeeklyReview {
  id: number;
  skater_id: number;
  coach_id: string;
  week_start: string;
  attendance: string;
  engagement: number;
  progression: number;
  attitude: number;
  strengths: string;
  improvements: string;
  visible_to_skater: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateReviewPayload {
  skater_id: number;
  week_start: string;
  attendance: string;
  engagement: number;
  progression: number;
  attitude: number;
  strengths: string;
  improvements: string;
  visible_to_skater: boolean;
}

export interface UpdateReviewPayload {
  attendance?: string;
  engagement?: number;
  progression?: number;
  attitude?: number;
  strengths?: string;
  improvements?: string;
  visible_to_skater?: boolean;
}

export interface TrainingIncident {
  id: number;
  skater_id: number;
  coach_id: string;
  date: string;
  incident_type: "injury" | "behavior" | "other";
  description: string;
  visible_to_skater: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateIncidentPayload {
  skater_id: number;
  date: string;
  incident_type: "injury" | "behavior" | "other";
  description: string;
  visible_to_skater: boolean;
}

export interface UpdateIncidentPayload {
  date?: string;
  incident_type?: "injury" | "behavior" | "other";
  description?: string;
  visible_to_skater?: boolean;
}

export interface TrainingChallenge {
  id: number;
  skater_id: number;
  coach_id: string;
  objective: string;
  target_date: string;
  score: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateChallengePayload {
  skater_id: number;
  objective: string;
  target_date: string;
}

export interface UpdateChallengePayload {
  objective?: string;
  target_date?: string;
  score?: number;
}

export type TimelineEntry = (WeeklyReview & { type: "review"; sort_date: string }) | (TrainingIncident & { type: "incident"; sort_date: string });

export interface JumpMastery {
  jump_type: string;
  attempts: number;
  positive_goe_pct: number;
  negative_goe_pct: number;
  neutral_goe_pct: number;
  avg_goe: number;
}

export interface LevelMastery {
  element_type: string;
  attempts: number;
  level_distribution: Record<string, number>;
  avg_goe: number;
}

export interface ElementMasteryData {
  jumps: JumpMastery[];
  spins: LevelMastery[];
  steps: LevelMastery[];
}

// --- Competition Club Analysis ---

export interface ClubChallengeEntry {
  club: string;
  total_points: number;
  podium_points: number;
  rank: number;
  is_my_club: boolean;
}

export interface CategoryBreakdownClub {
  club: string;
  points: number;
  podium_points: number;
}

export interface CategoryBreakdownSkater {
  skater_name: string;
  rank: number;
  base_points: number;
  podium_points: number;
  total_points: number;
}

export interface CategoryBreakdown {
  category: string;
  clubs: CategoryBreakdownClub[];
  club_skaters: CategoryBreakdownSkater[];
}

export interface MedalEntry {
  skater_id: number;
  skater_name: string;
  category: string;
  rank: 1 | 2 | 3;
  combined_total: number;
}

export interface CategoryCoverageEntry {
  category: string;
  club_skaters: number;
  total_skaters: number;
}

export interface ClubSkaterResult {
  skater_id: number;
  skater_name: string;
  category: string;
  overall_rank: number | null;
  total_skaters: number;
  combined_total: number | null;
  is_pb: boolean;
  medal: 1 | 2 | 3 | null;
}

export interface CompetitionClubAnalysis {
  competition: { id: number; name: string; date: string; season: string };
  club_name: string;
  kpis: {
    skaters_entered: number;
    total_medals: number;
    personal_bests: number;
    categories_entered: number;
    categories_total: number;
  };
  club_challenge: {
    ranking: ClubChallengeEntry[];
    category_breakdown: CategoryBreakdown[];
  };
  medals: MedalEntry[];
  categories: CategoryCoverageEntry[];
  results: ClubSkaterResult[];
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
    changePassword: (currentPassword: string, newPassword: string) =>
      request<LoginResponse>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
  },

  me: {
    skaters: (): Promise<MySkater[]> => request<MySkater[]>("/me/skaters"),
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
    list: (params?: { club?: string; season?: string; my_club?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.club) qs.set("club", params.club);
      if (params?.season) qs.set("season", params.season);
      if (params?.my_club) qs.set("my_club", "true");
      const query = qs.toString() ? `?${qs}` : "";
      return request<Competition[]>(`/competitions/${query}`);
    },
    seasons: () => request<string[]>("/competitions/seasons"),
    get: (id: number) => request<Competition>(`/competitions/${id}`),
    create: (data: CreateCompetitionPayload) =>
      request<Competition>("/competitions/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/competitions/${id}`, { method: "DELETE" }),
    import: (id: number) =>
      request<JobInfo>(`/competitions/${id}/import`, { method: "POST" }),
    reimport: (id: number) =>
      request<JobInfo>(`/competitions/${id}/import?force=true`, { method: "POST" }),
    enrich: (id: number) =>
      request<JobInfo>(`/competitions/${id}/enrich`, { method: "POST" }),
    importStatus: (id: number) =>
      request<ImportStatus>(`/competitions/${id}/import-status`),
    bulkImport: (data: { lot_name: string; urls: string[]; enrich: boolean; season?: string; discipline?: string }) =>
      request<BulkImportResult>("/competitions/bulk-import", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Pick<Competition, "city" | "country" | "competition_type" | "season">>) =>
      request<Competition>(`/competitions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    confirmMetadata: (id: number) =>
      request<Competition>(`/competitions/${id}/confirm-metadata`, { method: "POST" }),
    backfillMetadata: () =>
      request<{ status: string; competitions_updated: number }>("/competitions/backfill-metadata", { method: "POST" }),
  },

  jobs: {
    list: () => request<JobInfo[]>("/jobs/"),
    get: (id: string) => request<JobInfo>(`/jobs/${id}`),
  },

  admin: {
    resetDatabase: () =>
      request<{ status: string; message: string }>("/admin/reset-database", { method: "POST" }),
  },

  skaters: {
    list: (params?: { club?: string; search?: string; training_tracked?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.club) qs.set("club", params.club);
      if (params?.search) qs.set("search", params.search);
      if (params?.training_tracked !== undefined) qs.set("training_tracked", String(params.training_tracked));
      const query = qs.toString() ? `?${qs}` : "";
      return request<Skater[]>(`/skaters/${query}`);
    },
    get: (id: number) => request<Skater>(`/skaters/${id}`),
    create: (data: { first_name: string; last_name: string; nationality?: string; club?: string }) =>
      request<Skater>("/skaters/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Pick<Skater, "first_name" | "last_name" | "nationality" | "club" | "training_tracked">>) =>
      request<Skater>(`/skaters/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    clearTrainingData: (id: number) =>
      request<{ deleted: number }>(`/skaters/${id}/training-data`, { method: "DELETE" }),
    seasons: (id: number) => request<string[]>(`/skaters/${id}/seasons`),
    scores: (id: number, season?: string) => {
      const qs = new URLSearchParams();
      if (season) qs.set("season", season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<Score[]>(`/skaters/${id}/scores${query}`);
    },
    categoryResults: (id: number, season?: string) => {
      const qs = new URLSearchParams();
      if (season) qs.set("season", season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<CategoryResult[]>(`/skaters/${id}/category-results${query}`);
    },
    elements: (id: number, opts?: { elementType?: string; season?: string }) => {
      const qs = new URLSearchParams();
      if (opts?.elementType) qs.set("element_type", opts.elementType);
      if (opts?.season) qs.set("season", opts.season);
      const query = qs.toString() ? `?${qs}` : "";
      return request<Element[]>(`/skaters/${id}/elements${query}`);
    },
    merge: (targetId: number, sourceIds: number[]) =>
      request<{ merged: number; aliases_created: number }>("/skaters/merge", {
        method: "POST",
        body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
      }),
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

  stats: {
    progressionRanking: (params?: {
      season?: string;
      club?: string;
      skating_level?: string;
      age_group?: string;
      gender?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.season) qs.set("season", params.season);
      if (params?.club) qs.set("club", params.club);
      if (params?.skating_level) qs.set("skating_level", params.skating_level);
      if (params?.age_group) qs.set("age_group", params.age_group);
      if (params?.gender) qs.set("gender", params.gender);
      const query = qs.toString() ? `?${qs}` : "";
      return request<ProgressionRankingEntry[]>(`/stats/progression-ranking${query}`);
    },
    benchmarks: (params: {
      skating_level: string;
      age_group: string;
      gender: string;
      season?: string;
    }) => {
      const qs = new URLSearchParams({
        skating_level: params.skating_level,
        age_group: params.age_group,
        gender: params.gender,
      });
      if (params.season) qs.set("season", params.season);
      return request<BenchmarkData>(`/stats/benchmarks?${qs}`);
    },
    elementMastery: (params?: {
      season?: string;
      club?: string;
      skating_level?: string;
      age_group?: string;
      gender?: string;
    }) => {
      const qs = new URLSearchParams();
      if (params?.season) qs.set("season", params.season);
      if (params?.club) qs.set("club", params.club);
      if (params?.skating_level) qs.set("skating_level", params.skating_level);
      if (params?.age_group) qs.set("age_group", params.age_group);
      if (params?.gender) qs.set("gender", params.gender);
      const query = qs.toString() ? `?${qs}` : "";
      return request<ElementMasteryData>(`/stats/element-mastery${query}`);
    },
    competitionClubAnalysis: (params: { competition_id: number; club?: string }) => {
      const qs = new URLSearchParams();
      qs.set("competition_id", String(params.competition_id));
      if (params.club) qs.set("club", params.club);
      const query = qs.toString() ? `?${qs}` : "";
      return request<CompetitionClubAnalysis>(`/stats/competition-club-analysis${query}`);
    },
  },

  training: {
    reviews: {
      list: (params?: { skater_id?: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams();
        if (params?.skater_id !== undefined) qs.set("skater_id", String(params.skater_id));
        if (params?.from) qs.set("from_date", params.from);
        if (params?.to) qs.set("to_date", params.to);
        const query = qs.toString() ? `?${qs}` : "";
        return request<WeeklyReview[]>(`/training/reviews${query}`);
      },
      get: (id: number) => request<WeeklyReview>(`/training/reviews/${id}`),
      create: (data: CreateReviewPayload) =>
        request<WeeklyReview>("/training/reviews", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateReviewPayload) =>
        request<WeeklyReview>(`/training/reviews/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/reviews/${id}`, { method: "DELETE" }),
    },
    incidents: {
      list: (params?: { skater_id?: number; from?: string; to?: string }) => {
        const qs = new URLSearchParams();
        if (params?.skater_id !== undefined) qs.set("skater_id", String(params.skater_id));
        if (params?.from) qs.set("from_date", params.from);
        if (params?.to) qs.set("to_date", params.to);
        const query = qs.toString() ? `?${qs}` : "";
        return request<TrainingIncident[]>(`/training/incidents${query}`);
      },
      get: (id: number) => request<TrainingIncident>(`/training/incidents/${id}`),
      create: (data: CreateIncidentPayload) =>
        request<TrainingIncident>("/training/incidents", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateIncidentPayload) =>
        request<TrainingIncident>(`/training/incidents/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/incidents/${id}`, { method: "DELETE" }),
    },
    challenges: {
      list: (params?: { skater_id?: number; active?: boolean }) => {
        const qs = new URLSearchParams();
        if (params?.skater_id !== undefined) qs.set("skater_id", String(params.skater_id));
        if (params?.active !== undefined) qs.set("active", String(params.active));
        const query = qs.toString() ? `?${qs}` : "";
        return request<TrainingChallenge[]>(`/training/challenges${query}`);
      },
      create: (data: CreateChallengePayload) =>
        request<TrainingChallenge>("/training/challenges", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: number, data: UpdateChallengePayload) =>
        request<TrainingChallenge>(`/training/challenges/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      delete: (id: number) =>
        request<void>(`/training/challenges/${id}`, { method: "DELETE" }),
    },
    timeline: (params: { skater_id: number; from?: string; to?: string }) => {
      const qs = new URLSearchParams({ skater_id: String(params.skater_id) });
      if (params.from) qs.set("from_date", params.from);
      if (params.to) qs.set("to_date", params.to);
      return request<TimelineEntry[]>(`/training/timeline?${qs}`);
    },
  },
};
