"use client";

import { AppShell } from "@/components/AppShell";
import { DataView } from "@/features/DataView";

export default function Page() {
  return (
    <AppShell>
      <DataView />
    </AppShell>
  );
}
