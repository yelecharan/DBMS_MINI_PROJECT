"use client";

import { useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Notice, PageHeader } from "@/components/ui";

interface SqlQuery { key: string; title: string; category: string; sql: string }
interface MongoQuery { key: string; title: string; collection: string; pipeline: unknown[] }
interface Result { columns?: string[]; rows: Record<string, unknown>[] }

const isDate = (v: unknown) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v);
const cell = (v: unknown) => (v === null || v === undefined ? "—" : isDate(v) ? fmtDateTime(v) : typeof v === "object" ? JSON.stringify(v) : String(v));

export default function QueryLabPage() {
  const { data: sqlList } = useApi<SqlQuery[]>("/api/analytics/sql");
  const { data: mongoList } = useApi<MongoQuery[]>("/api/analytics/mongo");
  const [selected, setSelected] = useState<{ kind: "sql" | "mongo"; key: string } | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run(kind: "sql" | "mongo", key: string) {
    setSelected({ kind, key });
    setLoading(true);
    setError(null);
    try {
      setResult(await api.get<Result>(`/api/analytics/${kind}/${key}`));
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const sqlSel = selected?.kind === "sql" ? sqlList?.find((q) => q.key === selected.key) : undefined;
  const mongoSel = selected?.kind === "mongo" ? mongoList?.find((q) => q.key === selected.key) : undefined;
  const columns = result?.columns ?? (result?.rows[0] ? Object.keys(result.rows[0]) : []);
  const groups = [...new Set(sqlList?.map((q) => q.category))];

  return (
    <>
      <PageHeader title="Query Lab" subtitle="Run the report's SQL queries and MongoDB pipelines live against the real databases (with your role's privileges)" />
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="card max-h-[75vh] overflow-y-auto p-3">
          {groups.map((g) => (
            <div key={g} className="mb-3">
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">SQL · {g}</p>
              {sqlList?.filter((q) => q.category === g).map((q) => (
                <button key={q.key} onClick={() => run("sql", q.key)}
                  className={`block w-full rounded px-2 py-1.5 text-left text-sm ${selected?.key === q.key ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50"}`}>
                  {q.title}
                </button>
              ))}
            </div>
          ))}
          <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">MongoDB · aggregation</p>
          {mongoList?.map((q) => (
            <button key={q.key} onClick={() => run("mongo", q.key)}
              className={`block w-full rounded px-2 py-1.5 text-left text-sm ${selected?.key === q.key ? "bg-emerald-50 text-emerald-700" : "hover:bg-slate-50"}`}>
              {q.title}
            </button>
          ))}
        </aside>

        <section className="min-w-0">
          {!selected && <div className="card p-10 text-center text-slate-400">Choose a query on the left.</div>}
          {selected && (
            <>
              <div className="card mb-4 overflow-x-auto bg-slate-900 p-4">
                <p className="mb-2 text-xs text-slate-400">{sqlSel ? "PostgreSQL" : `MongoDB · db.${mongoSel?.collection}.aggregate(…)`}</p>
                <pre className="font-mono text-xs leading-relaxed text-emerald-200">{sqlSel ? sqlSel.sql : JSON.stringify(mongoSel?.pipeline, null, 2)}</pre>
              </div>
              {error && <Notice>{error}</Notice>}
              {loading ? <p className="text-slate-400">Running…</p> : result && (
                <div className="card overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="bg-slate-50"><tr>{columns.map((c) => <th key={c} className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">{c}</th>)}</tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {result.rows.map((r, i) => <tr key={i}>{columns.map((c) => <td key={c} className="px-3 py-1.5 font-mono text-xs">{cell(r[c])}</td>)}</tr>)}
                    </tbody>
                  </table>
                  <div className="border-t border-slate-100 px-3 py-2 text-xs text-slate-400">{result.rows.length} row(s)</div>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
