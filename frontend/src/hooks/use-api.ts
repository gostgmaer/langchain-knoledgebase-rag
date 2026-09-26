"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  agents,
  analytics,
  chat,
  conversations,
  documents,
  featureFlags,
  feedback,
  health,
  knowledgeBases,
  knowledgeSources,
  modelProfiles,
  observability,
  prompts,
  retrievalLogs,
  retrievalSettings,
  search,
  tools,
  uploadJobs,
  usage,
} from "@/lib/api/resources";
import type {
  CreateSourceRequest,
  DocumentUpdate,
  IdentityMapping,
  UpdateSourceRequest,
  RetrievalSettingsUpdate,
  DocumentUploadOptions,
  CreateAgentRequest,
  CreateFeatureFlagRequest,
  CreateKnowledgeBaseRequest,
  CreateModelProfileRequest,
  CreatePromptRequest,
  CreateToolRequest,
  FeedbackRating,
  SearchRequest,
  SubmitFeedbackRequest,
} from "@/lib/api/types";
import { useSession } from "@/lib/session";

function useIdentity() {
  const { session } = useSession();
  return session ? { tenantId: session.tenantId, userId: session.userId } : null;
}

// ---------------------------------------------------------------
// Health
// ---------------------------------------------------------------

export function useHealth() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["health"],
    queryFn: () => health.get(identity!),
    enabled: !!identity,
    refetchInterval: 30_000,
  });
}

// ---------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------

export function useConversation(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["conversation", identity?.tenantId, id],
    queryFn: () => conversations.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useConversationMessages(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["conversation-messages", identity?.tenantId, id],
    queryFn: () => conversations.messages(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useSendChat() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { message: string; conversation_id?: string }) =>
      chat.send(identity!, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["conversation-messages", identity?.tenantId, data.conversation_id] });
    },
  });
}

// ---------------------------------------------------------------
// Documents
// ---------------------------------------------------------------

export function useDocuments(knowledgeBaseId?: string) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["documents", identity?.tenantId, knowledgeBaseId ?? null],
    queryFn: () => documents.list(identity!, knowledgeBaseId),
    enabled: !!identity,
  });
}

export function useDocumentChunks(id: string | null, limit: number, offset: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["document-chunks", identity?.tenantId, id, limit, offset],
    queryFn: () => documents.chunks(identity!, id!, limit, offset),
    enabled: !!identity && !!id,
    placeholderData: (previous) => previous,
  });
}

export function useDocument(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["document", identity?.tenantId, id],
    queryFn: () => documents.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useDocumentVersions(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["document-versions", identity?.tenantId, id],
    queryFn: () => documents.versions(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useUploadDocument() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, options }: { file: File; options?: DocumentUploadOptions }) =>
      documents.upload(identity!, file, options),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", identity?.tenantId] }),
  });
}

export function useReindexDocument(id: string) {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => documents.reindex(identity!, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["document", identity?.tenantId, id] }),
  });
}

export function useReindexOutdated() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => documents.reindexOutdated(identity!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents", identity?.tenantId] });
      void queryClient.invalidateQueries({ queryKey: ["observability-summary", identity?.tenantId] });
    },
  });
}

export function useRetrievalSettings() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["retrieval-settings", identity?.tenantId],
    queryFn: () => retrievalSettings.get(identity!),
    enabled: !!identity,
  });
}

export function useSaveRetrievalSettings() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RetrievalSettingsUpdate) => retrievalSettings.save(identity!, body),
    onSuccess: (data) => queryClient.setQueryData(["retrieval-settings", identity?.tenantId], data),
  });
}

export function useUpdateDocument(id: string) {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DocumentUpdate) => documents.update(identity!, id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents", identity?.tenantId] });
      void queryClient.invalidateQueries({ queryKey: ["document", identity?.tenantId, id] });
      void queryClient.invalidateQueries({ queryKey: ["observability-audit", identity?.tenantId] });
    },
  });
}

