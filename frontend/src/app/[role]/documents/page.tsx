"use client";

import { use } from "react";

import { DocumentsView } from "@/components/features/documents-view";

export default function DocumentsPage({ params }: { params: Promise<{ role: string }> }) {
  const { role } = use(params);
  return <DocumentsView basePath={`/${role}/documents`} />;
}
