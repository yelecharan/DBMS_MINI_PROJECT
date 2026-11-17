"use client";

import Link from "next/link";
import { useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { METHODS, type Observation } from "@/lib/types";
import { ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, Select, type Column } from "@/components/ui";

interface Stats {
  per_gate: { gate: string; observations: number; unauthorised_people: number; avg_excess: number; max_excess: number }[];
  per_method: { method: string; count: number }[];
}
interface Gate { gate_id: number; gate_name: string }
type Form = { incident_id: string; method: string; observed_count: string; authorized_count: string; notes: string; tags: string };
const blank: Form = { incident_id: "", method: METHODS[0], observed_count: "", authorized_count: "", notes: "", tags: "" };

export default function ObservationsPage() {
  const { isAdmin, canWrite } = useAuth();
  const [method, setMethod] = useState("");
  const [gate, setGate] = useState("");
  const [minExcess, setMinExcess] = useState("");
  const [order, setOrder] = useState("desc");
  const { data, loading, error, reload, setError } = useApi<Observation[]>("/api/observations", { method, gate_id: gate, min_excess: minExcess, order });
  const { data: stats, reload: reloadStats } = useApi<Stats>("/api/observations/stats");
  const { data: gates } = useApi<Gate[]>("/api/gates");

  const [editing, setEditing] = useState<Observation | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Form>(blank);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Observation | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const refresh = () => { reload(); reloadStats(); };

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    const o = Number(form.observed_count), a = Number(form.authorized_count);
    if (!editing && !(Number(form.incident_id) > 0)) return setFormErr("Enter the PostgreSQL incident_id this observation belongs to.");
    if (form.observed_count === "" || form.authorized_count === "" || !Number.isInteger(o) || !Number.isInteger(a) || o < 0 || a < 0)
      return setFormErr("Counts must be whole numbers ≥ 0.");
    const body = { method: form.method, observed_count: o, authorized_count: a, notes: form.notes, tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean) };
    setBusy(true);
    try {
      if (editing) await api.put(`/api/observations/${editing.obs_id}`, body);
      else await api.post("/api/observations", { ...body, incident_id: Number(form.incident_id) });
      setMsg(editing ? `Observation ${editing.obs_id} updated ($set).` : "Observation inserted (insertOne).");
      setOpen(false);
      refresh();
    } catch (e) {
      setFormErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await api.del(`/api/observations/${toDelete.obs_id}`);
      setMsg(`Observation ${toDelete.obs_id} deleted (deleteOne).`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Observation>[] = [
    { key: "obs_id", label: "obs_id", render: (o) => <span className="font-mono text-xs">{o.obs_id}</span> },
    { key: "incident_id", label: "Incident", render: (o) => <Link href={`/incidents/${o.incident_id}`} className="text-indigo-600 hover:underline">#{o.incident_id}</Link> },
    { key: "timestamp", label: "Time", render: (o) => fmtDateTime(o.timestamp) },
    { key: "gate", label: "Gate (nested)", render: (o) => o.location?.gate_name ?? "—", sortValue: (o) => o.location?.gate_name ?? "" },
    { key: "method", label: "Method", render: (o) => o.method.replaceAll("_", " ") },
    { key: "observed_count", label: "Observed" },
    { key: "authorized_count", label: "Authorised" },
    { key: "excess", label: "Excess", render: (o) => <b className="text-rose-600">+{o.excess}</b> },
    { key: "tags", label: "Tags (array)", sortable: false, render: (o) => <div className="flex flex-wrap gap-1">{o.tags?.map((t) => <span key={t} className="rounded bg-slate-100 px-1.5 text-xs">{t}</span>)}</div> },
    {
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (o) => (
        <div className="flex justify-end gap-1">
          {canWrite && <button className="btn-ghost" onClick={() => { setEditing(o); setForm({ incident_id: String(o.incident_id), method: o.method, observed_count: String(o.observed_count), authorized_count: String(o.authorized_count), notes: o.notes ?? "", tags: (o.tags ?? []).join(", ") }); setFormErr(null); setOpen(true); }}>Edit</button>}
          {isAdmin && <button className="btn-ghost text-rose-600" onClick={() => setToDelete(o)}>Delete</button>}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Observations" subtitle="MongoDB collection Observations · head-counts compared with authorised scans"
        actions={canWrite && <button className="btn-primary" onClick={() => { setEditing(null); setForm(blank); setFormErr(null); setOpen(true); }}>+ Record observation</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <section className="card p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold">Unauthorised people per gate</h2>
          <p className="mb-2 text-xs text-slate-400">Aggregation: $project → $group → $sort</p>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-400"><tr><th>Gate</th><th>Observations</th><th>Unauthorised</th><th>Avg excess</th><th>Max</th></tr></thead>
            <tbody>{stats?.per_gate.map((g) => <tr key={g.gate} className="border-t border-slate-100"><td className="py-1">{g.gate}</td><td>{g.observations}</td><td className="font-semibold text-rose-600">{g.unauthorised_people}</td><td>{g.avg_excess}</td><td>{g.max_excess}</td></tr>)}</tbody>
          </table>
        </section>
        <section className="card p-4">
          <h2 className="text-sm font-semibold">By method</h2>
          <p className="mb-2 text-xs text-slate-400">Aggregation: $group → $sort</p>
          <ul className="space-y-1 text-sm">{stats?.per_method.map((m) => <li key={m.method} className="flex justify-between"><span>{m.method.replaceAll("_", " ")}</span><b>{m.count}</b></li>)}</ul>
        </section>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={method} onChange={setMethod} options={METHODS} placeholder="All methods" />
        <Select value={gate} onChange={setGate} options={(gates ?? []).map((g) => ({ value: String(g.gate_id), label: g.gate_name }))} placeholder="All gates" />
        <Select value={minExcess} onChange={setMinExcess} options={[{ value: "2", label: "Excess ≥ 2" }, { value: "3", label: "Excess ≥ 3" }, { value: "5", label: "Excess ≥ 5" }]} placeholder="Any excess" />
        <Select value={order} onChange={setOrder} options={[{ value: "desc", label: "Newest first" }, { value: "asc", label: "Oldest first" }]} />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(o) => o.obs_id} />

      <Modal title={editing ? `Edit ${editing.obs_id}` : "Record observation"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field label="Incident ID (PostgreSQL)" hint="The backend checks that this incident exists before inserting">
            <input className="input" type="number" min={1} value={form.incident_id} disabled={!!editing} onChange={(e) => setForm({ ...form, incident_id: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="People observed"><input className="input" type="number" min={0} value={form.observed_count} onChange={(e) => setForm({ ...form, observed_count: e.target.value })} /></Field>
            <Field label="Authorised scans"><input className="input" type="number" min={0} value={form.authorized_count} onChange={(e) => setForm({ ...form, authorized_count: e.target.value })} /></Field>
          </div>
          <Field label="Method"><select className="input" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>{METHODS.map((m) => <option key={m} value={m}>{m.replaceAll("_", " ")}</option>)}</select></Field>
          <Field label="Tags (comma separated)"><input className="input" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} /></Field>
          <Field label="Notes"><textarea className="input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button></div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete observation" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete observation <b>{toDelete?.obs_id}</b> from MongoDB? The PostgreSQL incident is not affected.</>} />
    </>
  );
}