export function useDeleteKnowledgeBase() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => knowledgeBases.delete(identity!, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases", identity?.tenantId] }),
  });
}

export function useDeleteFeatureFlag() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => featureFlags.delete(identity!, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feature-flags"] }),
  });
}

export function useDeleteDocument() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => documents.delete(identity!, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", identity?.tenantId] }),
  });
}

export function useUploadJob(id: string | null, pollWhilePending: boolean) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["upload-job", identity?.tenantId, id],
    queryFn: () => uploadJobs.get(identity!, id!),
    enabled: !!identity && !!id,
    refetchInterval: (query) => {
      if (!pollWhilePending) return false;
      const status = query.state.data?.status;
      return status === "QUEUED" || status === "RUNNING" ? 1500 : false;
    },
  });
}

// ---------------------------------------------------------------
// Knowledge Bases
// ---------------------------------------------------------------

export function useKnowledgeBases() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["knowledge-bases", identity?.tenantId],
    queryFn: () => knowledgeBases.list(identity!),
    enabled: !!identity,
  });
}

export function useKnowledgeBase(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["knowledge-base", identity?.tenantId, id],
    queryFn: () => knowledgeBases.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useCreateKnowledgeBase() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateKnowledgeBaseRequest) => knowledgeBases.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Search
// ---------------------------------------------------------------

export function useSearch() {
  const identity = useIdentity();
  return useMutation({
    mutationFn: (body: SearchRequest) => search.run(identity!, body),
  });
}

// ---------------------------------------------------------------
// Agents
// ---------------------------------------------------------------

export function useAgents() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["agents", identity?.tenantId],
    queryFn: () => agents.list(identity!),
    enabled: !!identity,
  });
}

export function useAgent(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["agent", identity?.tenantId, id],
    queryFn: () => agents.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useCreateAgent() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAgentRequest) => agents.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agents", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Model Profiles
// ---------------------------------------------------------------

export function useModelProfiles() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["model-profiles"],
    queryFn: () => modelProfiles.list(identity!),
    enabled: !!identity,
  });
}

export function useModelProfile(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["model-profile", id],
    queryFn: () => modelProfiles.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useCreateModelProfile() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateModelProfileRequest) => modelProfiles.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["model-profiles"] }),
  });
}

// ---------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------

export function usePrompts() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["prompts", identity?.tenantId],
    queryFn: () => prompts.list(identity!),
    enabled: !!identity,
  });
}

export function useCreatePrompt() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreatePromptRequest) => prompts.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["prompts", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Tool Definitions
// ---------------------------------------------------------------

export function useTools() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["tools", identity?.tenantId],
    queryFn: () => tools.list(identity!),
    enabled: !!identity,
  });
}

export function useCreateTool() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateToolRequest) => tools.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tools", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------

export function useFeedbackList(rating?: FeedbackRating) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["feedback", identity?.tenantId, rating],
    queryFn: () => feedback.list(identity!, rating),
    enabled: !!identity,
  });
}

export function useSubmitFeedback() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitFeedbackRequest) => feedback.submit(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feedback", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Usage (Token Usage + Cost Tracking, docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export function useUsage(days = 30) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["usage", identity?.tenantId, days],
    queryFn: () => usage.get(identity!, days),
    enabled: !!identity,
  });
}

// ---------------------------------------------------------------
// Analytics (docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export function useAnalyticsSummary(days = 30) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["analytics-summary", identity?.tenantId, days],
    queryFn: () => analytics.summary(identity!, days),
    enabled: !!identity,
  });
}

// ---------------------------------------------------------------
// Feature Flags (docs/mvpRAG.md v1.1)
// ---------------------------------------------------------------

export function useFeatureFlags() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["feature-flags", identity?.tenantId],
    queryFn: () => featureFlags.list(identity!),
    enabled: !!identity,
  });
}

