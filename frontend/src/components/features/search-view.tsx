"use client";

import { Search as SearchIcon } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useSearch } from "@/hooks/use-api";

export function SearchView() {
  const [query, setQuery] = useState("");
  const runSearch = useSearch();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    runSearch.mutate({ query: query.trim(), top_k: 10 });
  }

  return (
    <div>
      <PageHeader
        title="Search"
        description="Runs the same hybrid retrieval + cross-encoder reranking as chat, without a chat-mediated answer."
      />

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the knowledge base…"
        />
        <Button type="submit" loading={runSearch.isPending}>
          <SearchIcon className="h-4 w-4" />
          Search
        </Button>
      </form>

      {runSearch.data && runSearch.data.results.length === 0 && (
        <EmptyState icon={SearchIcon} title="No results" description="Nothing matched that query." />
      )}

      <div className="space-y-3">
        {runSearch.data?.results.map((result, i) => (
          <Card key={`${result.chunk_id}-${i}`}>
            <CardContent className="pt-5">
              <div className="mb-2 flex items-center justify-between">
                <Badge variant="secondary">score {result.score.toFixed(3)}</Badge>
                <span className="text-xs text-neutral-400">chunk #{result.chunk_index}</span>
              </div>
              <p className="text-sm text-neutral-700 dark:text-neutral-300">{result.content}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
