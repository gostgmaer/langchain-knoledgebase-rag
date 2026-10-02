"use client";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ConfigField } from "@/lib/api/types";

type Values = Record<string, unknown>;

/**
 * Renders a connector's settings straight from its schema, so a new connector needs no frontend work.
 * `string_list` is one value per line; `secret` is a write-only password field that never shows a stored value.
 */
export function ConfigForm({
  fields,
  values,
  onChange,
  idPrefix,
}: {
  fields: ConfigField[];
  values: Values;
  onChange: (next: Values) => void;
  idPrefix: string;
}) {
  const set = (key: string, value: unknown) => {
    const next = { ...values };
    if (value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) delete next[key];
    else next[key] = value;
    onChange(next);
  };

  return (
    <div className="grid gap-4">
      {fields.map((field) => {
        const id = `${idPrefix}-${field.key}`;
        const value = values[field.key];
        const fallback = field.default;
        return (
          <div key={field.key} className="grid gap-1.5">
            {field.type === "boolean" ? (
              <div className="flex items-start justify-between gap-4">
                <label htmlFor={id} className="grid gap-0.5 text-sm">
                  <span className="font-medium">{field.label}</span>
                  {field.help && <span className="text-xs text-neutral-500">{field.help}</span>}
                </label>
                <Switch
                  aria-label={field.label}
                  checked={typeof value === "boolean" ? value : Boolean(fallback)}
                  onCheckedChange={(v) => set(field.key, v)}
                />
              </div>
            ) : (
              <>
                <label htmlFor={id} className="text-sm font-medium">
                  {field.label}
                  {field.required && <span className="ml-0.5 text-red-600">*</span>}
                </label>
                {field.type === "string_list" ? (
                  <Textarea
                    id={id}
                    rows={3}
                    placeholder={field.placeholder ?? "One per line"}
                    value={Array.isArray(value) ? (value as string[]).join("\n") : ""}
                    onChange={(e) =>
                      set(
                        field.key,
                        e.target.value
                          .split("\n")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                ) : field.type === "select" ? (
                  <Select id={id} value={typeof value === "string" ? value : String(fallback ?? "")} onChange={(e) => set(field.key, e.target.value)}>
                    {field.options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </Select>
                ) : field.type === "text" ? (
                  <Textarea id={id} rows={3} value={typeof value === "string" ? value : ""} onChange={(e) => set(field.key, e.target.value)} />
                ) : field.type === "number" ? (
                  <Input
                    id={id}
                    type="number"
                    min={field.minimum ?? undefined}
                    max={field.maximum ?? undefined}
                    step="any"
                    placeholder={fallback !== null && fallback !== undefined ? String(fallback) : undefined}
                    value={typeof value === "number" ? value : ""}
                    onChange={(e) => set(field.key, e.target.value === "" ? undefined : Number(e.target.value))}
                  />
                ) : field.type === "secret" ? (
                  <Input
                    id={id}
                    name={`${id}-${idPrefix}-secret`}
                    type="password"
                    autoComplete="new-password"
                    placeholder={field.placeholder ?? "Stored encrypted; never shown again"}
                    value={typeof value === "string" ? value : ""}
                    onChange={(e) => set(field.key, e.target.value)}
                  />
                ) : (
                  <Input
                    id={id}
                    type={field.type === "url" ? "url" : "text"}
                    autoComplete="off"
                    placeholder={field.placeholder ?? (fallback !== null && fallback !== undefined ? String(fallback) : undefined)}
                    value={typeof value === "string" ? value : ""}
                    onChange={(e) => set(field.key, e.target.value)}
                  />
                )}
                {field.help && <p className="text-xs text-neutral-500">{field.help}</p>}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
