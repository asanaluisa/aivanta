import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center">
      <p className="text-sm font-semibold text-ink">404</p>
      <Link href="/" className="text-sm text-accent hover:underline">Aivanta</Link>
    </main>
  );
}
