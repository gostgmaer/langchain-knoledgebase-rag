"use client";

import { Bot } from "lucide-react";
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
import { useAgents, useCreateAgent, useModelProfiles } from "@/hooks/use-api";

export function AgentsView() {
  const { data, isLoading } = useAgents();
  const { data: profiles } = useModelProfiles();
  const createAgent = useCreateAgent();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
    llm_provider: "google",
    llm_model: "",
    model_profile_id: "",
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.model_profile_id) {
      toast.error("Pick a model profile first.");
      return;
    }
    try {
      await createAgent.mutateAsync({
        name: form.name,
        description: form.description || null,
        system_prompt: form.system_prompt,
        llm_provider: form.llm_provider,
        llm_model: form.llm_model,
        model_profile_id: form.model_profile_id,
      });
      toast.success("Agent created.");
      setOpen(false);
      setForm({ name: "", description: "", system_prompt: "", llm_provider: "google", llm_model: "", model_profile_id: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create agent.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Reusable assistant configurations — system prompt, model, sampling parameters."
        actions={<Button onClick={() => setOpen(true)}>New agent</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.agents.length === 0 ? (
        <EmptyState icon={Bot} title="No agents yet" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Provider / Model</TableHead>
              <TableHead>Temperature</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.agents.map((agent) => (
              <TableRow key={agent.id}>
                <TableCell>
                  <div className="font-medium">{agent.name}</div>
                  <div className="text-xs text-neutral-400">{agent.description}</div>
                </TableCell>
                <TableCell className="text-neutral-500">
                  {agent.llm_provider} / {agent.llm_model}
                </TableCell>
                <TableCell className="text-neutral-500">{agent.temperature}</TableCell>
                <TableCell>
                  <StatusBadge status={agent.status} />
                  {agent.is_active && <Badge variant="success" className="ml-1">active</Badge>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New agent" className="max-w-xl">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="grid gap-1.5">
            <Label>Description</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>System prompt</Label>
            <Textarea
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              required
              className="min-h-24"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label>LLM provider</Label>
              <Input
                value={form.llm_provider}
                onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
                required
              />
            </div>
            <div className="grid gap-1.5">
              <Label>LLM model</Label>
              <Input
                value={form.llm_model}
                onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Model profile</Label>
            <Select
              value={form.model_profile_id}
              onChange={(e) => setForm({ ...form, model_profile_id: e.target.value })}
              required
            >
              <option value="">Select a model profile…</option>
              {profiles?.model_profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.provider}/{p.model})
                </option>
              ))}
            </Select>
          </div>
          <Button type="submit" loading={createAgent.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
