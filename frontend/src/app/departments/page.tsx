"use client";

import { AppShell } from "@/components/AppShell";
import { DepartmentsView } from "@/features/DepartmentsView";

export default function Page() {
  return (
    <AppShell>
      <DepartmentsView />
    </AppShell>
  );
}
