"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { UseCaseView } from "@/features/OutcomesView";

export default function Page() {
  const params = useParams<{ key: string }>();
  return (
    <AppShell>
      <UseCaseView id={params.key} />
    </AppShell>
  );
}
