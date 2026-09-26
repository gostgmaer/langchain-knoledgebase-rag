import { apiFetch, type Identity } from "./client";
import type {
  Agent,
  AgentListResponse,
  AnalyticsSummary,
  ChatResponseData,
  Conversation,
  CreateAgentRequest,
  CreateFeatureFlagRequest,
  CreateKnowledgeBaseRequest,
  CreateModelProfileRequest,
  CreatePromptRequest,
  CreateToolRequest,
  AuditList,
  ConnectionTest,
  ConnectorTypes,
  CreateSourceRequest,
  ExternalDocumentList,
  IdentityMapping,
  KnowledgeSource,
  KnowledgeSourceList,
  SourceHealth,
  SourcePermissions,
  SourcePreview,
  SourcesSummary,
  SyncRun,
  SyncRunDetail,
  SyncRunList,
  UpdateSourceRequest,
  CredentialStatus,
  DocumentChunkListResponse,
  ObservabilitySummary,
  ReindexResult,
  RetrievalSettings,
  RetrievalSettingsUpdate,
  RetrievalLogDetail,
  RetrievalLogList,
  TopDocument,
  DocumentListResponse,
  DocumentUpdate,
  DocumentUploadOptions,
  DocumentRecord,
  DocumentUploadResponse,
  DocumentVersionListResponse,
  Feedback,
  FeedbackListResponse,
  FeedbackRating,
  FeatureFlag,
  FeatureFlagListResponse,
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
  UsageResponse,
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
  list: (identity: Identity, knowledgeBaseId?: string) =>
    apiFetch<DocumentListResponse>("/documents", identity, {
      query: { ...PAGE, limit: 200, knowledge_base_id: knowledgeBaseId },
    }),
  chunks: (identity: Identity, id: string, limit: number, offset: number) =>
    apiFetch<DocumentChunkListResponse>(`/documents/${id}/chunks`, identity, {
      query: { limit, offset },
    }),
  get: (identity: Identity, id: string) =>
    apiFetch<DocumentRecord>(`/documents/${id}`, identity),
  versions: (identity: Identity, id: string) =>
    apiFetch<DocumentVersionListResponse>(`/documents/${id}/versions`, identity),
  delete: (identity: Identity, id: string) =>
    apiFetch<null>(`/documents/${id}`, identity, { method: "DELETE" }),
  upload: (identity: Identity, file: File, options: DocumentUploadOptions = {}) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<DocumentUploadResponse>("/documents", identity, {
      method: "POST",
      formData,
      query: {
        chunking_strategy: options.chunkingStrategy,
        document_type: options.documentType || undefined,
        category: options.category || undefined,
        tags: options.tags || undefined,
        visibility: options.visibility,
      },
    });
  },
  reindex: (identity: Identity, id: string) =>
    apiFetch<ReindexResult>(`/documents/${id}/reindex`, identity, { method: "POST" }),
  reindexOutdated: (identity: Identity) =>
    apiFetch<ReindexResult>("/documents/reindex-outdated", identity, { method: "POST" }),
  update: (identity: Identity, id: string, body: DocumentUpdate) =>
    apiFetch<DocumentRecord>(`/documents/${id}`, identity, { method: "PATCH", body }),
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
  // Only an EMPTY knowledge base can be deleted (409 otherwise).
  delete: (identity: Identity, id: string) =>
    apiFetch<null>(`/knowledge-bases/${id}`, identity, { method: "DELETE" }),
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

// ---------------------------------------------------------------
// Usage (Token Usage + Cost Tracking, docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export const usage = {
  get: (identity: Identity, days = 30) =>
    apiFetch<UsageResponse>("/usage", identity, { query: { days } }),
};

// ---------------------------------------------------------------
// Analytics (docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export const analytics = {
  summary: (identity: Identity, days = 30) =>
    apiFetch<AnalyticsSummary>("/analytics/summary", identity, { query: { days } }),
};

// ---------------------------------------------------------------
// Feature Flags (docs/mvpRAG.md v1.1) — admin-only (require_role
// "admin", gated behind the dynamic enable_rbac flag itself)
// ---------------------------------------------------------------

export const featureFlags = {
  list: (identity: Identity) =>
    apiFetch<FeatureFlagListResponse>("/feature-flags", identity, { query: PAGE }),
  create: (identity: Identity, body: CreateFeatureFlagRequest) =>
    apiFetch<FeatureFlag>("/feature-flags", identity, { method: "POST", body }),
  toggle: (identity: Identity, id: string, enabled: boolean) =>
    apiFetch<FeatureFlag>(`/feature-flags/${id}/toggle`, identity, {
      method: "PATCH",
      body: { enabled },
    }),
  delete: (identity: Identity, id: string) =>
    apiFetch<null>(`/feature-flags/${id}`, identity, { method: "DELETE" }),
};

// ---------------------------------------------------------------
// Retrieval logs & observability — admin-only
// ---------------------------------------------------------------

export const retrievalLogs = {
  list: (identity: Identity, limit: number, offset: number) =>
    apiFetch<RetrievalLogList>("/retrieval-logs", identity, { query: { limit, offset } }),
  get: (identity: Identity, id: string) =>
    apiFetch<RetrievalLogDetail>(`/retrieval-logs/${id}`, identity),
};

