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
  DocumentUpdate,
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
