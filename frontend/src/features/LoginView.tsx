"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { LanguageSwitcher } from "@/components/AppShell";
import { Button } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { isLocale } from "@/i18n/core";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO = [
  ["admin@aivanta.demo", "login.role_admin"],
  ["finance@aivanta.demo", "login.role_finance"],
  ["analyst@aivanta.demo", "login.role_analyst"],
  ["viewer@aivanta.demo", "login.role_viewer"],
] as const;

export function LoginView() {
  const { t, setLocale } = useI18n();
  const { login, token, ready } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("admin@aivanta.demo");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && token) router.replace("/");
  }, [ready, token, router]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await login(email, password);
      if (isLocale(me.preferred_locale) && me.preferred_locale !== "en") setLocale(me.preferred_locale);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.code : "unknown");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <div className="flex justify-end p-4"><LanguageSwitcher /></div>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="grid w-full max-w-4xl gap-8 md:grid-cols-[1fr_1fr]">
          <div className="flex flex-col justify-center">
            <svg width="40" height="40" viewBox="0 0 32 32" aria-hidden>
              <rect width="32" height="32" rx="7" fill="#12233d" />
              <path d="M8 23 15.2 9h1.6L24 23h-3.3l-1.5-3.2h-6.4L11.3 23Zm5.6-5.8h4.8L16 12.1Z" fill="#fff" />
            </svg>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-ink">{t("login.title")}</h1>
            <p className="mt-2 text-ink-2">{t("login.subtitle")}</p>
            <ol className="mt-6 space-y-3 text-sm text-ink-2">
              {(["spend", "outcomes", "value"] as const).map((k) => (
                <li key={k}><span className="font-semibold text-ink">{t(`onboarding.step_${k}_title`)}</span></li>
              ))}
            </ol>
          </div>
          <form onSubmit={submit} className="rounded-lg border border-line bg-surface p-6" noValidate>
            <label className="block text-sm font-medium text-ink" htmlFor="email">{t("login.email")}</label>
            <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1 h-10 w-full rounded-md border border-line bg-surface px-3 text-sm" />
            <label className="mt-4 block text-sm font-medium text-ink" htmlFor="password">{t("login.password")}</label>
            <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1 h-10 w-full rounded-md border border-line bg-surface px-3 text-sm" />
            {error && <p role="alert" className="mt-3 text-sm text-critical-ink">{t(`error.${error}`)}</p>}
            <Button type="submit" variant="primary" className="mt-5 h-10 w-full" disabled={busy || !email || !password}>
              {busy ? t("login.submitting") : t("login.submit")}
            </Button>
            <div className="mt-6 border-t border-line pt-4">
              <p className="text-xs font-semibold text-ink">{t("login.demo_accounts")}</p>
              <ul className="mt-2 space-y-1">
                {DEMO.map(([mail, role]) => (
                  <li key={mail}>
                    <button type="button" onClick={() => setEmail(mail)} className="text-left text-xs text-ink-2 hover:text-ink">
                      <span className="font-mono text-accent">{mail}</span> — {t(role)}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-muted">{t("login.demo_hint")}</p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