export const observability = {
  summary: (identity: Identity, days: number) =>
    apiFetch<ObservabilitySummary>("/observability/summary", identity, { query: { days } }),
  topDocuments: (identity: Identity, days: number) =>
    apiFetch<TopDocument[]>("/observability/top-documents", identity, { query: { days, limit: 10 } }),
  audit: (identity: Identity, limit: number, offset: number) =>
    apiFetch<AuditList>("/observability/audit", identity, { query: { limit, offset } }),
};

export const retrievalSettings = {
  get: (identity: Identity) => apiFetch<RetrievalSettings>("/retrieval-settings", identity),
  save: (identity: Identity, body: RetrievalSettingsUpdate) =>
    apiFetch<RetrievalSettings>("/retrieval-settings", identity, { method: "PUT", body }),
};

// ---------------------------------------------------------------
// Knowledge sources — admin-only
// ---------------------------------------------------------------

const KS = "/knowledge-sources";

export const knowledgeSources = {
  types: (identity: Identity) => apiFetch<ConnectorTypes>(`${KS}/types`, identity),
  summary: (identity: Identity) => apiFetch<SourcesSummary>(`${KS}/summary`, identity),
  list: (identity: Identity) => apiFetch<KnowledgeSourceList>(KS, identity),
  get: (identity: Identity, id: string) => apiFetch<KnowledgeSource>(`${KS}/${id}`, identity),
  create: (identity: Identity, body: CreateSourceRequest) =>
    apiFetch<KnowledgeSource>(KS, identity, { method: "POST", body }),
  update: (identity: Identity, id: string, body: UpdateSourceRequest) =>
    apiFetch<KnowledgeSource>(`${KS}/${id}`, identity, { method: "PATCH", body }),
  remove: (identity: Identity, id: string) => apiFetch<null>(`${KS}/${id}`, identity, { method: "DELETE" }),
  testUnsaved: (identity: Identity, body: { type: string; configuration: Record<string, unknown>; credentials?: Record<string, unknown> | null }) =>
    apiFetch<ConnectionTest>(`${KS}/test`, identity, { method: "POST", body }),
  testSaved: (identity: Identity, id: string) =>
    apiFetch<ConnectionTest>(`${KS}/${id}/test-connection`, identity, { method: "POST" }),
  preview: (identity: Identity, id: string, limit = 20) =>
    apiFetch<SourcePreview>(`${KS}/${id}/preview`, identity, { method: "POST", query: { limit } }),
  setCredentials: (identity: Identity, id: string, credentials: Record<string, unknown>) =>
    apiFetch<CredentialStatus>(`${KS}/${id}/credentials`, identity, { method: "PUT", body: { credentials } }),
  revokeCredentials: (identity: Identity, id: string) =>
    apiFetch<CredentialStatus>(`${KS}/${id}/credentials`, identity, { method: "DELETE" }),
  sync: (identity: Identity, id: string, activate = false) =>
    apiFetch<SyncRun>(`${KS}/${id}/sync`, identity, { method: "POST", body: { activate } }),
  cancel: (identity: Identity, id: string) => apiFetch<null>(`${KS}/${id}/sync/cancel`, identity, { method: "POST" }),
  pause: (identity: Identity, id: string) => apiFetch<KnowledgeSource>(`${KS}/${id}/pause`, identity, { method: "POST" }),
  resume: (identity: Identity, id: string) => apiFetch<KnowledgeSource>(`${KS}/${id}/resume`, identity, { method: "POST" }),
  runs: (identity: Identity, id: string, limit: number, offset: number) =>
    apiFetch<SyncRunList>(`${KS}/${id}/runs`, identity, { query: { limit, offset } }),
  run: (identity: Identity, id: string, runId: string) =>
    apiFetch<SyncRunDetail>(`${KS}/${id}/runs/${runId}`, identity),
  documents: (identity: Identity, id: string, limit: number, offset: number, status?: string, q?: string) =>
    apiFetch<ExternalDocumentList>(`${KS}/${id}/documents`, identity, { query: { limit, offset, status: status || undefined, q: q || undefined } }),
  retryDocument: (identity: Identity, id: string, recordId: string) =>
    apiFetch<null>(`${KS}/${id}/documents/${recordId}/retry`, identity, { method: "POST" }),
  health: (identity: Identity, id: string) => apiFetch<SourceHealth>(`${KS}/${id}/health`, identity),
  permissions: (identity: Identity, id: string) => apiFetch<SourcePermissions>(`${KS}/${id}/permissions`, identity),
  mappings: (identity: Identity, provider?: string) =>
    apiFetch<{ mappings: IdentityMapping[] }>(`${KS}/identity-mappings`, identity, { query: { provider } }),
  saveMapping: (identity: Identity, body: IdentityMapping) =>
    apiFetch<IdentityMapping>(`${KS}/identity-mappings`, identity, { method: "PUT", body }),
  deleteMapping: (identity: Identity, id: string) =>
    apiFetch<null>(`${KS}/identity-mappings/${id}`, identity, { method: "DELETE" }),
};
