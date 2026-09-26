// Types mirroring packages/api/schemas/*.py exactly. Kept as one file
// since every resource here is small and they reference each other
// (e.g. DocumentVersion -> Document, Feedback -> Message).

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface ApiErrorResponse {
  success: false;
  error: string;
  message: string;
  details: Record<string, unknown>;
  timestamp: string;
}

// The type parameter documents which item type a list response carries (the concrete
// response interfaces below add the item array); it is intentionally unused here.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------
// Conversations / Chat
// ---------------------------------------------------------------

export type MessageRole = "USER" | "ASSISTANT" | "SYSTEM" | "TOOL";

export interface Conversation {
  id: string;
  tenant_id: string;
  user_id: string;
  agent_id: string;
  session_id: string;
  title: string | null;
  status: string;
  total_messages: number;
  total_tokens: number;
  total_cost: number;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  sources?: MessageSource[];
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  label?: string | null;
  document_name?: string | null;
  page_number?: number | null;
  section?: string | null;
}

/** Customer-visible source of an answer: which document, and where in it. */
export interface MessageSource {
  label: string;
  document_name: string | null;
  page_number: number | null;
  section: string | null;
  source_type?: string | null;
  source_name?: string | null;
  /** Original page/file URL for external sources. */
  url?: string | null;
  updated_at?: string | null;
}

export interface ChatResponseData {
  conversation_id: string;
  response: string;
  model: string;
  usage: Record<string, number>;
  citations: Citation[];
}

// ---------------------------------------------------------------
// Documents
// ---------------------------------------------------------------

// Matches packages/knowledge/schemas.py's ChunkingStrategy literal.
export type ChunkingStrategy = "auto" | "recursive" | "markdown" | "semantic";

export interface DocumentUploadResponse {
  status: string;
  document_name: string;
  file_id: string;
  upload_job_id: string;
}

export interface DocumentRecord {
  id: string;
  knowledge_base_id: string;
  title: string;
  description: string | null;
  file_id: string;
  file_name: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  status: string;
  is_current: boolean;
  created_at: string;
  updated_at: string;
  chunk_count: number;
  /** Extra retrieval representations (summary/graph); not chunks of the text. */
  representation_count: number;
  /** null for documents ingested before chunking was recorded. */
  chunking: ChunkingInfo | null;
  document_metadata: Record<string, unknown>;
  // Provenance / processing record. null = not recorded (ingested before these existed).
  content_hash: string | null;
  uploaded_by: string | null;
  processing_version: string | null;
  parser_name: string | null;
  chunking_version: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  processing_stage: string | null;
  error_reason: string | null;
  processed_at: string | null;
  embedding_is_stale: boolean | null;
  /** "tenant" = every member may retrieve it; "restricted" = administrators only. */
  visibility: "tenant" | "restricted";
  source_type: string | null;
  source_id: string | null;
  source_name: string | null;
  external_id: string | null;
  canonical_url: string | null;
  external_version: string | null;
  external_updated_at: string | null;
  last_synced_at: string | null;
  sync_id: string | null;
  freshness_seconds: number | null;
  /** For restricted documents: members with one of these roles, or listed by user id, may also retrieve it. */
  allowed_roles: string[] | null;
  allowed_users: string[] | null;
  document_type: string | null;
  category: string | null;
  tags: string[] | null;
}

export interface DocumentUploadOptions {
  chunkingStrategy?: ChunkingStrategy;
  documentType?: string;
  category?: string;
  tags?: string;
  visibility?: "tenant" | "restricted";
}

export interface DocumentUpdate {
  visibility?: "tenant" | "restricted";
  allowed_roles?: string[] | null;
  allowed_users?: string[] | null;
  document_type?: string | null;
  category?: string | null;
  tags?: string[] | null;
}

