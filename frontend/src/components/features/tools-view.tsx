"use client";

import { Wrench } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
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
import { useCreateTool, useTools } from "@/hooks/use-api";
import { TOOL_CATEGORIES, type ToolCategory } from "@/lib/api/types";

export function ToolsView() {
  const { data, isLoading } = useTools();
  const createTool = useCreateTool();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ToolCategory>("UTILITY");
  const [provider, setProvider] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createTool.mutateAsync({ name, description: description || null, category, provider });
      toast.success("Tool definition created.");
      setOpen(false);
      setName("");
      setDescription("");
      setProvider("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create tool definition.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Tool Definitions"
        description="DB-backed tool metadata — distinct from the in-process registry that actually powers chat tool-calling."
        actions={<Button onClick={() => setOpen(true)}>New tool definition</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.tools.length === 0 ? (
        <EmptyState icon={Wrench} title="No tool definitions yet" />
      ) : (
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
            {data.tools.map((t) => (
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
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New tool definition">
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
          <Button type="submit" loading={createTool.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
