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
import { useCreatePrompt, usePrompts } from "@/hooks/use-api";
import { PROMPT_CATEGORIES, type PromptCategory } from "@/lib/api/types";

export function PromptsView() {
  const { data, isLoading } = usePrompts();
  const createPrompt = useCreatePrompt();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<PromptCategory>("SYSTEM");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createPrompt.mutateAsync({ name, description: description || null, category });
      toast.success("Prompt created.");
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
        description="Versioned, named prompt definitions. Metadata only — actual prompt text/versioning has no UI yet."
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
              <TableHead>Status</TableHead>
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
                <TableCell>
                  <Badge variant={p.is_active ? "success" : "outline"}>
                    {p.is_active ? "active" : "inactive"}
                  </Badge>
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
    </div>
  );
}