export interface ChunkingInfo {
  requested: string | null;
  strategy: string | null;
  splitter: string | null;
  chunk_size: number | null;
  chunk_overlap: number | null;
  chunk_count: number | null;
  total_tokens: number | null;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  kind: string;
  page_number: number | null;
  section: string | null;
  content: string;
  token_count: number;
  character_count: number;
  start_offset: number | null;
  end_offset: number | null;
  metadata: Record<string, unknown>;
  content_hash: string | null;
  chunking_strategy: string | null;
  chunking_version: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  pipeline_version: string | null;
  indexed_at: string | null;
}

export interface DocumentChunkListResponse {
  document_id: string;
  total: number;
  limit: number;
  offset: number;
  chunking: ChunkingInfo | null;
  chunks: DocumentChunk[];
}

export interface DocumentListResponse extends Page<DocumentRecord> {
  documents: DocumentRecord[];
}

export interface DocumentVersionEntry {
  document_id: string;
  version_number: number;
  superseded_at: string | null;
  is_current: boolean;
}

export interface DocumentVersionListResponse {
  root_document_id: string;
  versions: DocumentVersionEntry[];
}

// ---------------------------------------------------------------
// Knowledge Bases
// ---------------------------------------------------------------

export interface KnowledgeBase {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  similarity_metric: string;
  search_type: string;
  max_results: number;
  is_public: boolean;
  document_count: number;
}

export interface KnowledgeBaseListResponse extends Page<KnowledgeBase> {
  knowledge_bases: KnowledgeBase[];
}

export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string | null;
  is_public?: boolean;
}

// ---------------------------------------------------------------
// Search
// ---------------------------------------------------------------

export interface SearchResult {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  content: string;
  score: number;
}

// Matches packages/api/schemas/search.py's SearchRequestSchema, which
// forbids extra fields — "limit", not "top_k" (a genuinely different
// concept from ModelProfile's LLM-sampling top_k below).
export interface SearchRequest {
  query: string;
  document_id?: string | null;
  limit?: number;
  document_types?: string[];
  categories?: string[];
  tags?: string[];
}

export interface SearchResponse {
  results: SearchResult[];
}

// ---------------------------------------------------------------
// Agents
// ---------------------------------------------------------------

export interface Agent {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  system_prompt: string;
  llm_provider: string;
  llm_model: string;
  model_profile_id: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  is_active: boolean;
  status: string;
}

export interface AgentListResponse extends Page<Agent> {
  agents: Agent[];
}

export interface CreateAgentRequest {
  name: string;
  description?: string | null;
  system_prompt: string;
  llm_provider: string;
  llm_model: string;
  model_profile_id: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
}

// ---------------------------------------------------------------
// Model Profiles (global, not tenant-scoped)
// ---------------------------------------------------------------

export interface ModelProfile {
  id: string;
  name: string;
  provider: string;
  model: string;
  description: string | null;
  temperature: number;
  top_p: number;
  top_k: number | null;
  max_tokens: number;
  context_window: number;
  embedding_dimensions: number;
  supports_streaming: boolean;
  supports_tools: boolean;
  supports_reasoning: boolean;
  supports_images: boolean;
  supports_embeddings: boolean;
  is_default: boolean;
  status: string;
}

export interface ModelProfileListResponse extends Page<ModelProfile> {
  model_profiles: ModelProfile[];
}

export interface CreateModelProfileRequest {
  name: string;
  provider: string;
  model: string;
  description?: string | null;
  temperature?: number;
  top_p?: number;
  top_k?: number | null;
  max_tokens?: number;
  context_window: number;
  embedding_dimensions?: number;
  supports_streaming?: boolean;
  supports_tools?: boolean;
  supports_reasoning?: boolean;
  supports_images?: boolean;
  supports_embeddings?: boolean;
  is_default?: boolean;
}

// ---------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------

export const PROMPT_CATEGORIES = [
  "SYSTEM",
  "RAG",
  "AGENT",
  "TOOL",
  "SUMMARIZATION",
  "CLASSIFICATION",
  "EXTRACTION",
  "CUSTOM",
] as const;
export type PromptCategory = (typeof PROMPT_CATEGORIES)[number];

export interface Prompt {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  category: string;
  is_active: boolean;
}

