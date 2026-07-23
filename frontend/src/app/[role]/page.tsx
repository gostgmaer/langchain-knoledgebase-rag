"use client";

import { useRouter } from "next/navigation";
import { use, useEffect } from "react";

import { DashboardView } from "@/components/features/dashboard-view";

export default function RoleDashboardPage({ params }: { params: Promise<{ role: string }> }) {
  const { role } = use(params);
  const router = useRouter();

  useEffect(() => {
    if (role === "customer") router.replace("/customer/chat");
  }, [role, router]);

  if (role === "customer") return null;

  return <DashboardView basePath={`/${role}`} />;
}
