"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { ConfigForm } from "@/components/sources/config-form";
import { SourceIcon } from "@/components/sources/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useCreateSource, useSourceAction, useSourceTypes, useTestUnsavedSource } from "@/hooks/use-api";
import type { ConfigField, ConnectionTest, ConnectorType, KnowledgeSource, SourcePreview, SyncMode } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STEPS = ["Select source", "Connect", "Test", "Select content", "Permissions", "Schedule", "Review", "Start"] as const;

const isFilled = (v: unknown) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0);

export function SourceWizard() {
  const { role } = useParams<{ role: string }>();
  const router = useRouter();
  const types = useSourceTypes();
  const create = useCreateSource();
  const testSource = useTestUnsavedSource();

  const [step, setStep] = useState(0);
  const [type, setType] = useState<ConnectorType | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [credentials, setCredentials] = useState<Record<string, unknown>>({});
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [syncMode, setSyncMode] = useState<SyncMode>("manual");
  const [interval, setInterval] = useState<number>(60);
  const [test, setTest] = useState<ConnectionTest | null>(null);
  const [created, setCreated] = useState<KnowledgeSource | null>(null);
  const [preview, setPreview] = useState<SourcePreview | null>(null);

  if (types.isError) return <QueryError error={types.error} onRetry={() => void types.refetch()} />;
  if (types.isLoading || !types.data) return <Skeleton className="h-64 w-full" />;

  const common = types.data.common_fields;
  const commonKeys = new Set(common.map((f) => f.key));
  const schema: ConfigField[] = type ? type.config_schema : [];
  // What must be known to connect at all: the connection group and anything required.
  const connectFields = schema.filter((f) => f.group === "connection" || f.required);
  const connectKeys = new Set(connectFields.map((f) => f.key));
  const contentFields = schema.filter((f) => !connectKeys.has(f.key) && f.group !== "permissions");
  const permissionFields = [...schema.filter((f) => !connectKeys.has(f.key) && f.group === "permissions"), ...common.filter((f) => f.group === "permissions")];
  const advancedCommon = common.filter((f) => f.group !== "permissions");
  const secretFields = type?.credential_fields ?? [];
  const needsCredentials = !!type && type.credential_kind !== "none";

  const specific = Object.fromEntries(Object.entries(config).filter(([k]) => !commonKeys.has(k)));
  const credentialsReady = !needsCredentials || (type!.credential_kind === "oauth_client" ? isFilled(credentials.access_token) || ["tenant_id", "client_id", "client_secret"].every((k) => isFilled(credentials[k])) : secretFields.filter((f) => f.required).every((f) => isFilled(credentials[f.key])));
  const requiredFilled = connectFields.filter((f) => f.required).every((f) => isFilled(config[f.key]));

  function chooseType(next: ConnectorType) {
    setType(next);
    setConfig({});
    setCredentials({});
    setTest(null);
    setName(next.display_name);
  }

  async function runTest() {
    if (!type) return;
    setTest(null);
    try {
      const result = await testSource.mutateAsync({ type: type.type, configuration: config, credentials: needsCredentials ? credentials : null });
      setTest(result);
    } catch (err) {
      setTest({ ok: false, message: err instanceof Error ? err.message : "The test failed.", authenticated: null, details: {}, validation: null });
    }
  }

  async function createSource() {
    if (!type) return;
    try {
      const source = await create.mutateAsync({
        name: name.trim(),
        type: type.type,
        description: description.trim() || null,
        configuration: config,
        credentials: needsCredentials ? credentials : null,
        sync_mode: syncMode,
        sync_interval_minutes: syncMode === "scheduled" ? interval : null,
      });
      setCreated(source);
      setStep(7);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create the source.");
    }
  }

  const canNext = [
    !!type,
    name.trim().length > 0 && credentialsReady && requiredFilled,
    !!test?.ok,
    true,
    true,
    syncMode !== "scheduled" || !!interval,
    true,
  ][step];

  return (
    <div>
      <PageHeader
        title="Add a knowledge source"
        description="Nothing is ingested until you confirm on the last step."
        actions={
          <Link href={`/${role}/knowledge-sources`}>
            <Button variant="outline" size="sm">Cancel</Button>
          </Link>
        }
      />

      <ol className="mb-6 flex flex-wrap gap-2 text-xs" aria-label="Progress">
        {STEPS.map((label, i) => (
          <li
            key={label}
            aria-current={i === step ? "step" : undefined}
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-3 py-1",
              i === step ? "border-neutral-900 font-medium dark:border-neutral-100" : "border-neutral-200 text-neutral-500 dark:border-neutral-800",
            )}
          >
            {i < step ? <Check className="h-3 w-3" /> : <span>{i + 1}</span>}
            {label}
          </li>
        ))}
      </ol>

      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5">
          {step === 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {types.data.types.map((t) => (
                <button
                  key={t.type}
                  type="button"
                  disabled={!t.available}
                  onClick={() => chooseType(t)}
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                    type?.type === t.type ? "border-neutral-900 bg-neutral-50 dark:border-neutral-100 dark:bg-neutral-900" : "border-neutral-200 hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900",
                  )}
                >
                  <SourceIcon icon={t.icon} className="mt-0.5 h-5 w-5 shrink-0" />
                  <span className="grid gap-0.5">
                    <span className="flex items-center gap-2 text-sm font-medium">
                      {t.display_name}
                      {!t.available && <Badge variant="outline">Coming soon</Badge>}
                    </span>
                    <span className="text-xs text-neutral-500">{t.description}</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {step === 1 && type && (
            <>
              <div className="grid gap-1.5">
                <label htmlFor="src-name" className="text-sm font-medium">Name</label>
                <Input id="src-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <label htmlFor="src-desc" className="text-sm font-medium">Description (optional)</label>
                <Textarea id="src-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
              </div>
              {connectFields.length > 0 && <ConfigForm idPrefix="wiz-connect" fields={connectFields} values={config} onChange={setConfig} />}
              {needsCredentials ? (
                <div className="grid gap-2 rounded-md border border-neutral-200 p-3 dark:border-neutral-800">
                  <p className="text-sm font-medium">Credentials</p>
                  <p className="text-xs text-neutral-500">Encrypted on save and never shown again. Use a read-only account or app registration.</p>
                  <ConfigForm idPrefix="wiz-cred" fields={secretFields} values={credentials} onChange={setCredentials} />
                </div>
              ) : (
                <p className="text-xs text-neutral-500">This source needs no credentials.</p>
              )}
              {type.notes && <p className="text-xs text-neutral-500">{type.notes}</p>}
            </>
          )}

          {step === 2 && type && (
            <>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                Checks the address and credentials without saving anything or reading your content.
              </p>
              <div>
                <Button onClick={runTest} loading={testSource.isPending}>Test connection</Button>
              </div>
              {test && (
                <div className={cn("rounded-md border p-3 text-sm", test.ok ? "border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30" : "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/30")} role="status">
                  <p className="font-medium">{test.ok ? "Connection works" : "Connection failed"}</p>
                  <p className="text-xs">{test.message}</p>
                  {test.validation && test.validation.errors.length > 0 && (
                    <ul className="mt-1 list-disc pl-4 text-xs">
                      {test.validation.errors.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </>
          )}

          {step === 3 && type && (
            <>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">Limit what is ingested. Leave a field empty to include everything the connector supports.</p>
              {contentFields.length > 0 ? <ConfigForm idPrefix="wiz-content" fields={contentFields} values={config} onChange={setConfig} /> : <p className="text-xs text-neutral-500">No further selection options for this source.</p>}
              <ConfigForm idPrefix="wiz-adv" fields={advancedCommon} values={config} onChange={setConfig} />
            </>
          )}

          {step === 4 && type && (
            <>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                Who can retrieve these documents in answers.
                {type.supports_permissions && " This source has its own permissions; principals need an identity mapping (Permissions tab after the first sync) or the document stays administrator-only."}
              </p>
              <ConfigForm idPrefix="wiz-perm" fields={permissionFields} values={config} onChange={setConfig} />
            </>
          )}

          {step === 5 && (
            <>
              <div className="grid gap-1.5">
                <label htmlFor="sync-mode" className="text-sm font-medium">Synchronisation</label>
                <Select id="sync-mode" value={syncMode} onChange={(e) => setSyncMode(e.target.value as SyncMode)}>
                  <option value="manual">Manual (only when I press Sync)</option>
                  <option value="scheduled">On a schedule</option>
                  <option value="webhook">When the source notifies us (webhook)</option>
                </Select>
              </div>
              {syncMode === "scheduled" && (
                <div className="grid gap-1.5">
                  <label htmlFor="sync-interval" className="text-sm font-medium">Repeat</label>
                  <Select id="sync-interval" value={interval} onChange={(e) => setInterval(Number(e.target.value))}>
                    {types.data.sync_intervals.map((i) => (
                      <option key={i.minutes} value={i.minutes}>{i.label}</option>
                    ))}
                  </Select>
                </div>
              )}
              {syncMode === "webhook" && <p className="text-xs text-neutral-500">A secret is generated when the source is created and shown once.</p>}
            </>
          )}

          {step === 6 && type && (
            <dl className="grid gap-2 text-sm">
              {[
                ["Source", `${type.display_name} — ${name}`],
                ["Credentials", needsCredentials ? "Provided (encrypted on save)" : "None"],
                ["Connection test", test?.ok ? "Passed" : "Not passed"],
                ["Schedule", syncMode === "scheduled" ? types.data.sync_intervals.find((i) => i.minutes === interval)?.label ?? "" : syncMode],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-neutral-100 pb-2 dark:border-neutral-900">
                  <dt className="text-neutral-500">{k}</dt>
                  <dd className="text-right">{v}</dd>
                </div>
              ))}
              <div>
                <dt className="mb-1 text-neutral-500">Settings</dt>
                <dd>
                  <pre className="max-h-56 overflow-auto rounded-md bg-neutral-100 p-3 text-xs dark:bg-neutral-900">{JSON.stringify({ ...specific, ...Object.fromEntries(Object.entries(config).filter(([k]) => commonKeys.has(k))) }, null, 2)}</pre>
                </dd>
              </div>
              <p className="text-xs text-neutral-500">Creating the source saves it paused. Nothing is fetched or indexed until you start the sync on the next step.</p>
            </dl>
          )}

          {step === 7 && created && (
            <FinalStep
              source={created}
              role={role}
              preview={preview}
              onPreview={setPreview}
              onDone={(id) => router.push(`/${role}/knowledge-sources/${id}`)}
            />
          )}

          {step < 7 && (
            <div className="flex justify-between border-t border-neutral-100 pt-4 dark:border-neutral-900">
              <Button variant="outline" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
              {step === 6 ? (
                <Button onClick={createSource} loading={create.isPending}>Create source</Button>
              ) : (
                <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Next</Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FinalStep({
  source,
  preview,
  onPreview,
  onDone,
}: {
  source: KnowledgeSource;
  role: string;
  preview: SourcePreview | null;
  onPreview: (p: SourcePreview) => void;
  onDone: (id: string) => void;
}) {
  const action = useSourceAction(source.id);
  const [secretSeen, setSecretSeen] = useState(false);

  async function loadPreview() {
    try {
      onPreview(await action.preview.mutateAsync(20));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not preview the source.");
    }
  }

  async function start() {
    try {
      await action.sync.mutateAsync(true);
      toast.success("Sync started.");
      onDone(source.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start the sync.");
    }
  }

  return (
    <div className="grid gap-4">
      <p className="text-sm">
        <span className="font-medium">{source.name}</span> is saved and paused. Preview what a sync would ingest, then start it.
      </p>

      {source.webhook_secret && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs dark:border-amber-900 dark:bg-amber-950/30">
          <p className="font-medium">Webhook secret (shown once)</p>
          <code className="break-all">{source.webhook_secret}</code>
          <p className="mt-1">POST to <code>/api/v1/webhooks/sources/{source.id}</code> with header <code>X-Webhook-Secret</code>.</p>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={secretSeen} onChange={(e) => setSecretSeen(e.target.checked)} /> I have saved it
          </label>
        </div>
      )}

      <div>
        <Button variant="outline" onClick={loadPreview} loading={action.preview.isPending}>Preview what will be ingested</Button>
      </div>

      {preview && (
        <div className="rounded-md border border-neutral-200 dark:border-neutral-800">
          <p className="border-b border-neutral-200 px-3 py-2 text-xs text-neutral-500 dark:border-neutral-800">
            {preview.items.length} item{preview.items.length === 1 ? "" : "s"}{preview.truncated ? " (first 20 shown)" : ""}
          </p>
          <ul className="max-h-64 divide-y divide-neutral-100 overflow-auto text-sm dark:divide-neutral-900">
            {preview.items.map((item) => (
              <li key={item.external_id} className="px-3 py-2">
                <p className="font-medium">{item.title}</p>
                {item.url && <p className="truncate text-xs text-neutral-500">{item.url}</p>}
              </li>
            ))}
            {preview.items.length === 0 && <li className="px-3 py-2 text-xs text-neutral-500">Nothing matched. Check the selection and filters.</li>}
          </ul>
          {preview.warnings.length > 0 && <p className="border-t border-neutral-200 px-3 py-2 text-xs text-amber-700 dark:border-neutral-800">{preview.warnings.slice(0, 3).join(" · ")}</p>}
        </div>
      )}

      <div className="flex justify-between border-t border-neutral-100 pt-4 dark:border-neutral-900">
        <Button variant="outline" disabled={!!source.webhook_secret && !secretSeen} onClick={() => onDone(source.id)}>Finish without syncing</Button>
        <Button onClick={start} loading={action.sync.isPending} disabled={!!source.webhook_secret && !secretSeen}>Start sync</Button>
      </div>
    </div>
  );
}