export function useCreateFeatureFlag() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateFeatureFlagRequest) => featureFlags.create(identity!, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feature-flags", identity?.tenantId] }),
  });
}

export function useToggleFeatureFlag() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      featureFlags.toggle(identity!, id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feature-flags", identity?.tenantId] }),
  });
}

// ---------------------------------------------------------------
// Retrieval logs & observability
// ---------------------------------------------------------------

export function useRetrievalLogs(limit: number, offset: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["retrieval-logs", identity?.tenantId, limit, offset],
    queryFn: () => retrievalLogs.list(identity!, limit, offset),
    enabled: !!identity,
    placeholderData: (previous) => previous,
  });
}

export function useRetrievalLog(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["retrieval-log", identity?.tenantId, id],
    queryFn: () => retrievalLogs.get(identity!, id!),
    enabled: !!identity && !!id,
  });
}

export function useObservabilitySummary(days: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["observability-summary", identity?.tenantId, days],
    queryFn: () => observability.summary(identity!, days),
    enabled: !!identity,
  });
}

export function useTopDocuments(days: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["observability-top-documents", identity?.tenantId, days],
    queryFn: () => observability.topDocuments(identity!, days),
    enabled: !!identity,
  });
}

export function useAuditEvents(limit: number, offset: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["observability-audit", identity?.tenantId, limit, offset],
    queryFn: () => observability.audit(identity!, limit, offset),
    enabled: !!identity,
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------
// Knowledge sources
// ---------------------------------------------------------------

/** Sources being synced refresh themselves; everything else is fetched on demand. */
const SOURCE_POLL_MS = 4000;

export function useSourceTypes() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-types", identity?.tenantId],
    queryFn: () => knowledgeSources.types(identity!),
    enabled: !!identity,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSourcesSummary() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["sources-summary", identity?.tenantId],
    queryFn: () => knowledgeSources.summary(identity!),
    enabled: !!identity,
    refetchInterval: SOURCE_POLL_MS * 3,
  });
}

export function useKnowledgeSources() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["knowledge-sources", identity?.tenantId],
    queryFn: () => knowledgeSources.list(identity!),
    enabled: !!identity,
    refetchInterval: SOURCE_POLL_MS * 2,
  });
}

export function useKnowledgeSource(id: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["knowledge-source", identity?.tenantId, id],
    queryFn: () => knowledgeSources.get(identity!, id!),
    enabled: !!identity && !!id,
    refetchInterval: SOURCE_POLL_MS * 2,
  });
}

export function useSourceRuns(id: string, limit: number, offset: number) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-runs", identity?.tenantId, id, limit, offset],
    queryFn: () => knowledgeSources.runs(identity!, id, limit, offset),
    enabled: !!identity,
    placeholderData: (previous) => previous,
    // Poll while anything is still running so progress shows without a manual refresh.
    refetchInterval: (query) =>
      query.state.data?.runs.some((r) => r.status === "queued" || r.status === "running") ? SOURCE_POLL_MS : false,
  });
}

export function useSourceRun(id: string, runId: string | null) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-run", identity?.tenantId, id, runId],
    queryFn: () => knowledgeSources.run(identity!, id, runId!),
    enabled: !!identity && !!runId,
    refetchInterval: (query) =>
      query.state.data && (query.state.data.status === "queued" || query.state.data.status === "running") ? SOURCE_POLL_MS : false,
  });
}

export function useSourceDocuments(id: string, limit: number, offset: number, status: string, q: string) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-documents", identity?.tenantId, id, limit, offset, status, q],
    queryFn: () => knowledgeSources.documents(identity!, id, limit, offset, status, q),
    enabled: !!identity,
    placeholderData: (previous) => previous,
  });
}

export function useSourceHealth(id: string) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-health", identity?.tenantId, id],
    queryFn: () => knowledgeSources.health(identity!, id),
    enabled: !!identity,
    refetchInterval: SOURCE_POLL_MS * 3,
  });
}

