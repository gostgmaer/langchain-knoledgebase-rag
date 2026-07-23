"use client";

import { UploadCloud } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Select } from "@/components/ui/select";
import { useUploadDocument, useUploadJob } from "@/hooks/use-api";
import type { ChunkingStrategy } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const CHUNKING_STRATEGIES: { value: ChunkingStrategy; label: string; description: string }[] = [
  { value: "auto", label: "Auto (recommended)", description: "Picks a strategy based on the file type." },
  { value: "recursive", label: "Recursive", description: "Fixed-size chunks with overlap — works for any text." },
  { value: "markdown", label: "Markdown", description: "Splits along headings — best for structured docs." },
  { value: "semantic", label: "Semantic", description: "Splits at meaning boundaries via embeddings — slower." },
];

export function UploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [chunkingStrategy, setChunkingStrategy] = useState<ChunkingStrategy>("auto");
  const upload = useUploadDocument();
  const { data: job } = useUploadJob(jobId, true);
  // Tracks which job we've already toasted for, so the one-shot success/
  // failure notification doesn't refire on every poll once a job reaches
  // a terminal status — a ref rather than state since it's bookkeeping,
  // not something a re-render should react to. jobId itself is left set
  // (not nulled out) once done: useUploadJob's refetchInterval already
  // stops polling on a terminal status on its own.
  const notifiedJobIdRef = useRef<string | null>(null);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    try {
      const result = await upload.mutateAsync({ file, chunkingStrategy });
      setJobId(result.upload_job_id);
      toast.info(`"${file.name}" accepted — ingestion running in the background.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  useEffect(() => {
    if (!jobId || !job) return;
    if (job.status !== "SUCCEEDED" && job.status !== "FAILED") return;
    if (notifiedJobIdRef.current === jobId) return;
    notifiedJobIdRef.current = jobId;

    if (job.status === "SUCCEEDED") {
      toast.success(`"${job.file_name}" ingested successfully.`);
    } else {
      toast.error(`"${job.file_name}" failed: ${job.error ?? "unknown error"}`);
    }
  }, [job, jobId]);

  return (
    <div className="space-y-3">
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
          <p className="text-xs text-neutral-400">
            Ingesting &quot;{job.file_name}&quot;… ({job.status.toLowerCase()})
          </p>
        )}
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="flex items-center gap-2">
        <label htmlFor="chunking-strategy" className="text-xs text-neutral-500 dark:text-neutral-400">
          Chunking strategy
        </label>
        <Select
          id="chunking-strategy"
          className="h-8 w-56 text-xs"
          value={chunkingStrategy}
          onChange={(e) => setChunkingStrategy(e.target.value as ChunkingStrategy)}
        >
          {CHUNKING_STRATEGIES.map((strategy) => (
            <option key={strategy.value} value={strategy.value}>
              {strategy.label}
            </option>
          ))}
        </Select>
        <span className="text-xs text-neutral-400">
          {CHUNKING_STRATEGIES.find((s) => s.value === chunkingStrategy)?.description}
        </span>
      </div>
    </div>
  );
}
