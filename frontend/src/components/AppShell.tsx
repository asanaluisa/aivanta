"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { useI18n } from "@/i18n/I18nProvider";
import { LOCALES, type Locale } from "@/i18n/core";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me, Meta } from "@/lib/types";
import { useApi } from "@/lib/useApi";

import { FilterBar } from "./FilterBar";
import { Onboarding } from "./Onboarding";
import { ErrorState, Loading, cx } from "./ui";

const MetaContext = createContext<Meta | null>(null);

export function useMeta(): Meta {
  const m = useContext(MetaContext);
  if (!m) throw new Error("useMeta must be used inside <AppShell>");
  return m;
}

const NAV: { section: string; items: { href: string; key: string; icon: string }[] }[] = [
  {
    section: "nav.section_analyze",
    items: [
      { href: "/", key: "nav.dashboard", icon: "M3 13h4v8H3zM10 9h4v12h-4zM17 4h4v17h-4z" },
      { href: "/costs", key: "nav.costs", icon: "M12 3v18M7 7.5C7 5.6 9.2 4.5 12 4.5s5 1.1 5 3-2.2 3-5 3.5-5 1.6-5 3.5 2.2 3 5 3 5-1.1 5-3" },
      { href: "/departments", key: "nav.departments", icon: "M4 21V8l8-5 8 5v13M9 21v-6h6v6" },
      { href: "/outcomes", key: "nav.outcomes", icon: "M4 19l5-6 4 3 7-9M15 7h5v5" },
      { href: "/comparison", key: "nav.comparison", icon: "M6 4v16M18 4v16M3 9h6M15 15h6" },
    ],
  },
  {
    section: "nav.section_act",
    items: [{ href: "/recommendations", key: "nav.recommendations", icon: "M12 3l9 16H3zM12 10v4M12 17h.01" }],
  },
  {
    section: "nav.section_manage",
    items: [
      { href: "/data", key: "nav.data", icon: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" },
      { href: "/settings", key: "nav.settings", icon: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4" },
    ],
  },
];

function isActive(path: string, href: string) {
  if (href === "/") return path === "/";
  return path === href || path.startsWith(`${href}/`) || (href === "/outcomes" && path.startsWith("/use-cases"));
}

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  const { token, setMe } = useAuth();
  const choose = (l: Locale) => {
    setLocale(l);
    if (token) {
      apiFetch<Me>("/api/auth/me", token, { method: "PATCH", body: JSON.stringify({ preferred_locale: l }) })
        .then(setMe)
        .catch(() => undefined);
    }
  };
  return (
    <div role="group" aria-label={t("app.language")} className="inline-flex rounded-md border border-line bg-surface p-0.5">
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={locale === l}
          onClick={() => choose(l)}
          className={cx("rounded px-2 py-0.5 text-xs font-semibold", locale === l ? "bg-brand text-white" : "text-ink-2 hover:bg-subtle")}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function Logo() {
  return (
    <span className="flex items-center gap-2">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#12233d" />
        <path d="M8 23 15.2 9h1.6L24 23h-3.3l-1.5-3.2h-6.4L11.3 23Zm5.6-5.8h4.8L16 12.1Z" fill="#fff" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink">Aivanta</span>
    </span>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const path = usePathname() || "/";
  return (
    <nav aria-label={t("nav.menu")} className="space-y-6">
      {NAV.map((group) => (
        <div key={group.section}>
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted">{t(group.section)}</p>
          <ul className="mt-2 space-y-0.5">
            {group.items.map((item) => {
              const active = isActive(path, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cx(
                      "flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm",
                      active ? "bg-brand-soft font-medium text-brand" : "text-ink-2 hover:bg-subtle hover:text-ink",
                    )}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d={item.icon} />
                    </svg>
                    {t(item.key)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children, filters = true }: { children: ReactNode; filters?: boolean }) {
  const { t } = useI18n();
  const { ready, token, me, logout } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const meta = useApi<Meta>(token ? "/api/meta" : null);

  useEffect(() => {
    if (ready && !token) router.replace("/login");
  }, [ready, token, router]);

  if (!ready || !token) {
    return <div className="p-8"><Loading rows={2} /></div>;
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        {t("app.skip_to_content")}
      </a>
      <aside className="hidden border-r border-line bg-surface lg:flex lg:flex-col">
        <div className="px-5 pb-4 pt-5"><Logo /></div>
        <div className="flex-1 overflow-y-auto px-2 pb-6"><Nav /></div>
        {me && (
          <div className="border-t border-line px-5 py-3 text-xs">
            <p className="truncate font-medium text-ink">{me.display_name ?? me.email}</p>
            <p className="truncate text-muted">{t(`role.${me.role}`)} · {me.organization_name}</p>
            <button onClick={logout} className="mt-2 text-accent hover:underline">{t("app.sign_out")}</button>
          </div>
        )}
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setMenuOpen(false)}>
          <div className="h-full w-64 bg-surface p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-6"><Logo /></div>
            <Nav onNavigate={() => setMenuOpen(false)} />
            {me && (
              <button onClick={logout} className="mt-8 text-sm text-accent hover:underline">{t("app.sign_out")}</button>
            )}
          </div>
        </div>
      )}

      <div className="min-w-0">
        <div className="sticky top-0 z-30 border-b border-line bg-page/95 backdrop-blur">
          {meta.data?.synthetic && (
            <div className="border-b border-[#c7dbf5] bg-info-soft px-4 py-1.5 text-center text-xs text-[#1c5cab] lg:px-8">
              <span className="font-semibold">{t("app.synthetic_short")}.</span> {t("app.synthetic_banner")}
            </div>
          )}
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 lg:px-8">
            <div className="flex items-center gap-3 lg:hidden">
              <button type="button" onClick={() => setMenuOpen(true)} aria-label={t("nav.menu")} className="rounded-md border border-line bg-surface p-1.5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden><path d="M4 7h16M4 12h16M4 17h16" /></svg>
              </button>
              <Logo />
            </div>
            <div className="hidden text-xs text-muted lg:block">{me?.organization_name}</div>
            <LanguageSwitcher />
          </div>
          {filters && meta.data && <FilterBar meta={meta.data} />}
        </div>
        <main id="main" className="mx-auto max-w-[1400px] px-4 py-6 lg:px-8">
          {meta.error ? (
            <ErrorState error={meta.error} onRetry={meta.reload} />
          ) : !meta.data ? (
            <Loading />
          ) : (
            <MetaContext.Provider value={meta.data}>
              <Onboarding />
              {children}
            </MetaContext.Provider>
          )}
        </main>
      </div>
    </div>
  );
}
