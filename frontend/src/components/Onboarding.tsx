"use client";

import { useEffect, useState } from "react";

import { useI18n } from "@/i18n/I18nProvider";

import { BasisBadge, Button } from "./ui";

const KEY = "aivanta.onboarded";

export function Onboarding() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    try {
      setOpen(window.localStorage.getItem(KEY) !== "1");
    } catch {
      setOpen(false);
    }
  }, []);
  if (!open) return null;
  const dismiss = () => {
    try {
      window.localStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
  };
  return (
    <section aria-labelledby="onboarding-title" className="mb-6 rounded-lg border border-brand/20 bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="onboarding-title" className="text-base font-semibold text-ink">{t("onboarding.title")}</h2>
          <p className="mt-1 text-sm text-ink-2">{t("onboarding.intro")}</p>
        </div>
        <Button variant="primary" onClick={dismiss}>{t("onboarding.dismiss")}</Button>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {(["spend", "outcomes", "value"] as const).map((k) => (
          <div key={k}>
            <h3 className="text-sm font-semibold text-ink">{t(`onboarding.step_${k}_title`)}</h3>
            <p className="mt-1 text-xs leading-relaxed text-ink-2">{t(`onboarding.step_${k}_body`)}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <p className="text-xs font-semibold text-ink">{t("onboarding.badges_title")}</p>
        <ul className="mt-2 grid gap-2 text-xs text-ink-2 md:grid-cols-3">
          {(["measured", "evidence_backed", "estimated"] as const).map((b) => (
            <li key={b} className="flex items-start gap-2"><BasisBadge basis={b} /><span>{t(`basis.${b}_help`)}</span></li>
          ))}
        </ul>
      </div>
    </section>
  );
}
