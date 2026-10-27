"use client";

import { AppShell } from "@/components/AppShell";
import { RecommendationsView } from "@/features/RecommendationsView";

export default function Page() {
  return (
    <AppShell>
      <RecommendationsView />
    </AppShell>
  );
}
