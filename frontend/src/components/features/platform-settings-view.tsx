"use client";

import { Cog, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { usePlatformSettings, useSavePlatformSettings } from "@/hooks/use-api";
import type { PlatformSettingItem, PlatformSettingsResponse } from "@/lib/api/types";

/** Operational knobs an admin can change without a redeploy — rate limits, CORS origins,
 * retention windows. Secrets and security-boundary settings (API keys, AUTH_REQUIRED, admin
 * roles) are never listed here; those stay .env-only (docs/BUGS.md item 38). */
export function PlatformSettingsView() {
  const { data, isLoading, isError, error, refetch } = usePlatformSettings();

  return (
    <div>
      <PageHeader
        title="Platform settings"
        description="Operational knobs, platform-wide — not per-tenant. A field left at its default (shown as the placeholder/hint) stays on the .env value. Changes apply within about 30 seconds, no restart needed."
      />
      {isError ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : isLoading || !data ? (
        <Skeleton className="h-96 w-full" />
      ) : data.settings.length === 0 ? (
        <EmptyState icon={Cog} title="No settings" />
      ) : (
        // Keyed by the saved values so the form re-seeds after a save without an effect.
        <SettingsForm key={JSON.stringify(data.settings.map((s) => s.value))} data={data} />
      )}
    </div>
  );
}

type DraftValue = number | boolean | string[] | null;

function SettingsForm({ data }: { data: PlatformSettingsResponse }) {
  const save = useSavePlatformSettings();
  const [draft, setDraft] = useState<Record<string, DraftValue>>(() =>
    Object.fromEntries(data.settings.map((item) => [item.key, item.is_overridden ? item.value : null]))
  );

  function setValue(key: string, value: DraftValue) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await save.mutateAsync({ values: draft });
      toast.success("Platform settings saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the settings.");
    }
  }

  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Operational settings</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 text-sm">
          {data.settings.map((item) => (
            <SettingField key={item.key} item={item} value={draft[item.key] ?? null} onChange={(v) => setValue(item.key, v)} />
          ))}
          <div className="flex gap-2">
            <Button type="submit" loading={save.isPending}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}

function SettingField({
  item,
  value,
  onChange,
}: {
  item: PlatformSettingItem;
  value: DraftValue;
  onChange: (value: DraftValue) => void;
}) {
  const isDefault = value === null;

  return (
    <div className="grid gap-1.5 border-b border-neutral-100 pb-5 last:border-0 last:pb-0 dark:border-neutral-800">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{item.label}</span>
        <div className="flex items-center gap-2">
          {!isDefault && <Badge variant="outline">overridden</Badge>}
          {!isDefault && (
            <Button type="button" variant="ghost" size="icon" title="Reset to .env default" onClick={() => onChange(null)}>
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
      {item.help && <span className="text-xs text-neutral-500">{item.help}</span>}

      {item.kind === "int" && (
        <Input
          type="number"
          min={item.minimum ?? undefined}
          max={item.maximum ?? undefined}
          value={isDefault ? "" : String(value)}
          placeholder={`${item.env_default} (.env default)`}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          aria-label={item.label}
        />
      )}

      {item.kind === "bool" && (
        <div className="flex items-center gap-2">
          {isDefault && <Badge variant="outline">default ({String(item.env_default)})</Badge>}
          <Switch
            checked={isDefault ? Boolean(item.env_default) : Boolean(value)}
            onCheckedChange={(next) => onChange(next)}
            aria-label={item.label}
          />
        </div>
      )}

      {item.kind === "string_list" && (
        <StringListField
          value={isDefault ? null : (value as string[] | null)}
          envDefault={item.env_default as string[]}
          onChange={onChange}
        />
      )}
    </div>
  );
}

function StringListField({
  value,
  envDefault,
  onChange,
}: {
  value: string[] | null;
  envDefault: string[];
  onChange: (value: string[]) => void;
}) {
  const [draftEntry, setDraftEntry] = useState("");
  const items = value ?? envDefault;
  const usingDefault = value === null;

  function add() {
    const entry = draftEntry.trim();
    if (!entry) return;
    const base = usingDefault ? envDefault : items;
    if (!base.includes(entry)) onChange([...base, entry]);
    setDraftEntry("");
  }

  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap gap-1.5">
        {items.map((entry) => (
          <Badge key={entry} variant="secondary" className="gap-1">
            {entry}
            <button
              type="button"
              onClick={() => onChange(items.filter((v) => v !== entry))}
              aria-label={`Remove ${entry}`}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          value={draftEntry}
          onChange={(e) => setDraftEntry(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder="https://example.com"
          className="text-sm"
        />
        <Button type="button" variant="outline" size="sm" onClick={add}>
          Add
        </Button>
      </div>
    </div>
  );
}
