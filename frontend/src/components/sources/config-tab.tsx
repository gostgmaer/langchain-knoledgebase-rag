"use client";

import { useState } from "react";
import { toast } from "sonner";

import { ConfigForm } from "@/components/sources/config-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateSource } from "@/hooks/use-api";
import type { ConnectorType, ConnectorTypes, KnowledgeSource, SyncMode } from "@/lib/api/types";

/** Edit name, settings (content selection, filters, permission behaviour) and the schedule. Credentials live on Overview. */
export function ConfigTab({ source, type, catalogue }: { source: KnowledgeSource; type: ConnectorType | undefined; catalogue: ConnectorTypes | undefined }) {
  const update = useUpdateSource(source.id);
  const [name, setName] = useState(source.name);
  const [description, setDescription] = useState(source.description ?? "");
  const [config, setConfig] = useState<Record<string, unknown>>(source.configuration);
  const [syncMode, setSyncMode] = useState<SyncMode>(source.sync_mode);
  const [interval, setInterval] = useState<number>(source.sync_interval_minutes ?? 60);

  if (!type || !catalogue) return null;
  const fields = [...type.config_schema, ...catalogue.common_fields];

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      const saved = await update.mutateAsync({
        name: name.trim(),
        description: description.trim() || null,
        configuration: config,
        sync_mode: syncMode,
        sync_interval_minutes: syncMode === "scheduled" ? interval : null,
      });
      if (saved.webhook_secret) {
        toast.message("Webhook secret (shown once)", { description: saved.webhook_secret, duration: 30000 });
      }
      toast.success("Saved. Changes apply on the next sync.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save.");
    }
  }

  return (
    <form onSubmit={save} className="grid max-w-3xl gap-4">
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-1.5">
            <label htmlFor="cfg-name" className="text-sm font-medium">Name</label>
            <Input id="cfg-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="cfg-desc" className="text-sm font-medium">Description</label>
            <Textarea id="cfg-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="cfg-mode" className="text-sm font-medium">Synchronisation</label>
            <Select id="cfg-mode" value={syncMode} onChange={(e) => setSyncMode(e.target.value as SyncMode)}>
              <option value="manual">Manual</option>
              <option value="scheduled">On a schedule</option>
              <option value="webhook">Webhook</option>
            </Select>
          </div>
          {syncMode === "scheduled" && (
            <div className="grid gap-1.5">
              <label htmlFor="cfg-interval" className="text-sm font-medium">Repeat</label>
              <Select id="cfg-interval" value={interval} onChange={(e) => setInterval(Number(e.target.value))}>
                {catalogue.sync_intervals.map((i) => (
                  <option key={i.minutes} value={i.minutes}>{i.label}</option>
                ))}
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{type.display_name} settings</CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigForm idPrefix="cfg" fields={fields} values={config} onChange={setConfig} />
        </CardContent>
      </Card>

      <div>
        <Button type="submit" loading={update.isPending} disabled={!name.trim()}>Save changes</Button>
      </div>
    </form>
  );
}
