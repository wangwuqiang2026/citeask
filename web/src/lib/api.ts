import { parseFileRows, parseUploadEvent } from "./files";
import { parseJsonData, readSse } from "./sse";
import type {
  ChatMessage,
  ChatOverrides,
  ChunksResponse,
  ConversationDetail,
  ConversationSummary,
  EmbeddingJob,
  EmbeddingSwitchResult,
  EvidenceItem,
  FileGroupItem,
  FileListResponse,
  GroupListResponse,
  HelpPayload,
  Meta,
  ResourcesPayload,
  SendMessageBody,
  SettingsSchema,
  StreamHandlers,
  UploadHandlers,
  User,
  UserPayload,
  VendorCatalog,
  VendorEntry,
  VendorPayload,
} from "./types";

/** Explicit opt-in mock for local UI work without a running backend. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "1";

const JSON_HEADERS: HeadersInit = {
  "Content-Type": "application/json",
  Accept: "application/json",
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** `/auth/login` answering 401 is a wrong password, not an expired session. */
function isAuthPath(path: string): boolean {
  return path.startsWith("/api/v1/auth/");
}

function messageFromDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const value = record.detail ?? record.message ?? record.error;
    if (typeof value === "string") return value;
    if (Array.isArray(value)) {
      return value
        .map((item) => (typeof item === "string" ? item : JSON.stringify(item)))
        .join("; ");
    }
  }
  return null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: "include", ...init });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      /* the body is not JSON (proxy error page, empty 500 …) */
    }
    const message =
      messageFromDetail(detail) || response.statusText || `HTTP ${response.status}`;
    if (response.status === 401 && !isAuthPath(path)) {
      window.dispatchEvent(new Event("citeask:unauthorized"));
    }
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

function handleChatEvent(event: string, data: string, handlers: StreamHandlers): void {
  switch (event) {
    case "start": {
      const payload = parseJsonData<{
        message_id: string;
        placeholder?: string;
        warning?: string | null;
        regenerate?: boolean;
      }>(data);
      if (payload) handlers.onStart?.(payload);
      break;
    }
    case "token": {
      const payload = parseJsonData<{ delta: string }>(data);
      if (payload) handlers.onToken?.(payload);
      break;
    }
    case "reset":
      handlers.onReset?.();
      break;
    case "evidence": {
      const payload = parseJsonData<{ items: EvidenceItem[] }>(data);
      if (payload) handlers.onEvidence?.(payload);
      break;
    }
    case "mindmap": {
      const payload = parseJsonData<{ markdown: string }>(data);
      if (payload) handlers.onMindmap?.(payload);
      break;
    }
    case "plot": {
      const payload = parseJsonData<{ json: unknown }>(data);
      if (payload) handlers.onPlot?.(payload);
      break;
    }
    case "title": {
      const payload = parseJsonData<{ name: string }>(data);
      if (payload) handlers.onTitle?.(payload);
      break;
    }
    case "suggestions": {
      const payload = parseJsonData<{ items: string[] }>(data);
      if (payload) handlers.onSuggestions?.(payload);
      break;
    }
    case "done": {
      const payload = parseJsonData<{ message_id: string; name?: string | null }>(data);
      if (payload) handlers.onDone?.(payload);
      break;
    }
    case "error": {
      const payload = parseJsonData<{ message: string }>(data);
      handlers.onError?.({ message: payload?.message ?? "unknown error" });
      break;
    }
    default:
      // Unknown events are ignored on purpose: the backend may add more.
      break;
  }
}

/** `POST /conversations/{id}/messages` streaming over `fetch` + ReadableStream. */
async function streamMessage(
  conversationId: string,
  body: SendMessageBody,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (USE_MOCK) {
    const { mockStreamMessage } = await import("./mock");
    return mockStreamMessage(conversationId, body, handlers, signal);
  }

  const response = await fetch(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    },
  );

  if (!response.ok || !response.body) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      /* no JSON body */
    }
    if (response.status === 401) {
      window.dispatchEvent(new Event("citeask:unauthorized"));
    }
    throw new ApiError(
      messageFromDetail(detail) ?? `HTTP ${response.status}`,
      response.status,
      detail,
    );
  }

  await readSse(response, (event) =>
    handleChatEvent(event.event, event.data, handlers),
  );
}

