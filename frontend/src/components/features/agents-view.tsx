"use client";

import { Bot, Copy, RefreshCw, X } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useAgents, useCreateAgent, useModelProfiles, useRotateWidgetId, useUpdateAgent } from "@/hooks/use-api";
import type { Agent } from "@/lib/api/types";

const EMPTY_FORM = {
  name: "",
  description: "",
  system_prompt: "",
  llm_provider: "google",
  llm_model: "",
  model_profile_id: "",
  widget_enabled: false,
  widget_allowed_origins: [] as string[],
};

export function AgentsView() {
  const { data, isLoading } = useAgents();
  const { data: profiles } = useModelProfiles();
  const createAgent = useCreateAgent();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);

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
      setForm(EMPTY_FORM);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create agent.");
    }
  }

  const updateAgent = useUpdateAgent();

  function startEdit(agent: Agent) {
    setEditing(agent);
    setForm({
      name: agent.name,
      description: agent.description ?? "",
      system_prompt: agent.system_prompt,
      llm_provider: agent.llm_provider,
      llm_model: agent.llm_model,
      model_profile_id: agent.model_profile_id,
      widget_enabled: agent.widget_enabled,
      widget_allowed_origins: agent.widget_allowed_origins,
    });
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      await updateAgent.mutateAsync({
        id: editing.id,
        body: {
          name: form.name,
          description: form.description || null,
          system_prompt: form.system_prompt,
          llm_provider: form.llm_provider,
          llm_model: form.llm_model,
          model_profile_id: form.model_profile_id,
          widget_enabled: form.widget_enabled,
          widget_allowed_origins: form.widget_allowed_origins,
        },
      });
      toast.success("Agent updated.");
      setEditing(null);
      setForm(EMPTY_FORM);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update agent.");
    }
  }

  async function toggleActive(agent: Agent) {
    try {
      await updateAgent.mutateAsync({ id: agent.id, body: { is_active: !agent.is_active } });
      toast.success(agent.is_active ? "Agent deactivated." : "Agent reactivated.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update agent.");
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
              <TableHead />
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
                  <StatusBadge status={agent.is_active ? agent.status : "DISABLED"} />
                </TableCell>
                <TableCell className="flex justify-end gap-2">
                  <Button size="sm" variant="outline" onClick={() => startEdit(agent)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => toggleActive(agent)}>
                    {agent.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New agent" className="max-w-xl">
        <form onSubmit={handleCreate} className="grid gap-4">
          <AgentFormFields form={form} setForm={setForm} profiles={profiles?.model_profiles ?? []} />
          <Button type="submit" loading={createAgent.isPending}>
            Create
          </Button>
        </form>
      </Dialog>

      <Dialog
        open={!!editing}
        onClose={() => {
          setEditing(null);
          setForm(EMPTY_FORM);
        }}
        title={`Edit ${editing?.name ?? "agent"}`}
        className="max-w-xl"
      >
        <form onSubmit={handleUpdate} className="grid gap-4">
          <AgentFormFields form={form} setForm={setForm} profiles={profiles?.model_profiles ?? []} />
          {editing && <WidgetSection agent={editing} form={form} setForm={setForm} />}
          <Button type="submit" loading={updateAgent.isPending}>
            Save changes
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

/**
 * Public embeddable chat widget (docs/BUGS.md item 37). `agent` is the last-SAVED state (the
 * embed snippet and rotate action use its real widget_public_id); `form`/`setForm` hold the
 * draft enabled/origins that only take effect once "Save changes" is actually submitted — rotating
 * the id is the one action here that's immediate and separate from that save, since it's
 * destructive (invalidates the previous embed right away) and shouldn't wait on unrelated edits.
 */
function WidgetSection({
  agent,
  form,
  setForm,
}: {
  agent: Agent;
  form: typeof EMPTY_FORM;
  setForm: (form: typeof EMPTY_FORM) => void;
}) {
  const [originDraft, setOriginDraft] = useState("");
  const rotateWidgetId = useRotateWidgetId();

  function addOrigin() {
    const value = originDraft.trim();
    if (!value) return;
    if (!form.widget_allowed_origins.includes(value)) {
      setForm({ ...form, widget_allowed_origins: [...form.widget_allowed_origins, value] });
    }
    setOriginDraft("");
  }

  const apiBase = process.env.NEXT_PUBLIC_WIDGET_API_URL ?? "http://127.0.0.1:8088/api/v1";
  const snippet = agent.widget_public_id
    ? `<script src="${typeof window !== "undefined" ? window.location.origin : ""}/widget.js" data-agent="${agent.widget_public_id}" data-api="${apiBase}" async></script>`
    : null;

  return (
    <div className="grid gap-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex items-center justify-between">
        <div>
          <Label>Embeddable chat widget</Label>
          <p className="text-xs text-neutral-500">
            A chat bubble a customer can drop on their own website. Restricted tool access — no IAM
            lookups, no webhook tools, knowledge-base search only.
          </p>
        </div>
        <Switch
          checked={form.widget_enabled}
          onCheckedChange={(next) => setForm({ ...form, widget_enabled: next })}
          aria-label="Enable embeddable widget"
        />
      </div>

      {form.widget_enabled && (
        <>
          <div className="grid gap-1.5">
            <Label className="text-xs">Allowed origins</Label>
            <p className="text-xs text-neutral-500">
              Only these exact origins (scheme + host + port, no path) can use the widget. Empty = no
              one can, yet.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {form.widget_allowed_origins.map((origin) => (
                <Badge key={origin} variant="secondary" className="gap-1">
                  {origin}
                  <button
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        widget_allowed_origins: form.widget_allowed_origins.filter((o) => o !== origin),
                      })
                    }
                    aria-label={`Remove ${origin}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={originDraft}
                onChange={(e) => setOriginDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addOrigin();
                  }
                }}
                placeholder="https://www.example.com"
                className="text-sm"
              />
              <Button type="button" variant="outline" size="sm" onClick={addOrigin}>
                Add
              </Button>
            </div>
          </div>

          {agent.widget_public_id ? (
            <div className="grid gap-1.5">
              <Label className="text-xs">Embed snippet</Label>
              <div className="flex items-start gap-2">
                <code className="flex-1 overflow-x-auto rounded-md bg-neutral-100 px-2 py-1.5 text-xs dark:bg-neutral-900">
                  {snippet}
                </code>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  title="Copy snippet"
                  onClick={() => {
                    if (snippet) navigator.clipboard.writeText(snippet);
                    toast.success("Snippet copied.");
                  }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-fit"
                loading={rotateWidgetId.isPending}
                onClick={async () => {
                  if (!confirm("Rotate the widget id? The current embed snippet stops working immediately.")) return;
                  try {
                    await rotateWidgetId.mutateAsync(agent.id);
                    toast.success("Widget id rotated — update the embed snippet wherever it's used.");
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : "Could not rotate the widget id.");
                  }
                }}
              >
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                Rotate widget id
              </Button>
            </div>
          ) : (
            <p className="text-xs text-neutral-500">
              Save with the widget enabled to get its embed snippet.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function AgentFormFields({
  form,
  setForm,
  profiles,
}: {
  form: typeof EMPTY_FORM;
  setForm: (form: typeof EMPTY_FORM) => void;
  profiles: { id: string; name: string; provider: string; model: string }[];
}) {
  return (
    <>
      <div className="grid gap-1.5">
        <Label>Name</Label>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </div>
      <div className="grid gap-1.5">
        <Label>Description</Label>
        <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
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
          <Input value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })} required />
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
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.provider}/{p.model})
            </option>
          ))}
        </Select>
      </div>
    </>
  );
}