export interface PromptListResponse extends Page<Prompt> {
  prompts: Prompt[];
}

export interface CreatePromptRequest {
  name: string;
  description?: string | null;
  category: PromptCategory;
}

// ---------------------------------------------------------------
// Tool Definitions
// ---------------------------------------------------------------

export const TOOL_CATEGORIES = [
  "SEARCH",
  "DATABASE",
  "API",
  "FILE",
  "EMAIL",
  "NOTIFICATION",
  "AI",
  "UTILITY",
  "CUSTOM",
] as const;
export type ToolCategory = (typeof TOOL_CATEGORIES)[number];

export interface ToolDefinition {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  category: string;
  provider: string;
  configuration: Record<string, unknown>;
  timeout_seconds: number;
  retry_count: number;
  is_active: boolean;
  status: string;
}

export interface ToolListResponse extends Page<ToolDefinition> {
  tools: ToolDefinition[];
}

export interface CreateToolRequest {
  name: string;
  description?: string | null;
  category: ToolCategory;
  provider: string;
  configuration?: Record<string, unknown>;
  timeout_seconds?: number;
  retry_count?: number;
}

// ---------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------

export type FeedbackRating = "THUMBS_UP" | "THUMBS_DOWN";

export interface Feedback {
  id: string;
  tenant_id: string;
  user_id: string;
  message_id: string;
  rating: FeedbackRating;
  comment: string | null;
  created_at: string;
}

export interface FeedbackListResponse extends Page<Feedback> {
  feedback: Feedback[];
}

export interface SubmitFeedbackRequest {
  message_id: string;
  rating: FeedbackRating;
  comment?: string | null;
}

// ---------------------------------------------------------------
// Upload Jobs
// ---------------------------------------------------------------

export type UploadJobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";

export interface UploadJob {
  id: string;
  file_name: string;
  status: UploadJobStatus;
  document_id: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------
// Usage (Token Usage + Cost Tracking, docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export interface DailyUsage {
  date: string;
  total_tokens: number;
  cost: string;
}

export interface UsageResponse {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: string;
  daily: DailyUsage[];
}

// ---------------------------------------------------------------
// Analytics (docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export interface QueriesPerDay {
  date: string;
  count: number;
}

export interface FeedbackTrend {
  date: string;
  rating: FeedbackRating;
  count: number;
}

export interface TopFailingQuery {
  message_id: string;
  content: string;
  negative_count: number;
}

export interface AnalyticsSummary {
  queries_per_day: QueriesPerDay[];
  feedback_trends: FeedbackTrend[];
  top_failing_queries: TopFailingQuery[];
}

// ---------------------------------------------------------------
// Feature Flags (docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export interface FeatureFlag {
  id: string;
  key: string;
  tenant_id: string | null;
  enabled: boolean;
  description: string | null;
}

export interface FeatureFlagListResponse extends Page<FeatureFlag> {
  feature_flags: FeatureFlag[];
}

export interface CreateFeatureFlagRequest {
  key: string;
  tenant_id?: string | null;
  enabled?: boolean;
  description?: string | null;
}

// ---------------------------------------------------------------
// Health
// ---------------------------------------------------------------

export interface HealthResponse {
  service: string;
  version: string;
  status: string;
  database: string;
  redis: string;
}

// ---------------------------------------------------------------
// Retrieval logs & observability (admin)
// ---------------------------------------------------------------

