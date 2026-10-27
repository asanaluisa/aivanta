"use client";

import type { ReactNode } from "react";

import { I18nProvider } from "@/i18n/I18nProvider";
import { AuthProvider } from "@/lib/auth";
import { FiltersProvider } from "@/lib/filtersContext";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <AuthProvider>
        <FiltersProvider>{children}</FiltersProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
