/**
 * In-memory mock of the M1 API.
 *
 * Only loaded when `VITE_USE_MOCK=1` (see `api.ts`), which is why importing it
 * dynamically is enough to keep it out of the real request path and out of the
 * critical bundle. It exists so the UI can be developed and reviewed before the
 * backend lands; nothing here is ever used in production.
 */
import type {
  ChatMessage,
  ConversationDetail,
  ConversationSummary,
  EvidenceItem,
  Meta,
  SendMessageBody,
  SettingsSchema,
  StreamHandlers,
  User,
} from "./types";

const USER: User = { id: 1, username: "admin", admin: true };

const EVIDENCE: EvidenceItem[] = [
  {
    id: "ev-1",
    index_id: "1",
    file_id: "file-1",
    file_name: "24级计科1班学年综测汇总表.xlsx",
    page: 1,
    type: "table",
    score: 0.82,
    vector_score: 0.44,
    rerank_score: 0.82,
    llm_score: 0.8,
    text: "综合测评由德育、智育、体育三部分构成，德育占 30%，智育占 50%，体育占 20%。班级前 10% 可参评一等奖学金。",
    file_path: "ktem_app_data/user_data/files/24级计科1班学年综测汇总表.xlsx",
    cited: true,
    spans: [{ start: 0, end: 12, idx: 1 }],
  },
  {
    id: "ev-2",
    index_id: "1",
    file_id: "file-2",
    file_name: "学院奖学金评定办法.pdf",
    page: 4,
    type: "text",
    score: 0.61,
    vector_score: 0.38,
    rerank_score: 0.61,
    llm_score: null,
    text: "申请材料包括成绩单、综测排名证明与个人陈述；逾期提交不予受理。",
    file_path: "ktem_app_data/user_data/files/学院奖学金评定办法.pdf",
    cited: true,
    spans: [],
  },
  {
    id: "ev-3",
    index_id: "1",
    file_id: "file-1",
    file_name: "24级计科1班学年综测汇总表.xlsx",
    page: 2,
    type: "table",
    score: 0.27,
    vector_score: 0.31,
    rerank_score: 0.27,
    llm_score: 0.2,
    text: "王务强：德育 28.5，智育 45.2，体育 18.0，合计 91.7，班级排名 3/41。",
    file_path: "ktem_app_data/user_data/files/24级计科1班学年综测汇总表.xlsx",
    cited: false,
    spans: [],
  },
];

const ANSWER = `综合测评由 **德育、智育、体育** 三部分构成【1】：

| 项目 | 权重 |
| --- | --- |
| 德育 | 30% |
| 智育 | 50% |
| 体育 | 20% |

- 班级前 10% 可以参评一等奖学金【1】
- 申请需要成绩单、综测排名证明与个人陈述【2】

> 逾期提交的材料不予受理【2】

\`\`\`text
合计 = 德育 × 0.3 + 智育 × 0.5 + 体育 × 0.2
\`\`\`

如果需要，我还可以按你的排名估算可参评的等级。`;

const now = Date.now();
const iso = (offsetMs: number) => new Date(now - offsetMs).toISOString();

const DETAILS: Record<string, ConversationDetail> = {
  "demo-1": {
    id: "demo-1",
    name: "综合测评与奖学金",
    is_public: false,
    messages: [
      { role: "user", content: "综合测评怎么计算？一等奖学金需要什么条件？" },
      { role: "assistant", content: ANSWER },
    ],
    evidence_history: [[], EVIDENCE],
    selected: {},
    state: {},
  },
  "demo-2": {
    id: "demo-2",
    name: "差旅报销标准",
    is_public: false,
    messages: [
      { role: "user", content: "出差住宿标准是多少？" },
      { role: "assistant", content: "按照《差旅管理办法》，一线城市每晚不超过 500 元，其他城市 350 元。" },
    ],
    evidence_history: [[], [EVIDENCE[1]]],
    selected: {},
    state: {},
  },
};

const CONVERSATIONS: ConversationSummary[] = [
  {
    id: "demo-1",
    name: "综合测评与奖学金",
    is_public: false,
    date_created: iso(3 * 60 * 60 * 1000),
    date_updated: iso(20 * 60 * 1000),
    preview: "综合测评由德育、智育、体育三部分构成…",
  },
  {
    id: "demo-2",
    name: "差旅报销标准",
    is_public: false,
    date_created: iso(2 * 24 * 60 * 60 * 1000),
    date_updated: iso(26 * 60 * 60 * 1000),
    preview: "一线城市每晚不超过 500 元…",
  },
  {
    id: "demo-3",
    name: "入党积极分子积分细则",
    is_public: true,
    date_created: iso(9 * 24 * 60 * 60 * 1000),
    date_updated: iso(8 * 24 * 60 * 60 * 1000),
    preview: "积分由思想汇报、志愿服务与获奖构成…",
  },
];

let sequence = 100;
const nextId = () => `demo-${++sequence}`;

const META: Meta = {
  app: { name: "citeask", version: "0.12.0", language: "zh" },
  features: {
    user_management: false,
    chat_suggestion: true,
    web_search: true,
    mindmap: true,
    demo_mode: false,
  },
  indices: [{ id: "1", name: "文件集合", private: false, file_count: 7 }],
  reasoning: {
    choices: [
      { value: "simple", label: "简单问答" },
      { value: "complex", label: "复杂问答" },
    ],
    default: "simple",
  },
  models: {
    choices: [
      { value: "deepseek-chat", label: "deepseek-chat" },
      { value: "qwen-plus", label: "qwen-plus" },
    ],
    default: "deepseek-chat",
  },
  languages: {
    choices: [
      { value: "zh", label: "中文" },
      { value: "en", label: "English" },
    ],
    default: "zh",
  },
  citations: {
    choices: [
      { value: "inline", label: "行内" },
      { value: "highlight", label: "高亮" },
      { value: "none", label: "无" },
    ],
    default: "inline",
  },
};

