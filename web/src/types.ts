// Types mirroring the engine's JSON API (engine/curelab/app.py).

export type Stage = 'stable' | 'symptomatic' | 'serious' | 'critical' | 'deceased' | 'cured';
export type Status = 'playing' | 'won' | 'lost';

export interface Vitals {
  hr: number;
  rr: number;
  spo2: number;
  sbp: number;
  dbp: number;
  temp: number;
}

export interface PatientInfo {
  id: string;
  name: string;
  first_name: string;
  age: string;
  sex: string;
  background: string;
  presenting: string;
  companion: string;
  art: string;
  illness: { id: string; name: string; short: string; blurb: string };
  fictional_notice: string;
}

export interface SourceRef {
  vignette: string;
  section: string;
  quote?: string | null;
  site_url: string;
  pinned_url: string;
  ref: string;
  repo?: string;
}

export interface CampaignMeta {
  id: string;
  title: string;
  subtitle: string;
  summary: string;
  order: number;
  datasets: string[];
  locked: boolean;
  unlock_after: string | null;
  won: boolean;
  total_points: number;
  missions: number;
  quizzes: number;
  patient: PatientInfo;
}

export interface Meta {
  pack: {
    id: string;
    name: string;
    tool: string;
    tool_version: string;
    language: string;
    editor_mode: string;
    source_pin: { repo: string; ref: string; path: string; site: string };
    sources?: { repo: string; ref: string; path: string; site: string }[];
  };
  campaigns: CampaignMeta[];
  difficulties: { id: string; label: string; description: string }[];
  rules: {
    hint_cost: number;
    note_min_words: number;
    note_rp: number;
    min_read_seconds: number;
    seconds_per_day: number;
  };
  active: string | null;
  history: Record<string, unknown>[];
  consult: ConsultStatus;
}

/** The optional "consult another doctor" chat (never includes the API key). */
export interface ConsultStatus {
  enabled: boolean;
  provider: string | null;
  label: string;
  model: string;
}

export interface ConsultMessage {
  role: 'user' | 'assistant';
  text: string;
  mission_id: string | null;
  day: number;
}

export interface ConsultData extends ConsultStatus {
  messages: ConsultMessage[];
}

export interface GameEvent {
  id: number;
  kind: 'trait' | 'mission' | 'quiz' | 'rp' | 'stage' | 'won' | 'lost' | string;
  title: string;
  text: string;
  data: Record<string, any>;
}

export interface AcquiredTrait {
  id: string | null;
  name: string;
  day: number;
  gain: number;
  note: string;
  cause: string;
}

export interface TreeTrait {
  id: string;
  name: string;
  category: string;
  tier: number;
  requires: string[];
  acquired: boolean;
  day: number | null;
  note: string | null;
}

export interface MissionSummary {
  id: string;
  title: string;
  points: number;
  status: 'locked' | 'available' | 'completed';
  attempts: number;
  wrong: number;
  hints_bought: number;
  hint_total: number;
}

export interface QuizView {
  id: string;
  after: string;
  status: 'locked' | 'available' | 'completed';
  points: number;
  wrong_choices: number[];
  question?: string;
  choices?: string[];
  answer?: number;
  explanation?: string;
  source?: SourceRef;
}

export interface TimelineEntry {
  day: number;
  kind: string;
  text: string;
}

export interface Stats {
  status: Status;
  days: number;
  active_minutes: number;
  errors: number;
  traits: number;
  events: number;
  missions_completed: number;
  missions_total: number;
  quizzes_correct: number;
  quizzes_total: number;
  hints_bought: number;
  rp_earned: number;
  rp_spent: number;
  pages_read: number;
  research: number;
  final_health: number;
}

export interface GameView {
  started_at: string;
  campaign: string;
  campaign_title: string;
  illness: string;
  difficulty: string;
  status: Status;
  day: number;
  clock: number;
  health: number;
  severity: number;
  decline_per_hour: number;
  stage: Stage;
  vitals: Vitals;
  research: number;
  rp: number;
  errors: number;
  paused: boolean;
  traits: AcquiredTrait[];
  overlays: string[];
  tree: TreeTrait[];
  missions: MissionSummary[];
  quizzes: QuizView[];
  pages_read: string[];
  notes: { qualifying: number; awarded: number; cap: number };
  timeline: TimelineEntry[];
  stats: Stats;
}

export interface Snapshot {
  game: GameView | null;
  patient?: PatientInfo;
  events: GameEvent[];
  cursor: number;
}

export interface MissionDetail {
  id: string;
  title: string;
  points: number;
  status: MissionSummary['status'];
  briefing: string;
  task: string[];
  starter_code: string;
  source: SourceRef;
  hints: string[];
  hint_total: number;
  hint_cost: number;
  notebook_pages: { id: string; title: string }[];
  attempts: number;
  timeout: number;
}

export interface Execution {
  status: 'ok' | 'error' | 'timeout';
  stdout: string;
  stderr: string;
  results: string[];
  images: string[];
  error: { ename: string; evalue: string; traceback: string[] } | null;
  elapsed: number;
}

export interface Outcome {
  graded: boolean;
  passed: boolean;
  message: string;
  execution: Execution;
  debug: string[];
}

export interface NotebookBlock {
  kind: 'text' | 'quote' | 'code';
  text: string;
  source: SourceRef | null;
}

export interface NotebookPage {
  id: string;
  title: string;
  rp: number;
  missions: string[];
  read: boolean;
  blocks: NotebookBlock[];
}

export interface Note {
  id: string;
  title: string;
  body: string;
  created: string;
  updated: string;
  words: number;
  qualifies: boolean;
  /** "consult": a saved consultation; it never earns research points */
  kind: 'note' | 'consult';
}

export interface NotebookData {
  campaign: string;
  pages: NotebookPage[];
  notes: Note[];
}
