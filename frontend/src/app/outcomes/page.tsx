"use client";

import { AppShell } from "@/components/AppShell";
import { OutcomesView } from "@/features/OutcomesView";

export default function Page() {
  return (
    <AppShell>
      <OutcomesView />
    </AppShell>
  );
}
