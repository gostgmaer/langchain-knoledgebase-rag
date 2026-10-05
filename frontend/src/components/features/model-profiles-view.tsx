"use client";

import { Cpu } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateModelProfile, useModelProfiles, useUpdateModelProfile } from "@/hooks/use-api";
import type { ModelProfile } from "@/lib/api/types";

const EMPTY_FORM = { name: "", provider: "GOOGLE", model: "", context_window: "32000" };

export function ModelProfilesView() {
  const { data, isLoading } = useModelProfiles();
  const createProfile = useCreateModelProfile();
  const updateProfile = useUpdateModelProfile();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ModelProfile | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createProfile.mutateAsync({
        name: form.name,
        provider: form.provider,
        model: form.model,
        context_window: Number(form.context_window),
      });
      toast.success("Model profile created.");
      setOpen(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create model profile.");
    }
  }

  function startEdit(profile: ModelProfile) {
    setEditing(profile);
    setForm({
      name: profile.name,
      provider: profile.provider,
      model: profile.model,
      context_window: String(profile.context_window),
    });
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      await updateProfile.mutateAsync({
        id: editing.id,
        body: {
          name: form.name,
          provider: form.provider,
          model: form.model,
          context_window: Number(form.context_window),
        },
      });
      toast.success("Model profile updated.");
      setEditing(null);
      setForm(EMPTY_FORM);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update model profile.");
    }
  }

  async function toggleDisabled(profile: ModelProfile) {
    try {
      await updateProfile.mutateAsync({
        id: profile.id,
        body: { status: profile.status === "DISABLED" ? "ACTIVE" : "DISABLED" },
      });
      toast.success(profile.status === "DISABLED" ? "Model profile reactivated." : "Model profile disabled.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update model profile.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Model Profiles"
        description="Shared, global LLM configurations — not scoped to any one tenant."
        actions={<Button onClick={() => setOpen(true)}>New model profile</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.model_profiles.length === 0 ? (
        <EmptyState icon={Cpu} title="No model profiles yet" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Provider / Model</TableHead>
              <TableHead>Context window</TableHead>
              <TableHead>Capabilities</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.model_profiles.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="font-medium">{p.name}</div>
                  {p.is_default && <Badge variant="secondary">default</Badge>}
                </TableCell>
                <TableCell className="text-neutral-500">
                  {p.provider} / {p.model}
                </TableCell>
                <TableCell className="text-neutral-500">{p.context_window.toLocaleString()}</TableCell>
                <TableCell className="space-x-1">
                  {p.supports_streaming && <Badge variant="outline">streaming</Badge>}
                  {p.supports_tools && <Badge variant="outline">tools</Badge>}
                  {p.supports_embeddings && <Badge variant="outline">embeddings</Badge>}
                </TableCell>
                <TableCell>
                  <StatusBadge status={p.status} />
                </TableCell>
                <TableCell className="flex justify-end gap-2">
                  <Button size="sm" variant="outline" onClick={() => startEdit(p)}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => toggleDisabled(p)}>
                    {p.status === "DISABLED" ? "Enable" : "Disable"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New model profile">
        <form onSubmit={handleCreate} className="grid gap-4">
          <ModelProfileFormFields form={form} setForm={setForm} />
          <Button type="submit" loading={createProfile.isPending}>
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
        title={`Edit ${editing?.name ?? "model profile"}`}
      >
        <form onSubmit={handleUpdate} className="grid gap-4">
          <ModelProfileFormFields form={form} setForm={setForm} />
          <Button type="submit" loading={updateProfile.isPending}>
            Save changes
          </Button>
        </form>
      </Dialog>
    </div>
  );
}

function ModelProfileFormFields({
  form,
  setForm,
}: {
  form: typeof EMPTY_FORM;
  setForm: (form: typeof EMPTY_FORM) => void;
}) {
  return (
    <>
      <div className="grid gap-1.5">
        <Label>Name</Label>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </div>
      <div className="grid gap-1.5">
        <Label>Provider</Label>
        <Input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} required />
      </div>
      <div className="grid gap-1.5">
        <Label>Model</Label>
        <Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} required />
      </div>
      <div className="grid gap-1.5">
        <Label>Context window</Label>
        <Input
          type="number"
          value={form.context_window}
          onChange={(e) => setForm({ ...form, context_window: e.target.value })}
          required
        />
      </div>
    </>
  );
}
