import { apiFetch, type Identity } from "./client";
import type {
  Agent,
  AgentListResponse,
  ChatResponseData,
  ChunkingStrategy,
  Conversation,
  CreateAgentRequest,
  CreateKnowledgeBaseRequest,
  CreateModelProfileRequest,
  CreatePromptRequest,
  CreateToolRequest,
  DocumentListResponse,
  DocumentRecord,
  DocumentUploadResponse,
  DocumentVersionListResponse,
  Feedback,
  FeedbackListResponse,
  FeedbackRating,
  HealthResponse,
  KnowledgeBase,
  KnowledgeBaseListResponse,
  Message,
  ModelProfile,
  ModelProfileListResponse,
  Prompt,
  PromptListResponse,
  SearchRequest,
  SearchResponse,
  SubmitFeedbackRequest,
  ToolDefinition,
  ToolListResponse,
  UploadJob,
} from "./types";

const PAGE = { limit: 100, offset: 0 };

// ---------------------------------------------------------------
// Health
// ---------------------------------------------------------------

export const health = {
  get: (identity: Identity) => apiFetch<HealthResponse>("/health", identity),
};

// ---------------------------------------------------------------
// Chat / Conversations
// ---------------------------------------------------------------

export const chat = {
  send: (
    identity: Identity,
    payload: { message: string; conversation_id?: string },
  ) => apiFetch<ChatResponseData>("/chat", identity, { method: "POST", body: payload }),
};

export const conversations = {
  create: (identity: Identity, body: { conversation_id?: string } = {}) =>
    apiFetch<Conversation>("/conversations", identity, { method: "POST", body }),
  get: (identity: Identity, id: string) =>
    apiFetch<Conversation>(`/conversations/${id}`, identity),
  messages: (identity: Identity, id: string) =>
    apiFetch<{ total: number; messages: Message[] }>(
      `/conversations/${id}/messages`,
      identity,
    ),
};

// ---------------------------------------------------------------
// Documents
// ---------------------------------------------------------------

export const documents = {
  list: (identity: Identity) =>
    apiFetch<DocumentListResponse>("/documents", identity, { query: PAGE }),
  get: (identity: Identity, id: string) =>
    apiFetch<DocumentRecord>(`/documents/${id}`, identity),
  versions: (identity: Identity, id: string) =>
    apiFetch<DocumentVersionListResponse>(`/documents/${id}/versions`, identity),
  delete: (identity: Identity, id: string) =>
    apiFetch<null>(`/documents/${id}`, identity, { method: "DELETE" }),
  upload: (identity: Identity, file: File, chunkingStrategy?: ChunkingStrategy) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<DocumentUploadResponse>("/documents", identity, {
      method: "POST",
      formData,
      query: { chunking_strategy: chunkingStrategy },
    });
  },
};

// ---------------------------------------------------------------
// Knowledge Bases
// ---------------------------------------------------------------

export const knowledgeBases = {
  list: (identity: Identity) =>
    apiFetch<KnowledgeBaseListResponse>("/knowledge-bases", identity, { query: PAGE }),
  get: (identity: Identity, id: string) =>
    apiFetch<KnowledgeBase>(`/knowledge-bases/${id}`, identity),
  create: (identity: Identity, body: CreateKnowledgeBaseRequest) =>
    apiFetch<KnowledgeBase>("/knowledge-bases", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Search
// ---------------------------------------------------------------

export const search = {
  run: (identity: Identity, body: SearchRequest) =>
    apiFetch<SearchResponse>("/search", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Agents
// ---------------------------------------------------------------

export const agents = {
  list: (identity: Identity) =>
    apiFetch<AgentListResponse>("/agents", identity, { query: PAGE }),
  get: (identity: Identity, id: string) => apiFetch<Agent>(`/agents/${id}`, identity),
  create: (identity: Identity, body: CreateAgentRequest) =>
    apiFetch<Agent>("/agents", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Model Profiles (global — not tenant-scoped, but we still send the
// header on every call since apiFetch requires an Identity; the
// backend simply ignores tenant scoping for this one resource)
// ---------------------------------------------------------------

export const modelProfiles = {
  list: (identity: Identity) =>
    apiFetch<ModelProfileListResponse>("/model-profiles", identity, { query: PAGE }),
  get: (identity: Identity, id: string) =>
    apiFetch<ModelProfile>(`/model-profiles/${id}`, identity),
  create: (identity: Identity, body: CreateModelProfileRequest) =>
    apiFetch<ModelProfile>("/model-profiles", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------

export const prompts = {
  list: (identity: Identity) =>
    apiFetch<PromptListResponse>("/prompts", identity, { query: PAGE }),
  get: (identity: Identity, id: string) => apiFetch<Prompt>(`/prompts/${id}`, identity),
  create: (identity: Identity, body: CreatePromptRequest) =>
    apiFetch<Prompt>("/prompts", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Tool Definitions
// ---------------------------------------------------------------

export const tools = {
  list: (identity: Identity) =>
    apiFetch<ToolListResponse>("/tool-definitions", identity, { query: PAGE }),
  get: (identity: Identity, id: string) =>
    apiFetch<ToolDefinition>(`/tool-definitions/${id}`, identity),
  create: (identity: Identity, body: CreateToolRequest) =>
    apiFetch<ToolDefinition>("/tool-definitions", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------

export const feedback = {
  list: (identity: Identity, rating?: FeedbackRating) =>
    apiFetch<FeedbackListResponse>("/feedback", identity, {
      query: { ...PAGE, rating },
    }),
  submit: (identity: Identity, body: SubmitFeedbackRequest) =>
    apiFetch<Feedback>("/feedback", identity, { method: "POST", body }),
};

// ---------------------------------------------------------------
// Upload Jobs (no list-all endpoint on the backend — fetch by id only)
// ---------------------------------------------------------------

export const uploadJobs = {
  get: (identity: Identity, id: string) => apiFetch<UploadJob>(`/upload-jobs/${id}`, identity),
};
