"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { INCIDENT_STATUSES as STATUSES, SEVERITIES, type Incident } from "@/lib/types";
import { Badge, ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";

const SEV_ORDER: Record<string, number> = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

function IncidentsInner() {
  const { isAdmin, canWrite } = useAuth();
  const params = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Incident[]>("/api/incidents", { search: q, severity, status });

  const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<Incident | null>(null);
  const [form, setForm] = useState({ severity: "LOW", status: "OPEN" });
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Incident | null>(null);

  async function changeStatus(i: Incident, s: string) {
    try {
      await api.patch(`/api/incidents/${i.incident_id}/status`, { status: s });
      setMsg(`Incident #${i.incident_id} → ${s.replace("_", " ")}`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveEdit(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy(true);
    try {
      await api.put(`/api/incidents/${editing!.incident_id}`, form);
      setMsg(`Incident #${editing!.incident_id} updated.`);
      setEditing(null);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      const r = await api.del<{ mongo_documents_removed: Record<string, number> }>(`/api/incidents/${toDelete.incident_id}`);
      const m = r.mongo_documents_removed;
      setMsg(`Incident #${toDelete.incident_id} deleted from PostgreSQL; MongoDB cleanup: ${m.Observations} observation(s), ${m.Report} report(s), ${m.Alerts} alert(s).`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Incident>[] = [
    { key: "incident_id", label: "#", render: (i) => <Link className="font-medium text-indigo-600 hover:underline" href={`/incidents/${i.incident_id}`}>#{i.incident_id}</Link> },
    { key: "detected_time", label: "Detected", render: (i) => fmtDateTime(i.detected_time) },
    { key: "gate_name", label: "Gate" },
    { key: "employee", label: "Card holder", render: (i) => <>{i.employee}<div className="font-mono text-xs text-slate-400">{i.card_no} · scan #{i.scan_id}</div></> },
    { key: "severity", label: "Severity", render: (i) => <Badge value={i.severity} />, sortValue: (i) => SEV_ORDER[i.severity] },
    {
      key: "status", label: "Status",
      render: (i) => !canWrite ? <Badge value={i.status} /> : (
        <select className="rounded border border-slate-200 bg-white px-1.5 py-1 text-xs" value={i.status} onChange={(e) => changeStatus(i, e.target.value)} aria-label="Change status">
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
      ),
    },
    { key: "mongo", label: "MongoDB docs", sortable: false, render: (i) => <span className="text-xs text-slate-500">{i.observations} obs · {i.reports} rep · {i.pending_alerts ? <b className="text-rose-600">{i.pending_alerts} pending</b> : "0 pending"}</span> },
    {
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (i) => (
        <div className="flex justify-end gap-1">
          <Link href={`/incidents/${i.incident_id}`} className="btn-ghost">Open</Link>
          {isAdmin && <button className="btn-ghost" onClick={() => { setEditing(i); setForm({ severity: i.severity, status: i.status }); }}>Edit</button>}
          {isAdmin && <button className="btn-ghost text-rose-600" onClick={() => setToDelete(i)}>Delete</button>}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Incidents" subtitle="R5 Incidents (PostgreSQL) with linked MongoDB documents · new incidents are reported from Access Logs"
        actions={canWrite && <Link href="/access-logs" className="btn-primary">+ Report from a scan</Link>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search employee, gate or card…" />
        <Select value={severity} onChange={setSeverity} options={SEVERITIES} placeholder="All severities" />
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(i) => i.incident_id} />

      <Modal title={`Edit incident #${editing?.incident_id}`} open={!!editing} onClose={() => setEditing(null)}>
        <form onSubmit={saveEdit} className="space-y-3">
          <Field label="Severity"><select className="input" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>{SEVERITIES.map((s) => <option key={s}>{s}</option>)}</select></Field>
          <Field label="Status"><select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></Field>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>Save</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete incident" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete incident <b>#{toDelete?.incident_id}</b>? Its observations, reports and alerts in MongoDB will also be removed.</>} />
    </>
  );
}

export default function IncidentsPage() {
  return (
    <Suspense>
      <IncidentsInner />
    </Suspense>
  );
}
