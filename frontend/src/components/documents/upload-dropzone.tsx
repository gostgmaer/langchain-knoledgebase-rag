"use client";

import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { useUploadDocument, useUploadJob } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

export function UploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const upload = useUploadDocument();
  const { data: job } = useUploadJob(jobId, true);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    try {
      const result = await upload.mutateAsync(file);
      setJobId(result.upload_job_id);
      toast.info(`"${file.name}" accepted — ingestion running in the background.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  if (job?.status === "SUCCEEDED" && jobId) {
    // One-shot toast, then clear so re-uploading the same file works again.
    toast.success(`"${job.file_name}" ingested successfully.`);
    setJobId(null);
  } else if (job?.status === "FAILED" && jobId) {
    toast.error(`"${job.file_name}" failed: ${job.error ?? "unknown error"}`);
    setJobId(null);
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors",
        dragOver
          ? "border-neutral-900 bg-neutral-50 dark:border-neutral-100 dark:bg-neutral-900"
          : "border-neutral-200 dark:border-neutral-800",
      )}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <UploadCloud className="h-6 w-6 text-neutral-400" />
      <p className="text-sm text-neutral-600 dark:text-neutral-400">
        Drag a file here, or{" "}
        <button
          type="button"
          className="font-medium text-neutral-900 underline underline-offset-2 dark:text-neutral-100"
          onClick={() => inputRef.current?.click()}
        >
          browse
        </button>
      </p>
      {job && (job.status === "QUEUED" || job.status === "RUNNING") && (
        <p className="text-xs text-neutral-400">Ingesting "{job.file_name}"… ({job.status.toLowerCase()})</p>
      )}
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