/** Shared error handling for the two streaming file endpoints. */
async function streamIndexing(
  path: string,
  body: FormData | undefined,
  handlers: UploadHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "text/event-stream" },
    body,
    signal,
  });

  if (!response.ok || !response.body) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      /* no JSON body */
    }
    if (response.status === 401) {
      window.dispatchEvent(new Event("citeask:unauthorized"));
    }
    throw new ApiError(
      messageFromDetail(detail) ?? `HTTP ${response.status}`,
      response.status,
      detail,
    );
  }

  await readSse(response, (event) => {
    const parsed = parseUploadEvent(event);
    if (!parsed) return;
    if (parsed.type === "progress") handlers.onProgress?.({ line: parsed.line });
    else if (parsed.type === "done") {
      handlers.onDone?.({ ids: parsed.ids, errors: parsed.errors });
    } else {
      handlers.onError?.({ message: parsed.message });
    }
  });
}

export interface FileOption {
  id: string;
  file_name: string;
  index_id?: string;
}

export const api = {
  async me(): Promise<{ user: User | null }> {
    if (USE_MOCK) return (await import("./mock")).mockApi.me();
    return request<{ user: User | null }>("/api/v1/auth/me");
  },

  async login(username: string, password: string): Promise<{ user: User }> {
    if (USE_MOCK) return (await import("./mock")).mockApi.login(username, password);
    return request<{ user: User }>("/api/v1/auth/login", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ username, password }),
    });
  },

  async logout(): Promise<void> {
    if (USE_MOCK) return (await import("./mock")).mockApi.logout();
    await request<void>("/api/v1/auth/logout", { method: "POST" });
  },

  /** Change the signed-in user's own password. */
  async changePassword(
    current_password: string,
    new_password: string,
  ): Promise<void> {
    await request<void>("/api/v1/auth/password", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ current_password, new_password }),
    });
  },

  async meta(): Promise<Meta> {
    if (USE_MOCK) return (await import("./mock")).mockApi.meta();
    return request<Meta>("/api/v1/meta");
  },

  /** Configured indices and model pools (read-only, for `/resources`). */
  async getResources(): Promise<ResourcesPayload> {
    return request<ResourcesPayload>("/api/v1/resources");
  },

  /**
   * Store the LLM this account's chat runs on (`""` = follow the pool default).
   * Persisted in the account, so `/meta` and every device agree (§5.33).
   */
  async setCurrentLlm(name: string): Promise<{ name: string }> {
    if (USE_MOCK) return (await import("./mock")).mockApi.setCurrentLlm(name);
    return request<{ name: string }>("/api/v1/resources/llm", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({ name }),
    });
  },

  /**
   * Switch the embedding model. The server rebuilds the whole index in the
   * background; poll {@link getEmbeddingJob} for progress (§5.36).
   */
  async setEmbedding(name: string): Promise<EmbeddingSwitchResult> {
    return request<EmbeddingSwitchResult>("/api/v1/resources/embedding", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({ name }),
    });
  },

  async getEmbeddingJob(): Promise<{ job: EmbeddingJob }> {
    return request<{ job: EmbeddingJob }>("/api/v1/resources/embedding/job");
  },

  /** Switch the reranker; effective immediately, no rebuild needed (§5.36). */
  async setCurrentReranking(name: string): Promise<{ name: string }> {
    return request<{ name: string }>("/api/v1/resources/reranking", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({ name }),
    });
  },

  /** Bundled About / user-guide documents (read-only, for `/help`). */
  async getHelp(): Promise<HelpPayload> {
    return request<HelpPayload>("/api/v1/help");
  },

  /* ----------------------------------------------------------------- users */

  async listUsers(): Promise<{ items: User[] }> {
    return request<{ items: User[] }>("/api/v1/users");
  },

  async createUser(body: {
    username: string;
    password: string;
    admin?: boolean;
  }): Promise<User> {
    return request<User>("/api/v1/users", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  async updateUser(id: string | number, body: UserPayload): Promise<User> {
    return request<User>(`/api/v1/users/${encodeURIComponent(String(id))}`, {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  async deleteUser(id: string | number): Promise<void> {
    await request<void>(`/api/v1/users/${encodeURIComponent(String(id))}`, {
      method: "DELETE",
    });
  },

  /* --------------------------------------------------------------- vendors */

  /** Vendor catalog with the parameter metadata used to build the forms. */
  async getVendorCatalog(): Promise<VendorCatalog> {
    return request<VendorCatalog>("/api/v1/vendors");
  },

  async listVendors(kind: string): Promise<{ items: VendorEntry[] }> {
    return request<{ items: VendorEntry[] }>(`/api/v1/vendors/${kind}`);
  },

  async getVendor(kind: string, name: string): Promise<VendorEntry> {
    return request<VendorEntry>(
      `/api/v1/vendors/${kind}/${encodeURIComponent(name)}`,
    );
  },

  async createVendor(kind: string, body: VendorPayload): Promise<VendorEntry> {
    return request<VendorEntry>(`/api/v1/vendors/${kind}`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  async updateVendor(
    kind: string,
    name: string,
    body: VendorPayload,
  ): Promise<VendorEntry> {
    return request<VendorEntry>(
      `/api/v1/vendors/${kind}/${encodeURIComponent(name)}`,
      {
        method: "PATCH",
        headers: JSON_HEADERS,
        body: JSON.stringify(body),
      },
    );
  },

  async deleteVendor(kind: string, name: string): Promise<void> {
    await request<void>(
      `/api/v1/vendors/${kind}/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    );
  },

  /** Builds the chat client without sending a request (no tokens spent). */
  async testVendor(
    vendor: string,
    params: Record<string, unknown>,
  ): Promise<{ ok: boolean; message: string }> {
    return request<{ ok: boolean; message: string }>("/api/v1/vendors/llms/test", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ vendor, params }),
    });
  },

  async listConversations(): Promise<{ items: ConversationSummary[] }> {
    if (USE_MOCK) return (await import("./mock")).mockApi.listConversations();
    return request<{ items: ConversationSummary[] }>("/api/v1/conversations");
  },

  async createConversation(name?: string): Promise<ConversationSummary> {
    if (USE_MOCK) return (await import("./mock")).mockApi.createConversation(name);
    return request<ConversationSummary>("/api/v1/conversations", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(name ? { name } : {}),
    });
  },

  async getConversation(id: string): Promise<ConversationDetail> {
    if (USE_MOCK) return (await import("./mock")).mockApi.getConversation(id);
    return request<ConversationDetail>(
      `/api/v1/conversations/${encodeURIComponent(id)}`,
    );
  },

  async updateConversation(
    id: string,
    patch: { name?: string; is_public?: boolean },
  ): Promise<ConversationSummary> {
    if (USE_MOCK) return (await import("./mock")).mockApi.updateConversation(id, patch);
    return request<ConversationSummary>(
      `/api/v1/conversations/${encodeURIComponent(id)}`,
      { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(patch) },
    );
  },

  async deleteConversation(id: string): Promise<void> {
    if (USE_MOCK) return (await import("./mock")).mockApi.deleteConversation(id);
    await request<void>(`/api/v1/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async feedback(
    id: string,
    messageIndex: number,
    liked: boolean,
    value: string,
  ): Promise<void> {
    if (USE_MOCK) {
      return (await import("./mock")).mockApi.feedback(messageIndex, liked, value);
    }
    await request<void>(
      `/api/v1/conversations/${encodeURIComponent(id)}/feedback`,
      {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ message_index: messageIndex, liked, value }),
      },
    );
  },

  async getSettings(): Promise<{ values: Record<string, unknown> }> {
    if (USE_MOCK) return (await import("./mock")).mockApi.getSettings();
    return request<{ values: Record<string, unknown> }>("/api/v1/settings");
  },

  async getSettingsSchema(): Promise<SettingsSchema> {
    if (USE_MOCK) return (await import("./mock")).mockApi.getSettingsSchema();
    return request<SettingsSchema>("/api/v1/settings/schema");
  },

  async putSettings(
    values: Record<string, unknown>,
  ): Promise<{ values: Record<string, unknown> }> {
    if (USE_MOCK) {
      await (await import("./mock")).mockApi.putSettings(values);
      const stored = (await (await import("./mock")).mockApi.getSettings()).values;
      return { values: stored };
    }
    return request<{ values: Record<string, unknown> }>("/api/v1/settings", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({ values }),
    });
  },

  /* ------------------------------------------------------------------ files */

  /** `GET /files` — one index's file list (id/name/type/size/blocks/loader/…). */
  async listFiles(
    indexId?: string | number,
    query = "",
  ): Promise<FileListResponse> {
    if (USE_MOCK) {
      const items = await (await import("./mock")).mockApi.listFiles();
      return {
        index_id: indexId ?? "mock",
        columns: [
          "file_id",
          "name",
          "type",
          "size",
          "blocks",
          "loader",
          "profile",
          "date_created",
          "tokens",
        ],
        rows: items.map((item) => ({
          file_id: item.id,
          name: item.file_name,
          type: item.file_name.includes(".")
            ? item.file_name.slice(item.file_name.lastIndexOf(".") + 1)
            : "other",
          size: "-",
          blocks: 0,
          loader: "mock",
          profile: "",
          date_created: "",
          tokens: "-",
        })),
      };
    }
    const params = new URLSearchParams();
    if (indexId !== undefined && indexId !== null && indexId !== "") {
      params.set("index_id", String(indexId));
    }
    if (query.trim()) params.set("query", query.trim());
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return request<FileListResponse>(`/api/v1/files${suffix}`);
  },

  /** `POST /files/upload` — multipart upload, indexed while the SSE stream lasts. */
  async uploadFiles(
    form: FormData,
    handlers: UploadHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    if (USE_MOCK) {
      handlers.onProgress?.({ line: "✅ | mock.txt" });
      handlers.onDone?.({ ids: ["mock-file"], errors: [] });
      return;
    }
    await streamIndexing("/api/v1/files/upload", form, handlers, signal);
  },

  /** `POST /files/{id}/reindex` — same SSE frames as an upload. */
  async reindexFile(
    fileId: string,
    handlers: UploadHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    if (USE_MOCK) {
      handlers.onDone?.({ ids: [fileId], errors: [] });
      return;
    }
    await streamIndexing(
      `/api/v1/files/${encodeURIComponent(fileId)}/reindex`,
      undefined,
      handlers,
      signal,
    );
  },

  async deleteFile(
    fileId: string,
  ): Promise<{ ok: boolean; file_id: string; name: string }> {
    return request<{ ok: boolean; file_id: string; name: string }>(
      `/api/v1/files/${encodeURIComponent(fileId)}`,
      { method: "DELETE" },
    );
  },

  /** `GET /files/{id}/chunks` — header, per-type counts and the chunk texts. */
  async fileChunks(fileId: string, type = "all"): Promise<ChunksResponse> {
    if (USE_MOCK) {
      return {
        file_id: fileId,
        name: "mock.txt",
        header: "0 chunks",
        counts: { text: 0, table: 0, image: 0, thumbnail: 0 },
        chunks: [],
      };
    }
    const suffix = type && type !== "all" ? `?type=${encodeURIComponent(type)}` : "";
    return request<ChunksResponse>(
      `/api/v1/files/${encodeURIComponent(fileId)}/chunks${suffix}`,
    );
  },

  /** Same-origin download URL; the browser sends the auth cookie with it. */
  downloadFileUrl(fileId: string): string {
    return `/api/v1/files/${encodeURIComponent(fileId)}/download`;
  },

  /* ----------------------------------------------------------------- groups */

  async listGroups(indexId?: string | number): Promise<GroupListResponse> {
    if (USE_MOCK) return { index_id: indexId ?? "mock", items: [] };
    const params = new URLSearchParams();
    if (indexId !== undefined && indexId !== null && indexId !== "") {
      params.set("index_id", String(indexId));
    }
    const suffix = params.size > 0 ? `?${params.toString()}` : "";
    return request<GroupListResponse>(`/api/v1/groups${suffix}`);
  },

  async createGroup(
    name: string,
    files: string[],
  ): Promise<{ index_id?: number | string; item: FileGroupItem }> {
    return request<{ index_id?: number | string; item: FileGroupItem }>(
      "/api/v1/groups",
      { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ name, files }) },
    );
  },

  async updateGroup(
    groupId: string,
    patch: { name?: string; files?: string[] },
  ): Promise<{ index_id?: number | string; item: FileGroupItem }> {
    return request<{ index_id?: number | string; item: FileGroupItem }>(
      `/api/v1/groups/${encodeURIComponent(groupId)}`,
      { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(patch) },
    );
  },

  async deleteGroup(groupId: string): Promise<{ ok: boolean; id: string }> {
    return request<{ ok: boolean; id: string }>(
      `/api/v1/groups/${encodeURIComponent(groupId)}`,
      { method: "DELETE" },
    );
  },

  /**
   * Best effort: `GET /files` answers `{index_id, columns, rows}`; older builds
   * used a bare list or `{items}`. `null` means "endpoint not available yet"
   * (404/405/501), which the composer renders as a link to the classic UI.
   */
  async tryListFiles(indexId?: string | number): Promise<FileOption[] | null> {
    if (USE_MOCK) return (await import("./mock")).mockApi.listFiles();
    const query =
      indexId !== undefined && indexId !== ""
        ? `?index_id=${encodeURIComponent(String(indexId))}`
        : "";
    try {
      const data = await request<unknown>(`/api/v1/files${query}`);
      return parseFileRows(data);
    } catch (error) {
      if (error instanceof ApiError && [404, 405, 501].includes(error.status)) {
        return null;
      }
      throw error;
    }
  },

  streamMessage,

  /** Only used by the login page for the legacy UI's autologin storage. */
  rememberLegacyCredentials(username: string, password: string): void {
    try {
      window.localStorage.setItem("username", username);
      window.localStorage.setItem("password", password);
    } catch {
      /* private mode: the classic UI will just ask again */
    }
  },
};

export type { ChatMessage, ChatOverrides };
