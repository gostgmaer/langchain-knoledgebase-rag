"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { DOCS_SECTIONS, DOCS_TOPICS } from "@/lib/docs-topics";

export function DocsIndexView() {
  const { role } = useParams<{ role: string }>();

  return (
    <div>
      <PageHeader
        title="Documentation"
        description="How to use every part of Meridian, by what you're trying to do. Pick a topic below."
      />

      <div className="flex flex-col gap-8">
        {DOCS_SECTIONS.map((section) => {
          const topics = DOCS_TOPICS.filter((t) => t.section === section);
          if (topics.length === 0) return null;
          return (
            <div key={section}>
              <p className="mb-3 text-xs font-semibold tracking-wider text-neutral-400 uppercase dark:text-neutral-600">
                {section}
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {topics.map((topic) => (
                  <Link key={topic.slug} href={`/${role}/docs/${topic.slug}`}>
                    <Card className="h-full transition-colors hover:border-neutral-300 dark:hover:border-neutral-700">
                      <CardContent className="flex items-start justify-between gap-3 pt-5">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium">{topic.title}</p>
                            {topic.roleNote && (
                              <Badge variant="outline" className="text-[0.65rem]">
                                {topic.roleNote}
                              </Badge>
                            )}
                          </div>
                          <p className="mt-1 text-xs text-neutral-500">{topic.description}</p>
                        </div>
                        <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" aria-hidden="true" />
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
