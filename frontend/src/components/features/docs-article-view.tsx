"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DocsMarkdown } from "@/components/features/docs-markdown";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Skeleton } from "@/components/ui/skeleton";
import { DOCS_TOPICS, findDocsTopic } from "@/lib/docs-topics";

async function fetchTopic(slug: string): Promise<string> {
  const res = await fetch(`/docs/topics/${slug}.md`);
  if (!res.ok) throw new Error(`Could not load this page (HTTP ${res.status}).`);
  return res.text();
}

export function DocsArticleView() {
  const { role, slug } = useParams<{ role: string; slug: string }>();
  const topic = findDocsTopic(slug);
  const index = DOCS_TOPICS.findIndex((t) => t.slug === slug);
  const previous = index > 0 ? DOCS_TOPICS[index - 1] : undefined;
  const next = index >= 0 && index < DOCS_TOPICS.length - 1 ? DOCS_TOPICS[index + 1] : undefined;

  const { data, isError, error, isLoading, refetch } = useQuery({
    queryKey: ["docs-topic", slug],
    queryFn: () => fetchTopic(slug),
    enabled: !!topic,
  });

  if (!topic) {
    return (
      <div>
        <PageHeader title="Page not found" description="That documentation page doesn't exist." />
        <Link href={`/${role}/docs`} className="text-sm font-medium underline underline-offset-2">
          Back to Documentation
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Link
        href={`/${role}/docs`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100"
      >
        <ChevronLeft className="h-4 w-4" />
        Documentation
      </Link>

      <PageHeader title={topic.title} description={topic.description} />

      {isError ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : isLoading || !data ? (
        <div className="max-w-3xl space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ) : (
        <DocsMarkdown content={data} />
      )}

      <div className="mt-10 flex max-w-3xl items-center justify-between gap-3 border-t border-neutral-200 pt-4 text-sm dark:border-neutral-800">
        {previous ? (
          <Link href={`/${role}/docs/${previous.slug}`} className="inline-flex items-center gap-1.5 font-medium hover:underline">
            <ArrowLeft className="h-3.5 w-3.5" />
            {previous.title}
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link href={`/${role}/docs/${next.slug}`} className="inline-flex items-center gap-1.5 font-medium hover:underline">
            {next.title}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}
