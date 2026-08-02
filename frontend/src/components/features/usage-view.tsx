"use client";

import { DollarSign, Gauge } from "lucide-react";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUsage } from "@/hooks/use-api";

const RANGE_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
] as const;

function formatCost(cost: string): string {
  const n = Number(cost);
  return `$${n < 0.01 && n > 0 ? n.toFixed(6) : n.toFixed(2)}`;
}

const compactNumber = new Intl.NumberFormat("en-US", { notation: "compact" });

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-xs shadow-md dark:border-neutral-800 dark:bg-neutral-900">
      <p className="mb-1 font-medium text-neutral-700 dark:text-neutral-300">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="flex items-center gap-1.5 text-neutral-600 dark:text-neutral-400">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          {entry.name}: <span className="font-medium text-neutral-900 dark:text-neutral-100">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

export function UsageView() {
  const [days, setDays] = useState<number>(30);
  const { data, isLoading } = useUsage(days);

  const stats = data
    ? [
        { label: "Prompt tokens", value: data.prompt_tokens.toLocaleString(), icon: Gauge },
        { label: "Completion tokens", value: data.completion_tokens.toLocaleString(), icon: Gauge },
        { label: "Total tokens", value: data.total_tokens.toLocaleString(), icon: Gauge },
        { label: "Total cost", value: formatCost(data.cost), icon: DollarSign },
      ]
    : [];

  return (
    <div>
      <PageHeader
        title="Usage"
        description="Token consumption and estimated cost for this tenant."
      />

      <Tabs defaultValue="30" className="mb-6">
        <TabsList>
          {RANGE_OPTIONS.map((opt) => (
            <TabsTrigger key={opt.value} value={String(opt.value)}>
              <span onClick={() => setDays(opt.value)}>{opt.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !data || data.total_tokens === 0 ? (
        <EmptyState
          icon={Gauge}
          title="No usage yet"
          description="Token usage and cost will show up here once this tenant has some chat activity."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map(({ label, value, icon: Icon }) => (
              <Card key={label}>
                <CardContent className="flex items-center justify-between pt-5">
                  <div>
                    <p className="text-xs text-neutral-500">{label}</p>
                    <p className="text-2xl font-semibold">{value}</p>
                  </div>
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft">
                    <Icon className="h-5 w-5 text-primary" />
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Daily token usage</CardTitle>
            </CardHeader>
            <CardContent>
              {data.daily.length === 0 ? (
                <p className="py-16 text-center text-sm text-neutral-500">No usage in this range.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={data.daily} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-neutral-200 dark:stroke-neutral-800" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="currentColor" className="text-neutral-400" />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11 }}
                      stroke="currentColor"
                      className="text-neutral-400"
                      tickFormatter={(value: number) => compactNumber.format(value)}
                      width={48}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="total_tokens"
                      name="Tokens"
                      stroke="var(--primary)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
