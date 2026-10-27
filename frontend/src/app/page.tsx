"use client";

import { AppShell } from "@/components/AppShell";
import { DashboardView } from "@/features/DashboardView";

export default function Page() {
  return (
    <AppShell>
      <DashboardView />
    </AppShell>
  );
}
