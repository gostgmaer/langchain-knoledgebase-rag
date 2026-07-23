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

export interface SearchRequest {
  query: string;
  document_id?: string | null;
  top_k?: number;
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
// Health
// ---------------------------------------------------------------

export interface HealthResponse {
  service: string;
  version: string;
  status: string;
  database: string;
  redis: string;
}
