"use client";

import { use } from "react";

import { DocumentDetailView } from "@/components/features/document-detail-view";

export default function DocumentDetailPage({ params }: { params: Promise<{ role: string; id: string }> }) {
  const { role, id } = use(params);
  return <DocumentDetailView documentId={id} basePath={`/${role}/documents`} />;
}
