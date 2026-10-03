"use client";

import { Wrench } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useCreateTool, useTools } from "@/hooks/use-api";
import { TOOL_CATEGORIES, type ToolCategory } from "@/lib/api/types";

// packages/tools/builtin/ — real, code-defined, always available to chat regardless of tenant.
// Not DB rows, so there's no API to list them; kept in sync with that directory by hand.
const BUILTIN_TOOLS = [
  { name: "calculator", description: "Perform mathematical calculations." },
  { name: "get_weather", description: "Get the current weather for a given location." },
  { name: "get_news", description: "Get the latest news for a given topic." },
  { name: "get_google_search", description: "Get the latest news/results for a given topic via Google." },
  { name: "search_knowledge_base", description: "Explicitly search the user's knowledge base for a specific query." },
  { name: "search_document", description: "Search within a single, specific document." },
  { name: "lookup_iam_user", description: "Look up an EasyDev platform user's profile." },
  { name: "lookup_iam_tenant", description: "Look up details about the current tenant/organization." },
];

export function ToolsView() {
  const { data, isLoading } = useTools();
  const createTool = useCreateTool();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ToolCategory>("CUSTOM");
  const [provider, setProvider] = useState("");
  const [url, setUrl] = useState("");
  const [method, setMethod] = useState<"POST" | "GET">("POST");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createTool.mutateAsync({
        name,
        description: description || null,
        category,
        provider,
        configuration: category === "CUSTOM" && url ? { url, method } : undefined,
      });
      toast.success(
        category === "CUSTOM"
          ? "Tool created — it's now callable in chat."
          : "Tool definition created.",
      );
      setOpen(false);
      setName("");
      setDescription("");
      setProvider("");
      setUrl("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create tool definition.");
    }
  }

  const customTools = data?.tools.filter((t) => t.category === "CUSTOM") ?? [];
  const otherTools = data?.tools.filter((t) => t.category !== "CUSTOM") ?? [];

  return (
    <div>
      <PageHeader
        title="Tools"
        description="Built-in tools power every chat automatically. A CUSTOM tool with a URL becomes a real, callable webhook tool too — other categories are metadata only for now."
        actions={<Button onClick={() => setOpen(true)}>New tool definition</Button>}
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Built-in (always available, not editable here)</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {BUILTIN_TOOLS.map((t) => (
            <div key={t.name} className="flex items-start gap-2 text-sm">
              <Badge variant="outline" className="shrink-0 font-mono text-xs">
                {t.name}
              </Badge>
              <span className="text-neutral-500">{t.description}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <h2 className="mb-2 text-sm font-medium text-neutral-700 dark:text-neutral-300">Custom webhook tools</h2>
      {isLoading ? (
        <Skeleton className="mb-6 h-32 w-full" />
      ) : customTools.length === 0 ? (
        <EmptyState icon={Wrench} title="No custom tools yet" description="Create a CUSTOM tool with a URL to make it callable in chat." />
      ) : (
        <Table className="mb-6">
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>URL</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customTools.map((t) => (
              <TableRow key={t.id}>
                <TableCell>
                  <div className="font-medium">{t.name}</div>
                  <div className="text-xs text-neutral-400">{t.description}</div>
                </TableCell>
                <TableCell className="max-w-xs truncate font-mono text-xs text-neutral-500">
                  {typeof t.configuration.url === "string" ? t.configuration.url : (
                    <span className="text-amber-600">missing — not callable in chat</span>
                  )}
                </TableCell>
                <TableCell>
                  <StatusBadge status={t.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {otherTools.length > 0 && (
        <>
          <h2 className="mb-2 text-sm font-medium text-neutral-700 dark:text-neutral-300">Other definitions (metadata only)</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {otherTools.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-neutral-400">{t.description}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{t.category}</Badge>
                  </TableCell>
                  <TableCell className="text-neutral-500">{t.provider}</TableCell>
                  <TableCell>
                    <StatusBadge status={t.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New tool definition">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label>Description (what the LLM sees — be specific about when to call it)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label>Category</Label>
            <Select value={category} onChange={(e) => setCategory(e.target.value as ToolCategory)}>
              {TOOL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Provider</Label>
            <Input value={provider} onChange={(e) => setProvider(e.target.value)} required />
          </div>
          {category === "CUSTOM" && (
            <>
              <div className="grid gap-1.5">
                <Label>Webhook URL (required to actually become callable in chat)</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/your-webhook"
                  type="url"
                />
              </div>
              <div className="grid gap-1.5">
                <Label>Method</Label>
                <Select value={method} onChange={(e) => setMethod(e.target.value as "POST" | "GET")}>
                  <option value="POST">POST (JSON body: {"{ input }"})</option>
                  <option value="GET">GET (query param: ?input=...)</option>
                </Select>
              </div>
            </>
          )}
          <Button type="submit" loading={createTool.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
