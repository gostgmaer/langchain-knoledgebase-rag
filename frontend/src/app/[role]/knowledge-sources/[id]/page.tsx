"use client";

import { use } from "react";

import { SourceDetailView } from "@/components/features/source-detail-view";

export default function KnowledgeSourceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SourceDetailView sourceId={id} />;
}