export interface RetrievalLogSummary {
  retrieval_id: string;
  trace_id: string | null;
  request_id: string | null;
  user_id: string | null;
  conversation_id: string | null;
  query_hash: string;
  query_length: number;
  strategy: string;
  top_k: number;
  reranking_enabled: boolean;
  reranker_model: string | null;
  candidate_count: number;
  selected_count: number;
  search_latency_ms: number | null;
  rerank_latency_ms: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface RetrievalResult {
  chunk_id: string;
  chunk_index: number;
  document_id: string;
  document_name: string | null;
  document_version: number | null;
  document_is_current: boolean | null;
  page_number: number | null;
  section: string | null;
  chunking_strategy: string | null;
  source_type?: string | null;
  source_name?: string | null;
  canonical_url?: string | null;
  retrieval_rank: number;
  retrieval_score: number;
  vector_score: number | null;
  keyword_score: number | null;
  reranker_score: number | null;
  final_rank: number | null;
  selected_for_context: boolean;
  reranking_changed_rank: boolean | null;
}

export interface RetrievalLogDetail extends RetrievalLogSummary {
  model_profile_id: string | null;
  min_relevance_score: number | null;
  sub_query_count: number;
  filters: Record<string, unknown>;
  results: RetrievalResult[];
}

export interface RetrievalLogList {
  total: number;
  limit: number;
  offset: number;
  retrievals: RetrievalLogSummary[];
}

export interface RetrievalSummary {
  days: number;
  retrievals: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  avg_candidates: number | null;
  avg_selected: number | null;
  empty_rate: number | null;
  low_confidence_rate: number | null;
  answers_with_sources: number;
  answers_total: number;
  citation_coverage: number | null;
}

export interface DocumentHealth {
  total: number;
  by_status: Record<string, number>;
  stale_embeddings: number;
  never_retrieved: number;
  current_pipeline_version: string;
}

export interface ObservabilitySummary {
  retrieval: RetrievalSummary;
  documents: DocumentHealth;
}

export interface TopDocument {
  document_id: string;
  document_name: string | null;
  times_retrieved: number;
  times_selected: number;
  avg_reranker_score: number | null;
}

export interface AuditEvent {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_id: string | null;
  request_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AuditList {
  total: number;
  limit: number;
  offset: number;
  events: AuditEvent[];
}

// ---------------------------------------------------------------
// Retrieval settings & re-indexing
// ---------------------------------------------------------------

export interface RetrievalValues {
  max_results: number;
  min_relevance_score: number;
  reranking_enabled: boolean;
}

export interface RetrievalSettings {
  effective: RetrievalValues;
  /** Only what this workspace changed; null = using the platform default. */
  overrides: {
    max_results: number | null;
    min_relevance_score: number | null;
    reranking_enabled: boolean | null;
  };
  defaults: RetrievalValues;
  retrieval_strategy: string;
}

export interface RetrievalSettingsUpdate {
  max_results: number | null;
  min_relevance_score: number | null;
  reranking_enabled: boolean | null;
}

export interface ReindexResult {
  queued: number;
  skipped?: number;
}

export interface ChatFilters {
  document_types?: string[];
  categories?: string[];
  tags?: string[];
  sources?: string[];
}

// ---------------------------------------------------------------
// Knowledge sources (external connectors)
// ---------------------------------------------------------------

export type SourceStatus = "active" | "paused" | "error" | "disconnected";
export type SyncMode = "manual" | "scheduled" | "webhook" | "realtime";

export interface ConfigField {
  key: string;
  label: string;
  type: "string" | "text" | "url" | "number" | "boolean" | "select" | "string_list" | "secret";
  required: boolean;
  default: unknown;
  help: string | null;
  placeholder: string | null;
  options: string[];
  minimum: number | null;
  maximum: number | null;
  group: "connection" | "content" | "filters" | "permissions" | "advanced";
}

export interface ConnectorType {
  type: string;
  display_name: string;
  description: string;
  icon: string;
  available: boolean;
  credential_kind: string;
  credential_fields: ConfigField[];
  config_schema: ConfigField[];
  supports_permissions: boolean;
  supports_changes: boolean;
  notes: string | null;
}

export interface ConnectorTypes {
  types: ConnectorType[];
  common_fields: ConfigField[];
  sync_intervals: { minutes: number; label: string }[];
}

export interface CredentialStatus {
  configured: boolean;
  kind: string | null;
  revoked: boolean;
  updated_at: string | null;
}

export interface KnowledgeSource {
  id: string;
  name: string;
  type: string;
  type_label: string;
  description: string | null;
  status: SourceStatus;
  sync_mode: SyncMode;
  sync_interval_minutes: number | null;
  last_sync_at: string | null;
  next_sync_at: string | null;
  last_successful_sync_at: string | null;
  last_sync_status: string | null;
  configuration: Record<string, unknown>;
  knowledge_base_id: string | null;
  credential: CredentialStatus;
  document_count: number;
  failed_count: number;
  health: Record<string, unknown>;
  webhook_enabled: boolean;
  /** Shown once, when created or rotated. */
  webhook_secret: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeSourceList {
  total: number;
  sources: KnowledgeSource[];
}

export interface CreateSourceRequest {
  name: string;
  type: string;
  description?: string | null;
  configuration: Record<string, unknown>;
  credentials?: Record<string, unknown> | null;
  sync_mode: SyncMode;
  sync_interval_minutes?: number | null;
}

export interface UpdateSourceRequest {
  name?: string;
  description?: string | null;
  configuration?: Record<string, unknown>;
  sync_mode?: SyncMode;
  sync_interval_minutes?: number | null;
}

export interface ConnectionTest {
  ok: boolean;
  message: string;
  authenticated: boolean | null;
  details: Record<string, unknown>;
  validation: { ok: boolean; errors: string[]; warnings: string[] } | null;
}

export interface SourcePreview {
  items: {
    external_id: string;
    title: string;
    url: string | null;
    version: string | null;
    updated_at: string | null;
    metadata: Record<string, unknown>;
  }[];
  truncated: boolean;
  warnings: string[];
}

export interface SyncRun {
  id: string;
  source_id: string;
  trigger: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled";
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  documents_discovered: number;
  documents_created: number;
  documents_updated: number;
  documents_deleted: number;
  documents_skipped: number;
  documents_failed: number;
  permissions_updated: number;
  error_count: number;
  error_summary: string | null;
  trace_id: string | null;
  request_id: string | null;
  stats: Record<string, unknown>;
}

export interface SyncRunDetail extends SyncRun {
  errors: { external_id: string; title: string; stage: string; message: string }[];
}

export interface SyncRunList {
  total: number;
  limit: number;
  offset: number;
  runs: SyncRun[];
}

export interface ExternalDocument {
  id: string;
  external_id: string;
  title: string | null;
  canonical_url: string | null;
  status: "discovered" | "pending" | "fetching" | "processing" | "indexed" | "updated" | "deleted" | "failed";
  document_id: string | null;
  external_version: string | null;
  external_updated_at: string | null;
  last_synced_at: string | null;
  last_indexed_at: string | null;
  freshness_seconds: number | null;
  failure_count: number;
  last_error: string | null;
  metadata: Record<string, unknown>;
}

export interface ExternalDocumentList {
  total: number;
  limit: number;
  offset: number;
  documents: ExternalDocument[];
}

export interface SourceHealth {
  connection: string;
  authentication: string;
  last_successful_sync_at: string | null;
  last_failed_sync_at: string | null;
  last_failure: string | null;
  avg_sync_seconds: number | null;
  documents_discovered: number;
  documents_indexed: number;
  documents_failed: number;
  api: Record<string, number | null>;
  rate_limit_used_percent: number | null;
  warnings: string[];
}

export interface SourcesSummary {
  total_sources: number;
  connected_sources: number;
  disconnected_sources: number;
  sources_with_errors: number;
  paused_sources: number;
  total_documents: number;
  total_chunks: number;
  documents_added_today: number;
  documents_updated_today: number;
  documents_deleted_today: number;
  failed_documents: number;
  last_sync_duration_seconds: number | null;
  stale_documents: number;
}

export interface IdentityMapping {
  id?: string | null;
  provider: string;
  principal_type: "user" | "group";
  external_id: string;
  internal_type: "user" | "role";
  internal_id: string;
}

export interface SourcePermissions {
  permission_mode: string;
  default_visibility: string;
  default_allowed_roles: string[];
  supports_external_permissions: boolean;
  restricted_documents: number;
  unmapped_principals: { principal_type: string; external_id: string; documents: number }[];
}
