"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useRetrievalSettings, useSaveRetrievalSettings } from "@/hooks/use-api";
import type { RetrievalSettings } from "@/lib/api/types";

/** How many chunks answers use, how strict the relevance cut-off is, and whether reranking runs. */
export function RetrievalSettingsView() {
  const { data, isLoading, isError, error, refetch } = useRetrievalSettings();

  return (
    <div>
      <PageHeader
        title="Retrieval settings"
        description="Tune how this workspace finds the text answers are built from. Changes apply within about 30 seconds."
      />
      {isError ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : isLoading || !data ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        // Keyed by the saved values so the form re-seeds after a save without an effect.
        <SettingsForm key={JSON.stringify(data.overrides)} data={data} />
      )}
    </div>
  );
}

function SettingsForm({ data }: { data: RetrievalSettings }) {
  const { role } = useParams<{ role: string }>();
  const save = useSaveRetrievalSettings();
  const o = data.overrides;
  const d = data.defaults;

  // Text state so a field can be empty ("use the platform default").
  const [maxResults, setMaxResults] = useState(o.max_results?.toString() ?? "");
  const [minScore, setMinScore] = useState(o.min_relevance_score?.toString() ?? "");
  const [rerank, setRerank] = useState<boolean | null>(o.reranking_enabled);

  const effectiveRerank = rerank ?? d.reranking_enabled;
  const maxNum = maxResults === "" ? null : Number(maxResults);
  const minNum = minScore === "" ? null : Number(minScore);
  const invalid =
    (maxNum !== null && (!Number.isInteger(maxNum) || maxNum < 1 || maxNum > 20)) ||
    (minNum !== null && (Number.isNaN(minNum) || minNum < -10 || minNum > 10));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (invalid) return;
    try {
      await save.mutateAsync({ max_results: maxNum, min_relevance_score: minNum, reranking_enabled: rerank });
      toast.success("Retrieval settings saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the settings.");
    }
  }

  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Answer context</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5 text-sm">
          <label className="grid gap-1">
            <span className="font-medium">Chunks used per answer</span>
            <Input
              type="number"
              min={1}
              max={20}
              step={1}
              value={maxResults}
              placeholder={`${d.max_results} (platform default)`}
              onChange={(e) => setMaxResults(e.target.value)}
              aria-label="Chunks used per answer"
            />
            <span className="text-xs text-neutral-500">
              More chunks help when an answer spans several passages, and make prompts longer and slower. 1–20.
            </span>
          </label>

          <label className="grid gap-1">
            <span className="font-medium">Minimum relevance score</span>
            <Input
              type="number"
              min={-10}
              max={10}
              step={0.1}
              value={minScore}
              placeholder={`${d.min_relevance_score} (platform default)`}
              onChange={(e) => setMinScore(e.target.value)}
              disabled={!effectiveRerank}
              aria-label="Minimum relevance score"
            />
            <span className="text-xs text-neutral-500">
              Chunks the reranker scores below this are dropped; the single best chunk is always kept. Higher = stricter,
              fewer but more relevant chunks. Only applies while reranking is on. The Retrieval Log shows real scores.
            </span>
          </label>

          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-1">
              <span className="font-medium">Rerank with the cross-encoder</span>
              <span className="text-xs text-neutral-500">
                A second, slower pass that re-scores candidates against the question. Off = keep the search ranking (faster;
                the relevance score above no longer applies).
              </span>
            </div>
            <div className="flex items-center gap-2">
              {rerank === null && <Badge variant="outline">default</Badge>}
              <Switch checked={effectiveRerank} onCheckedChange={(v) => setRerank(v)} aria-label="Rerank with the cross-encoder" />
            </div>
          </div>

          <p className="text-xs text-neutral-400">
            Search strategy (<code>{data.retrieval_strategy}</code>) is fixed for the whole platform. Try changes in{" "}
            <Link className="underline" href={`/${role}/search`}>
              Search
            </Link>{" "}
            or Chat, then check <Link className="underline" href={`/${role}/retrieval`}>the Retrieval Log</Link>. Leave a field empty to use the
            platform default.
          </p>

          {invalid && <p className="text-xs text-red-600">Values are out of range.</p>}

          <div className="flex gap-2">
            <Button type="submit" loading={save.isPending} disabled={invalid}>
              Save
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setMaxResults("");
                setMinScore("");
                setRerank(null);
              }}
            >
              Reset to defaults
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}