const SCHEMA: SettingsSchema = {
  groups: [
    {
      id: "reasoning",
      label: "推理设置",
      items: [
        { key: "reasoning.use", label: "推理方式", type: "dropdown", value: "simple" },
        { key: "reasoning.lang", label: "语言", type: "dropdown", value: "zh" },
      ],
    },
  ],
};

let settings: Record<string, unknown> = { "reasoning.use": "simple", "reasoning.lang": "zh" };

const delay = (ms = 120) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export const mockApi = {
  async me(): Promise<{ user: User | null }> {
    await delay(60);
    return { user: USER };
  },
  async login(username: string, password: string): Promise<{ user: User }> {
    await delay(200);
    if (!username || !password) throw new Error("invalid credentials");
    return { user: { ...USER, username } };
  },
  async logout(): Promise<void> {
    await delay(60);
  },
  async meta(): Promise<Meta> {
    await delay(80);
    return META;
  },
  async listConversations(): Promise<{ items: ConversationSummary[] }> {
    await delay(100);
    return { items: [...CONVERSATIONS].sort((a, b) => b.date_updated.localeCompare(a.date_updated)) };
  },
  async createConversation(name?: string): Promise<ConversationSummary> {
    await delay(80);
    const id = nextId();
    const summary: ConversationSummary = {
      id,
      name: name || "新对话",
      is_public: false,
      date_created: new Date().toISOString(),
      date_updated: new Date().toISOString(),
      preview: "",
    };
    CONVERSATIONS.unshift(summary);
    DETAILS[id] = {
      id,
      name: summary.name,
      is_public: false,
      messages: [],
      evidence_history: [],
      selected: {},
      state: {},
    };
    return summary;
  },
  async getConversation(id: string): Promise<ConversationDetail> {
    await delay(100);
    const detail = DETAILS[id];
    if (!detail) throw new Error("conversation not found");
    return detail;
  },
  async updateConversation(
    id: string,
    patch: { name?: string; is_public?: boolean },
  ): Promise<ConversationSummary> {
    await delay(60);
    const detail = DETAILS[id];
    const summary = CONVERSATIONS.find((item) => item.id === id);
    if (!detail || !summary) throw new Error("conversation not found");
    if (patch.name !== undefined) {
      detail.name = patch.name;
      summary.name = patch.name;
    }
    if (patch.is_public !== undefined) {
      detail.is_public = patch.is_public;
      summary.is_public = patch.is_public;
    }
    summary.date_updated = new Date().toISOString();
    return summary;
  },
  async deleteConversation(id: string): Promise<void> {
    await delay(60);
    delete DETAILS[id];
    const index = CONVERSATIONS.findIndex((item) => item.id === id);
    if (index >= 0) CONVERSATIONS.splice(index, 1);
  },
  async feedback(_messageIndex: number, _liked: boolean, _value: string): Promise<void> {
    await delay(40);
  },
  async getSettings(): Promise<{ values: Record<string, unknown> }> {
    await delay(60);
    return { values: settings };
  },
  async getSettingsSchema(): Promise<SettingsSchema> {
    await delay(60);
    return SCHEMA;
  },
  async putSettings(values: Record<string, unknown>): Promise<void> {
    await delay(60);
    settings = { ...settings, ...values };
  },
  async listFiles(): Promise<{ id: string; file_name: string }[]> {
    await delay(60);
    return [
      { id: "file-1", file_name: "24级计科1班学年综测汇总表.xlsx" },
      { id: "file-2", file_name: "学院奖学金评定办法.pdf" },
    ];
  },
};

function tokensOf(text: string): string[] {
  const chunks: string[] = [];
  for (let index = 0; index < text.length; index += 6) {
    chunks.push(text.slice(index, index + 6));
  }
  return chunks;
}

/** Token-by-token stream so the UI's streaming states can be exercised. */
export async function mockStreamMessage(
  conversationId: string,
  body: SendMessageBody,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const detail = DETAILS[conversationId];
  if (!detail) throw new Error("conversation not found");

  const messageId = `mock-msg-${Date.now()}`;
  handlers.onStart?.({ message_id: messageId, placeholder: "" });
  await delay(120);
  handlers.onEvidence?.({ items: EVIDENCE });

  const tokens = tokensOf(ANSWER);
  for (const token of tokens) {
    if (signal?.aborted) {
      handlers.onError?.({ message: "aborted" });
      return;
    }
    handlers.onToken?.({ delta: token });
    await delay(12);
  }

  detail.messages.push({ role: "user", content: body.message }, { role: "assistant", content: ANSWER });
  detail.evidence_history.push([], EVIDENCE);
  handlers.onTitle?.({
    name: detail.messages.length > 2 ? detail.name : body.message.slice(0, 18),
  });
  handlers.onSuggestions?.({
    items: ["按我的排名估算可参评等级", "列出申请材料清单", "对比去年的评定办法"],
  });
  handlers.onDone?.({ message_id: messageId });
}

export type MockChatMessage = ChatMessage;
