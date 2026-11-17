"use client";

import Link from "next/link";
import { useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { ALERT_TYPES, SEVERITIES, type Alert } from "@/lib/types";
import { Badge, ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";

interface Summary { by_status: { ack_status: string; alert_type: string; count: number }[] }

export default function AlertsPage() {
  const { isAdmin } = useAuth();
  const [status, setStatus] = useState("PENDING");
  const [type, setType] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Alert[]>("/api/alerts", { ack_status: status, alert_type: type, severity, search: q });
  const { data: summary, reload: reloadSummary } = useApi<Summary>("/api/alerts/summary");
  const refresh = () => { reload(); reloadSummary(); };

  const [msg, setMsg] = useState<string | null>(null);
  const [ackFor, setAckFor] = useState<Alert | null>(null);
  const [comment, setComment] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Alert | null>(null);
  const [form, setForm] = useState({ incident_id: "", alert_type: "TAILGATING", message: "" });
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Alert | null>(null);

  const pending = summary?.by_status.filter((s) => s.ack_status === "PENDING").reduce((a, b) => a + b.count, 0) ?? 0;
  const acked = summary?.by_status.filter((s) => s.ack_status === "ACKNOWLEDGED").reduce((a, b) => a + b.count, 0) ?? 0;

  async function acknowledge(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy(true);
    try {
      await api.patch(`/api/alerts/${ackFor!.alert_id}/ack`, { comment });
      setMsg(`Alert ${ackFor!.alert_id} acknowledged.`);
      setAckFor(null);
      refresh();
    } catch (e) {
      setError((e as Error).message);
      setAckFor(null);
    } finally {
      setBusy(false);
    }
  }

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    if (!editing && !(Number(form.incident_id) > 0)) return setFormErr("Enter the incident_id from PostgreSQL.");
    if (form.message.trim().length < 5) return setFormErr("Message must be at least 5 characters.");
    setBusy(true);
    try {
      if (editing) await api.put(`/api/alerts/${editing.alert_id}`, { alert_type: form.alert_type, message: form.message });
      else await api.post("/api/alerts", { incident_id: Number(form.incident_id), alert_type: form.alert_type, message: form.message });
      setMsg(editing ? `Alert ${editing.alert_id} updated.` : "Alert created.");
      setOpen(false);
      refresh();
    } catch (e) {
      setFormErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reopen(a: Alert) {
    try {
      await api.post(`/api/alerts/${a.alert_id}/reopen`);
      setMsg(`Alert ${a.alert_id} set back to PENDING.`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await api.del(`/api/alerts/${toDelete.alert_id}`);
      setMsg(`Alert ${toDelete.alert_id} deleted.`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Alert>[] = [
    { key: "alert_time", label: "Time", render: (a) => fmtDateTime(a.alert_time) },
    { key: "incident_id", label: "Incident", render: (a) => <Link href={`/incidents/${a.incident_id}`} className="text-indigo-600 hover:underline">#{a.incident_id}</Link> },
    { key: "alert_type", label: "Type", render: (a) => <Badge value={a.alert_type} /> },
    { key: "severity", label: "Severity", render: (a) => <Badge value={a.severity} /> },
    { key: "message", label: "Message", className: "max-w-md" },
    { key: "ack_status", label: "Status", render: (a) => <><Badge value={a.ack_status} />{a.acknowledged && <div className="mt-1 text-xs text-slate-400">by {a.acknowledged.by}{a.acknowledged.comment && ` – “${a.acknowledged.comment}”`}</div>}</> },
    {
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (a) => (
        <div className="flex justify-end gap-1">
          {a.ack_status === "PENDING" && <button className="btn-secondary px-2 py-1" onClick={() => { setAckFor(a); setComment(""); }}>Acknowledge</button>}
          {isAdmin && a.ack_status === "ACKNOWLEDGED" && <button className="btn-ghost" onClick={() => reopen(a)}>Reopen</button>}
          {isAdmin && <button className="btn-ghost" onClick={() => { setEditing(a); setForm({ incident_id: String(a.incident_id), alert_type: a.alert_type, message: a.message }); setFormErr(null); setOpen(true); }}>Edit</button>}
          {isAdmin && <button className="btn-ghost text-rose-600" onClick={() => setToDelete(a)}>Delete</button>}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Alerts" subtitle="MongoDB collection Alerts · acknowledgement stored as a nested document"
        actions={isAdmin && <button className="btn-primary" onClick={() => { setEditing(null); setForm({ incident_id: "", alert_type: "TAILGATING", message: "" }); setFormErr(null); setOpen(true); }}>+ New alert</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}

      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <button className={`card p-4 text-left ${status === "PENDING" ? "ring-2 ring-amber-300" : ""}`} onClick={() => setStatus("PENDING")}>
          <p className="text-xs text-slate-500">Pending</p><p className="text-2xl font-semibold text-amber-600">{pending}</p>
        </button>
        <button className={`card p-4 text-left ${status === "ACKNOWLEDGED" ? "ring-2 ring-emerald-300" : ""}`} onClick={() => setStatus("ACKNOWLEDGED")}>
          <p className="text-xs text-slate-500">Acknowledged</p><p className="text-2xl font-semibold text-emerald-600">{acked}</p>
        </button>
        <div className="card col-span-2 p-4 text-xs text-slate-500">
          <p className="mb-1 font-semibold text-slate-700">$group by ack_status + alert_type</p>
          {summary?.by_status.map((s) => <span key={s.ack_status + s.alert_type} className="mr-3 inline-block">{s.ack_status.toLowerCase()} · {s.alert_type.toLowerCase()}: <b>{s.count}</b></span>)}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search message…" />
        <Select value={status} onChange={setStatus} options={["PENDING", "ACKNOWLEDGED"]} placeholder="All statuses" />
        <Select value={type} onChange={setType} options={ALERT_TYPES} placeholder="All types" />
        <Select value={severity} onChange={setSeverity} options={SEVERITIES} placeholder="All severities" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(a) => a.alert_id} empty="No alerts match the filters." />

      <Modal title={`Acknowledge ${ackFor?.alert_id}`} open={!!ackFor} onClose={() => setAckFor(null)}>
        <form onSubmit={acknowledge} className="space-y-3">
          <p className="text-sm text-slate-600">{ackFor?.message}</p>
          <Field label="Comment (optional)"><input className="input" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={200} /></Field>
          <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setAckFor(null)}>Cancel</button><button className="btn-primary" disabled={busy}>Acknowledge</button></div>
        </form>
      </Modal>

      <Modal title={editing ? `Edit ${editing.alert_id}` : "New alert"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field label="Incident ID (PostgreSQL)"><input className="input" type="number" min={1} disabled={!!editing} value={form.incident_id} onChange={(e) => setForm({ ...form, incident_id: e.target.value })} /></Field>
          <Field label="Type"><select className="input" value={form.alert_type} onChange={(e) => setForm({ ...form, alert_type: e.target.value })}>{ALERT_TYPES.map((t) => <option key={t}>{t}</option>)}</select></Field>
          <Field label="Message"><textarea className="input" rows={3} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></Field>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>Save</button></div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete alert" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete alert <b>{toDelete?.alert_id}</b> from MongoDB?</>} />
    </>
  );
}
