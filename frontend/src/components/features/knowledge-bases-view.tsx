"use client";

import { Library } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useCreateKnowledgeBase, useKnowledgeBases } from "@/hooks/use-api";

export function KnowledgeBasesView() {
  const { data, isLoading } = useKnowledgeBases();
  const createKb = useCreateKnowledgeBase();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createKb.mutateAsync({ name, description: description || null });
      toast.success("Knowledge base created.");
      setOpen(false);
      setName("");
      setDescription("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create knowledge base.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Knowledge Bases"
        description="Named collections of documents that retrieval is scoped around."
        actions={<Button onClick={() => setOpen(true)}>New knowledge base</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.knowledge_bases.length === 0 ? (
        <EmptyState icon={Library} title="No knowledge bases yet" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.knowledge_bases.map((kb) => (
            <Card key={kb.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{kb.name}</CardTitle>
                  {kb.is_public && <Badge variant="secondary">public</Badge>}
                </div>
                <p className="text-xs text-neutral-500">{kb.description ?? "No description"}</p>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-xs text-neutral-500">
                <span>{kb.document_count} documents</span>
                <span>{kb.embedding_model}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New knowledge base">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="kb-name">Name</Label>
            <Input id="kb-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="kb-desc">Description</Label>
            <Textarea id="kb-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <Button type="submit" loading={createKb.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
