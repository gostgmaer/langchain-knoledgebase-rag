"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  agents,
  chat,
  conversations,
  documents,
  feedback,
  health,
  knowledgeBases,
  modelProfiles,
  prompts,
  search,
  tools,
  uploadJobs,
} from "@/lib/api/resources";
import type {
  CreateAgentRequest,
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

export function useDocuments() {
  const identity = useIdentity();
  return useQuery({
    queryKey: ["documents", identity?.tenantId],
    queryFn: () => documents.list(identity!),
    enabled: !!identity,
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
    mutationFn: (file: File) => documents.upload(identity!, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", identity?.tenantId] }),
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
