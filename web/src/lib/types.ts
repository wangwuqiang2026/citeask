/**
 * Wire types of the citeask HTTP API (contract: task M1; backend in `app.py` /
 * the parallel API work). Keep these in sync with the server, not with the UI.
 */

export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
  /** Optional today; the API may add per-message timestamps (date separators). */
  created_at?: string;
}

export type SelectionMode = "all" | "select" | "disabled";

export interface Selection {
  mode: SelectionMode;
  file_ids: string[];
}

export interface EvidenceSpan {
  start: number;
  end: number;
  idx: number;
}

export interface EvidenceItem {
  id: string;
  index_id: string;
  file_id: string;
  file_name: string;
  page?: number | null;
  type?: string | null;
  score?: number | null;
  vector_score?: number | null;
  rerank_score?: number | null;
  llm_score?: number | null;
  text: string;
  file_path?: string | null;
  cited?: boolean;
  spans?: EvidenceSpan[];
}

export interface ConversationSummary {
  id: string;
  name: string;
  is_public: boolean;
  date_created: string;
  date_updated: string;
  preview?: string | null;
}

export interface ConversationDetail {
  id: string;
  name: string;
  is_public: boolean;
  messages: ChatMessage[];
  evidence_history: EvidenceItem[][];
  /** Mind-map markdown per stored Q/A pair (`null` when the turn had none). */
  mindmap_history?: (string | null)[];
  selected: Record<string, Selection>;
  state?: Record<string, unknown> | null;
  /** Present on the backend; used for the day separators of the message list. */
  date_created?: string;
  date_updated?: string;
}

export interface User {
  id: string | number;
  username: string;
  admin: boolean;
}

export interface Choice {
  value: string;
  label: string;
}

export interface ChoiceList {
  choices: Choice[];
  default: string;
}

export interface IndexInfo {
  id: string | number;
  name: string;
  private: boolean;
  file_count: number;
}

export interface FeatureFlags {
  user_management: boolean;
  chat_suggestion: boolean;
  web_search: boolean;
  mindmap: boolean;
  demo_mode: boolean;
}

export interface Meta {
  app: { name: string; version: string; language: string };
  user: User;
  features: FeatureFlags;
  indices: IndexInfo[];
  reasoning: ChoiceList;
  models: ChoiceList;
  languages: ChoiceList;
  citations: ChoiceList;
}

export interface ChatOverrides {
  reasoning?: string | null;
  llm?: string | null;
  language?: string | null;
  citation?: string | null;
  mindmap?: boolean | null;
}

export interface SendMessageBody {
  message: string;
  selection: Record<string, Selection>;
  overrides: ChatOverrides;
  regenerate?: boolean;
}

export interface SettingsItem {
  key: string;
  label: string;
  type: "text" | "number" | "checkbox" | "dropdown" | "radio" | "checkboxgroup";
  choices?: Choice[] | null;
  value?: unknown;
  info?: string | null;
  /** "llm" / "embedding" for the settings the classic page refreshes live. */
  special_type?: string | null;
}

export interface SettingsGroup {
  id: string;
  label: string;
  items: SettingsItem[];
}

export interface SettingsSchema {
  groups: SettingsGroup[];
}

/* --------------------------------------------------------------------- files */

/** One row of `GET /files`. ``file_id`` is the id follow-up calls take. */
export interface FileRow {
  file_id: string;
  name: string;
  type: string;
  size: string | number;
  blocks: number;
  loader: string;
  profile: string;
  date_created: string;
  tokens: number | string;
}

export interface FileListResponse {
  index_id: number | string;
  columns: string[];
  rows: FileRow[];
}

export interface ChunkItem {
  index: number;
  page: number | null;
  type: string;
  text: string;
  html?: string;
}

/** `GET /files/{id}/chunks` — the counts are totals, not the filtered page. */
export interface ChunksResponse {
  file_id: string;
  name: string;
  header: string;
  counts: Record<string, number>;
  chunks: ChunkItem[];
}

export interface FileGroupItem {
  id: string;
  name: string;
  files: string[];
  date_created?: string;
}

export interface GroupListResponse {
  index_id?: number | string;
  items: FileGroupItem[];
}

/** Streaming callbacks of the upload / reindex SSE endpoints. */
export interface UploadHandlers {
  onProgress?: (payload: { line: string }) => void;
  onDone?: (payload: { ids: string[]; errors: string[] }) => void;
  onError?: (payload: { message: string }) => void;
}

/** Streaming callbacks of `POST /conversations/{id}/messages` (SSE). */
export interface StreamHandlers {
  onStart?: (payload: {
    message_id: string;
    placeholder?: string;
    /** Set when the answer has no retrieval scope (backend hint). */
    warning?: string | null;
    regenerate?: boolean;
  }) => void;
  onToken?: (payload: { delta: string }) => void;
  onReset?: () => void;
  onEvidence?: (payload: { items: EvidenceItem[] }) => void;
  onMindmap?: (payload: { markdown: string }) => void;
  onPlot?: (payload: { json: unknown }) => void;
  onTitle?: (payload: { name: string }) => void;
  onSuggestions?: (payload: { items: string[] }) => void;
  onDone?: (payload: { message_id: string; name?: string | null }) => void;
  onError?: (payload: { message: string }) => void;
}

/* --------------------------------------------------------------- resources */

/** One configured model pool entry; the vendor spec itself stays on the server. */
export interface ModelResource {
  name: string;
  vendor: string;
  model: string;
  default: boolean;
}

export interface ResourcesPayload {
  indices: IndexInfo[];
  llms: ModelResource[];
  embeddings: ModelResource[];
  rerankings: ModelResource[];
  mcp: { name: string }[];
}

export interface HelpPayload {
  app: { name: string; version: string; language: string };
  about_md: string;
  usage_md: string;
}

export interface UserPayload {
  username?: string;
  password?: string;
  admin?: boolean;
}
