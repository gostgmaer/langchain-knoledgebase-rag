"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useUploadJob } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";

export function UploadJobsView() {
  const [draft, setDraft] = useState("");
  const [lookupId, setLookupId] = useState<string | null>(null);
  const { data: job, isFetching, isError } = useUploadJob(lookupId, true);

  return (
    <div>
      <PageHeader
        title="Upload Jobs"
        description="The backend has no list-all endpoint for these — paste the upload_job_id returned from a document upload to check its real pipeline progress."
      />

      <form
        className="mb-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setLookupId(draft.trim() || null);
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="upload_job_id (UUID)"
          className="font-mono"
        />
        <Button type="submit" loading={isFetching}>
          <Search className="h-4 w-4" />
          Look up
        </Button>
      </form>

      {isError && <p className="text-sm text-red-600">No upload job found with that ID.</p>}

      {job && (
        <Card>
          <CardContent className="grid gap-2 pt-5 text-sm">
            <Row label="File" value={job.file_name} />
            <Row label="Status" value={<StatusBadge status={job.status} />} />
            <Row label="Document ID" value={job.document_id ?? "—"} />
            <Row label="Error" value={job.error ?? "—"} />
            <Row label="Started" value={formatDateTime(job.started_at)} />
            <Row label="Finished" value={formatDateTime(job.finished_at)} />
            <Row label="Created" value={formatDateTime(job.created_at)} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-neutral-100 pb-2 last:border-0 dark:border-neutral-900">
      <span className="text-neutral-500">{label}</span>
      <span>{value}</span>
    </div>
  );
}