export function useSourcePermissions(id: string) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["source-permissions", identity?.tenantId, id],
    queryFn: () => knowledgeSources.permissions(identity!, id),
    enabled: !!identity,
  });
}

export function useIdentityMappings(provider: string) {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["identity-mappings", identity?.tenantId, provider],
    queryFn: () => knowledgeSources.mappings(identity!, provider),
    enabled: !!identity,
  });
}

function useSourceInvalidation() {
  const identity = useIdentity();
  const queryClient = useQueryClient();
  return () => {
    for (const key of ["knowledge-sources", "knowledge-source", "sources-summary", "source-runs", "source-run", "source-documents", "source-health", "source-permissions", "documents"]) {
      void queryClient.invalidateQueries({ queryKey: [key, identity?.tenantId] });
    }
  };
}

export function useCreateSource() {
  const identity = useIdentity();
  const invalidate = useSourceInvalidation();
  return useMutation({
    mutationFn: (body: CreateSourceRequest) => knowledgeSources.create(identity!, body),
    onSuccess: invalidate,
  });
}

export function useUpdateSource(id: string) {
  const identity = useIdentity();
  const invalidate = useSourceInvalidation();
  return useMutation({
    mutationFn: (body: UpdateSourceRequest) => knowledgeSources.update(identity!, id, body),
    onSuccess: invalidate,
  });
}

/** Actions on one source that change what the pages show. */
export function useSourceAction(id: string) {
  const identity = useIdentity();
  const invalidate = useSourceInvalidation();
  const run = (fn: () => Promise<unknown>) => async () => {
    const result = await fn();
    invalidate();
    return result;
  };
  return {
    sync: useMutation({ mutationFn: (activate: boolean) => knowledgeSources.sync(identity!, id, activate), onSuccess: invalidate }),
    cancel: useMutation({ mutationFn: run(() => knowledgeSources.cancel(identity!, id)) }),
    pause: useMutation({ mutationFn: run(() => knowledgeSources.pause(identity!, id)) }),
    resume: useMutation({ mutationFn: run(() => knowledgeSources.resume(identity!, id)) }),
    remove: useMutation({ mutationFn: run(() => knowledgeSources.remove(identity!, id)) }),
    testSaved: useMutation({ mutationFn: () => knowledgeSources.testSaved(identity!, id), onSuccess: invalidate }),
    preview: useMutation({ mutationFn: (limit: number) => knowledgeSources.preview(identity!, id, limit) }),
    setCredentials: useMutation({ mutationFn: (credentials: Record<string, unknown>) => knowledgeSources.setCredentials(identity!, id, credentials), onSuccess: invalidate }),
    revokeCredentials: useMutation({ mutationFn: () => knowledgeSources.revokeCredentials(identity!, id), onSuccess: invalidate }),
    retryDocument: useMutation({ mutationFn: (recordId: string) => knowledgeSources.retryDocument(identity!, id, recordId), onSuccess: invalidate }),
  };
}

export function useTestUnsavedSource() {
  const identity = useIdentity();
  return useMutation({
    mutationFn: (body: { type: string; configuration: Record<string, unknown>; credentials?: Record<string, unknown> | null }) =>
      knowledgeSources.testUnsaved(identity!, body),
  });
}

export function useSaveMapping() {
  const identity = useIdentity();
  const invalidate = useSourceInvalidation();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IdentityMapping) => knowledgeSources.saveMapping(identity!, body),
    onSuccess: () => {
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ["identity-mappings", identity?.tenantId] });
    },
  });
}

export function useDeleteMapping() {
  const identity = useIdentity();
  const invalidate = useSourceInvalidation();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => knowledgeSources.deleteMapping(identity!, id),
    onSuccess: () => {
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ["identity-mappings", identity?.tenantId] });
    },
  });
}
