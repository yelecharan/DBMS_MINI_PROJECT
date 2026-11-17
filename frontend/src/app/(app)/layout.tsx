"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

const NAV = [
  { section: "Overview", items: [{ href: "/dashboard", label: "Dashboard", icon: "▦" }] },
  {
    section: "PostgreSQL",
    items: [
      { href: "/employees", label: "Employees", icon: "👤" },
      { href: "/cards", label: "Cards", icon: "▭" },
      { href: "/gates", label: "Gates", icon: "⛩" },
      { href: "/access-logs", label: "Access Logs", icon: "≡" },
      { href: "/incidents", label: "Incidents", icon: "⚠" },
    ],
  },
  {
    section: "MongoDB",
    items: [
      { href: "/observations", label: "Observations", icon: "👁" },
      { href: "/reports", label: "Reports", icon: "📄" },
      { href: "/alerts", label: "Alerts", icon: "🔔" },
    ],
  },
  { section: "Database", items: [{ href: "/query-lab", label: "Query Lab", icon: "⌘" }] },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !user) router.replace("/login");
  }, [ready, user, router]);

  if (!ready || !user) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400">Loading…</div>;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-slate-900 text-slate-300 md:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">⛨</span>
          <span className="text-lg font-semibold text-white">GateSentry</span>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          {NAV.map((group) => (
            <div key={group.section} className="mb-4">
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{group.section}</p>
              {group.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm ${active ? "bg-slate-800 text-white" : "hover:bg-slate-800/60 hover:text-white"}`}
                  >
                    <span className="w-5 text-center">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-6 py-3 backdrop-blur">
          <select
            className="input w-auto md:hidden"
            value={pathname}
            onChange={(e) => router.push(e.target.value)}
            aria-label="Navigate"
          >
            {NAV.flatMap((g) => g.items).map((i) => (
              <option key={i.href} value={i.href}>{i.label}</option>
            ))}
          </select>
          <span className="hidden text-sm text-slate-500 md:block">Tailgating Management System</span>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium">{user.username}</p>
              <p className={`text-xs font-semibold ${user.role === "admin" ? "text-indigo-600" : user.role === "security" ? "text-emerald-600" : "text-slate-500"}`}>
                {user.role === "admin" ? "Administrator" : user.role === "security" ? "Security Staff" : "Viewer (read-only)"}
              </p>
            </div>
            <button
              className="btn-secondary"
              onClick={async () => {
                await logout();
                router.replace("/login");
              }}
            >
              Logout
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
