"use client";

import { AppShell } from "@/components/AppShell";
import { CostsView } from "@/features/CostsView";

export default function Page() {
  return (
    <AppShell>
      <CostsView />
    </AppShell>
  );
}
