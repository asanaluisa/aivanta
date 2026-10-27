/**
 * Framework-free translation helpers. Messages live in ./messages/<locale>.json;
 * components never branch on the locale themselves.
 */
import en from "./messages/en.json";
import es from "./messages/es.json";

export const LOCALES = ["en", "es"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

type Tree = { [key: string]: string | Tree };
export const MESSAGES: Record<Locale, Tree> = { en: en as Tree, es: es as Tree };

export type Params = Record<string, string | number>;

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function lookup(tree: Tree, key: string): string | undefined {
  let node: string | Tree | undefined = tree;
  for (const part of key.split(".")) {
    if (node === undefined || typeof node === "string") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Translate ``key``; falls back to English, then to the key itself (visible in QA). */
export function translate(locale: Locale, key: string, params?: Params): string {
  const raw = lookup(MESSAGES[locale], key) ?? lookup(MESSAGES.en, key) ?? key;
  return interpolate(raw, params);
}

export function hasKey(locale: Locale, key: string): boolean {
  return lookup(MESSAGES[locale], key) !== undefined;
}

/** All leaf keys of a message tree, dotted. Used by the parity test. */
export function flattenKeys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [prefix + k] : flattenKeys(v, `${prefix}${k}.`),
  );
}

export function placeholders(template: string): string[] {
  return Array.from(template.matchAll(/\{(\w+)\}/g), (m) => m[1]).sort();
}
