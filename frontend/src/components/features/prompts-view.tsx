"use client";

import { ScrollText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  useCreatePrompt,
  useCreatePromptVersion,
  usePromptVersions,
  usePrompts,
  usePublishPromptVersion,
} from "@/hooks/use-api";
import { PROMPT_CATEGORIES, type Prompt, type PromptCategory } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

export function PromptsView() {
  const { data, isLoading } = usePrompts();
  const createPrompt = useCreatePrompt();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<PromptCategory>("SYSTEM");
  const [versionsFor, setVersionsFor] = useState<Prompt | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createPrompt.mutateAsync({ name, description: description || null, category });
      toast.success("Prompt created — add its text from the Versions panel.");
      setOpen(false);
      setName("");
      setDescription("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create prompt.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Prompts"
        description="Versioned prompt templates. Every edit is a new version — nothing is overwritten, so rolling back is just publishing an older one again."
        actions={<Button onClick={() => setOpen(true)}>New prompt</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.prompts.length === 0 ? (
        <EmptyState icon={ScrollText} title="No prompts yet" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Live version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.prompts.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-neutral-400">{p.description}</div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{p.category}</Badge>
                </TableCell>
                <TableCell className="max-w-sm">
                  {p.published_version ? (
                    <>
                      <div className="text-xs text-neutral-500">v{p.published_version.version}</div>
                      <div className="truncate text-sm">{p.published_version.template}</div>
                    </>
                  ) : (
                    <span className="text-xs text-amber-600">no published version yet</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={p.is_active ? "success" : "outline"}>
                    {p.is_active ? "active" : "inactive"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button size="sm" variant="outline" onClick={() => setVersionsFor(p)}>
                    Versions
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New prompt">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label>Description</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label>Category</Label>
            <Select value={category} onChange={(e) => setCategory(e.target.value as PromptCategory)}>
              {PROMPT_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <Button type="submit" loading={createPrompt.isPending}>
            Create
          </Button>
        </form>
      </Dialog>

      {versionsFor && (
        <VersionsDialog prompt={versionsFor} onClose={() => setVersionsFor(null)} />
      )}
    </div>
  );
}

function VersionsDialog({ prompt, onClose }: { prompt: Prompt; onClose: () => void }) {
  const { data, isLoading } = usePromptVersions(prompt.id);
  const createVersion = useCreatePromptVersion(prompt.id);
  const publishVersion = usePublishPromptVersion(prompt.id);
  const [template, setTemplate] = useState("");
  const [changelog, setChangelog] = useState("");

  async function handleCreateVersion(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createVersion.mutateAsync({ template, changelog: changelog || null });
      toast.success("Draft version created — publish it to make it live.");
      setTemplate("");
      setChangelog("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create version.");
    }
  }

  async function handlePublish(versionId: string, version: number) {
    try {
      await publishVersion.mutateAsync(versionId);
      toast.success(`Version ${version} is now live.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not publish version.");
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={`${prompt.name} — versions`}
      description="Every version is kept. Publishing an older one is how a rollback works here."
      className="max-w-2xl"
    >
      <form onSubmit={handleCreateVersion} className="mb-6 grid gap-3 rounded-lg border p-4">
        <Label>New draft version</Label>
        <Textarea
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          placeholder="The actual prompt template text…"
          rows={5}
          required
        />
        <Input
          value={changelog}
          onChange={(e) => setChangelog(e.target.value)}
          placeholder="What changed? (optional)"
        />
        <Button type="submit" size="sm" loading={createVersion.isPending} className="justify-self-start">
          Save as new draft
        </Button>
      </form>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : !data || data.versions.length === 0 ? (
        <EmptyState icon={ScrollText} title="No versions yet" description="Create the first one above." />
      ) : (
        <div className="grid gap-3">
          {data.versions.map((v) => (
            <div key={v.id} className="rounded-lg border p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">v{v.version}</span>
                  <Badge variant={v.is_published ? "success" : v.status === "DRAFT" ? "outline" : "secondary"}>
                    {v.is_published ? "LIVE" : v.status}
                  </Badge>
                  <span className="text-xs text-neutral-400">{formatDateTime(v.created_at)}</span>
                </div>
                {!v.is_published && (
                  <Button
                    size="sm"
                    variant="outline"
                    loading={publishVersion.isPending}
                    onClick={() => handlePublish(v.id, v.version)}
                  >
                    Publish
                  </Button>
                )}
              </div>
              {v.changelog && <p className="mb-1 text-xs text-neutral-500">{v.changelog}</p>}
              <pre className="whitespace-pre-wrap rounded bg-neutral-50 p-2 text-xs dark:bg-neutral-900">
                {v.template}
              </pre>
            </div>
          ))}
        </div>
      )}
    </Dialog>
  );
}
