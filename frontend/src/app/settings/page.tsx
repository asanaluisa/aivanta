"use client";

import { AppShell } from "@/components/AppShell";
import { SettingsView } from "@/features/SettingsView";

export default function Page() {
  return (
    <AppShell>
      <SettingsView />
    </AppShell>
  );
}
