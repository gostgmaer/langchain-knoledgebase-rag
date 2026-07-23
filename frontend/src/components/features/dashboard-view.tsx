"use client";

import { Bot, FileText, Library, MessagesSquare } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useAgents,
  useDocuments,
  useFeedbackList,
  useHealth,
  useKnowledgeBases,
} from "@/hooks/use-api";
import { useSession } from "@/lib/session";

export function DashboardView({ basePath }: { basePath: string }) {
  const { session } = useSession();
  const { data: health } = useHealth();
  const { data: documents } = useDocuments();
  const { data: knowledgeBases } = useKnowledgeBases();
  const { data: agents } = useAgents();
  const { data: feedback } = useFeedbackList();

  const stats = [
    { label: "Documents", value: documents?.total ?? "—", href: `${basePath}/documents`, icon: FileText },
    { label: "Knowledge Bases", value: knowledgeBases?.total ?? "—", href: `${basePath}/knowledge-bases`, icon: Library },
    { label: "Agents", value: agents?.total ?? "—", href: `${basePath}/agents`, icon: Bot },
    { label: "Feedback", value: feedback?.total ?? "—", href: `${basePath}/feedback`, icon: MessagesSquare },
  ];

  return (
    <div>
      <PageHeader
        title={`Welcome, ${session?.displayName ?? ""}`}
        description={`Browsing tenant ${session?.tenantId}`}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, href, icon: Icon }) => (
          <Link key={label} href={href}>
            <Card className="transition-colors hover:border-neutral-300 dark:hover:border-neutral-700">
              <CardContent className="flex items-center justify-between pt-5">
                <div>
                  <p className="text-xs text-neutral-500">{label}</p>
                  <p className="text-2xl font-semibold">{value}</p>
                </div>
                <Icon className="h-6 w-6 text-neutral-300 dark:text-neutral-700" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backend health</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-xs text-neutral-500">Service</p>
            <p>{health?.status ?? "checking…"}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-500">Database</p>
            <p>{health?.database ?? "checking…"}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-500">Redis</p>
            <p>{health?.redis ?? "checking…"}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
