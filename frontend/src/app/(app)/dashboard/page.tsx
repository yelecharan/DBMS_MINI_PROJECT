"use client";

import Link from "next/link";
import { fmtDateTime } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Badge, Notice, PageHeader } from "@/components/ui";

interface Dashboard {
  counts: Record<string, number>;
  trend: { day: string; incidents: number }[];
  gate_risk: { gate_id: number; gate_name: string; total_scans: number; denied_scans: number; incidents: number; risk_score: string | null }[];
  recent_incidents: { incident_id: number; detected_time: string; severity: string; status: string; gate_name: string; employee: string }[];
}

function Stat({ label, value, sub, href, accent }: { label: string; value: number | undefined; sub?: string; href: string; accent: string }) {
  return (
    <Link href={href} className="card group p-5 transition-shadow hover:shadow-md">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${accent}`}>{value ?? "–"}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </Link>
  );
}

export default function DashboardPage() {
  const { data, loading, error } = useApi<Dashboard>("/api/dashboard");
  const c = data?.counts ?? {};
  const maxTrend = Math.max(1, ...(data?.trend.map((t) => t.incidents) ?? [1]));

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live figures from PostgreSQL (gatesentry) and MongoDB (gatesentry)" />
      {error && <Notice>{error}</Notice>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <Stat label="Employees" value={c.employees} href="/employees" accent="text-slate-900" />
        <Stat label="Registered cards" value={c.cards} sub={`${c.active_cards ?? "–"} active`} href="/cards" accent="text-slate-900" />
        <Stat label="Gates" value={c.gates} href="/gates" accent="text-slate-900" />
        <Stat label="Access scans" value={c.scans} sub={`${c.denied_scans ?? "–"} denied`} href="/access-logs" accent="text-slate-900" />
        <Stat label="Tailgating incidents" value={c.incidents} sub={`${c.open_incidents ?? "–"} open / investigating`} href="/incidents" accent="text-orange-600" />
        <Stat label="Pending alerts" value={c.pending_alerts} sub="MongoDB · Alerts" href="/alerts" accent="text-rose-600" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-5">
        <section className="card p-5 xl:col-span-3">
          <h2 className="font-semibold">Incidents – last 14 days</h2>
          <p className="mb-4 text-xs text-slate-400">Recursive CTE generates the calendar, LEFT JOIN incidents</p>
          {loading ? (
            <p className="py-16 text-center text-slate-400">Loading…</p>
          ) : (
            <div className="flex h-48 items-end gap-1.5">
              {data?.trend.map((t) => (
                <div key={t.day} className="flex flex-1 flex-col items-center gap-1" title={`${t.day}: ${t.incidents}`}>
                  <span className="text-[10px] text-slate-500">{t.incidents || ""}</span>
                  <div className="w-full rounded-t bg-indigo-500" style={{ height: `${(t.incidents / maxTrend) * 150}px`, minHeight: t.incidents ? 4 : 1 }} />
                  <span className="text-[10px] text-slate-400">{new Date(t.day).getDate()}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card p-5 xl:col-span-2">
          <h2 className="font-semibold">Gate risk</h2>
          <p className="mb-3 text-xs text-slate-400">Stored function fn_gate_risk_summary() – incidents per 100 scans</p>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-400">
              <tr><th className="py-1">Gate</th><th>Scans</th><th>Denied</th><th>Incidents</th><th>Risk</th></tr>
            </thead>
            <tbody>
              {data?.gate_risk.map((g) => (
                <tr key={g.gate_id} className="border-t border-slate-100">
                  <td className="py-1.5">{g.gate_name}</td>
                  <td>{g.total_scans}</td>
                  <td>{g.denied_scans}</td>
                  <td>{g.incidents}</td>
                  <td className="font-semibold">{g.risk_score ?? "0"}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <section className="card mt-6 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Most recent incidents</h2>
          <Link href="/incidents" className="text-sm text-indigo-600 hover:underline">View all →</Link>
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-400">
            <tr><th className="py-1">#</th><th>Detected</th><th>Gate</th><th>Card holder</th><th>Severity</th><th>Status</th></tr>
          </thead>
          <tbody>
            {data?.recent_incidents.map((i) => (
              <tr key={i.incident_id} className="border-t border-slate-100">
                <td className="py-2"><Link className="text-indigo-600 hover:underline" href={`/incidents/${i.incident_id}`}>#{i.incident_id}</Link></td>
                <td>{fmtDateTime(i.detected_time)}</td>
                <td>{i.gate_name}</td>
                <td>{i.employee}</td>
                <td><Badge value={i.severity} /></td>
                <td><Badge value={i.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
