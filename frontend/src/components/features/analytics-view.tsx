"use client";

import { BarChart3, MessagesSquare } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAnalyticsSummary } from "@/hooks/use-api";

const RANGE_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
] as const;

// Reuses this app's own existing status tokens (globals.css) rather
// than inventing a new categorical palette — light/dark variants are
// already defined and used elsewhere (see dashboard-view.tsx).
const POSITIVE_COLOR = "var(--success)";
const NEGATIVE_COLOR = "var(--danger)";

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

export function AnalyticsView() {
  const [days, setDays] = useState<number>(30);
  const { data, isLoading } = useAnalyticsSummary(days);

  const feedbackByDay = useMemo(() => {
    if (!data) return [];
    const byDate = new Map<string, { date: string; THUMBS_UP: number; THUMBS_DOWN: number }>();
    for (const row of data.feedback_trends) {
      const entry = byDate.get(row.date) ?? { date: row.date, THUMBS_UP: 0, THUMBS_DOWN: 0 };
      entry[row.rating] = row.count;
      byDate.set(row.date, entry);
    }
    return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [data]);

  const hasData =
    !!data &&
    (data.queries_per_day.length > 0 ||
      data.feedback_trends.length > 0 ||
      data.top_failing_queries.length > 0);

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Usage trends for this tenant: queries per day, feedback over time, and the most-flagged responses."
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
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      ) : !hasData ? (
        <EmptyState
          icon={BarChart3}
          title="No activity yet"
          description="Once there's chat activity and feedback for this tenant, trends will show up here."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Queries per day</CardTitle>
              </CardHeader>
              <CardContent>
                {data!.queries_per_day.length === 0 ? (
                  <p className="py-16 text-center text-sm text-neutral-500">No queries in this range.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={data!.queries_per_day} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-neutral-200 dark:stroke-neutral-800" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="currentColor" className="text-neutral-400" />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="currentColor" className="text-neutral-400" width={40} />
                      <Tooltip content={<ChartTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="count"
                        name="Queries"
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

            <Card>
              <CardHeader>
                <CardTitle>Feedback trend</CardTitle>
              </CardHeader>
              <CardContent>
                {feedbackByDay.length === 0 ? (
                  <p className="py-16 text-center text-sm text-neutral-500">No feedback in this range.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={feedbackByDay} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-neutral-200 dark:stroke-neutral-800" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="currentColor" className="text-neutral-400" />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="currentColor" className="text-neutral-400" width={40} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="THUMBS_UP" name="Positive" fill={POSITIVE_COLOR} radius={[2, 2, 0, 0]} maxBarSize={28} />
                      <Bar dataKey="THUMBS_DOWN" name="Negative" fill={NEGATIVE_COLOR} radius={[2, 2, 0, 0]} maxBarSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Top failing queries</CardTitle>
            </CardHeader>
            <CardContent>
              {data!.top_failing_queries.length === 0 ? (
                <EmptyState icon={MessagesSquare} title="No negative feedback yet" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Response</TableHead>
                      <TableHead className="text-right">Times flagged</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data!.top_failing_queries.map((row) => (
                      <TableRow key={row.message_id}>
                        <TableCell className="max-w-lg truncate text-neutral-700 dark:text-neutral-300">
                          {row.content}
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge variant="destructive">{row.negative_count}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
