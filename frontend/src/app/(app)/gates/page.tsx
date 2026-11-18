"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { Badge, ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";

interface Gate { gate_id: number; gate_name: string; location: string; type: string; status: string; scan_count: number; incident_count: number }
interface Cascade { incidents_removed: number; mongo_documents_removed: Record<string, number> }
type Form = { gate_name: string; location: string; type: string; status: string };
const TYPES = ["ENTRY", "EXIT", "BIDIRECTIONAL"];
const STATUSES = ["ACTIVE", "INACTIVE", "MAINTENANCE"];
const blank: Form = { gate_name: "", location: "", type: "ENTRY", status: "ACTIVE" };

export default function GatesPage() {
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Gate[]>("/api/gates", { search: q, status });

  const [editing, setEditing] = useState<Gate | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Form>(blank);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Gate | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    if (form.gate_name.trim().length < 2) return setFormErr("Gate name must have at least 2 characters.");
    if (form.location.trim().length < 2) return setFormErr("Location is required.");
    setBusy(true);
    try {
      if (editing) await api.put(`/api/gates/${editing.gate_id}`, form);
      else await api.post("/api/gates", form);
      setMsg(editing ? `Gate ${form.gate_name} updated.` : `Gate ${form.gate_name} created.`);
      setOpen(false);
      reload();
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
      const r = await api.del<Cascade>(`/api/gates/${toDelete.gate_id}`);
      setMsg(`Gate ${toDelete.gate_name} deleted with its scans; ` + `${r.incidents_removed} incident(s) and ${Object.values(r.mongo_documents_removed).reduce((a, b) => a + b, 0)} MongoDB document(s) removed with it.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Gate>[] = [
    { key: "gate_id", label: "ID" },
    { key: "gate_name", label: "Gate", render: (g) => <span className="font-medium">{g.gate_name}</span> },
    { key: "location", label: "Location" },
    { key: "type", label: "Type", render: (g) => <Badge value={g.type} /> },
    { key: "status", label: "Status", render: (g) => <Badge value={g.status} /> },
    { key: "scan_count", label: "Scans" },
    { key: "incident_count", label: "Incidents", render: (g) => <span className={g.incident_count ? "font-semibold text-orange-600" : ""}>{g.incident_count}</span> },
  ];
  if (isAdmin)
    columns.push({
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (g) => (
        <div className="flex justify-end gap-1">
          <button className="btn-ghost" onClick={() => { setEditing(g); setForm({ gate_name: g.gate_name, location: g.location, type: g.type, status: g.status }); setFormErr(null); setOpen(true); }}>Edit</button>
          <button className="btn-ghost text-rose-600" onClick={() => setToDelete(g)}>Delete</button>
        </div>
      ),
    });

  return (
    <>
      <PageHeader title="Gates" subtitle="R3 Gates · scans at gates that are not ACTIVE are denied by trigger trg_validate_access_log"
        actions={isAdmin && <button className="btn-primary" onClick={() => { setEditing(null); setForm(blank); setFormErr(null); setOpen(true); }}>+ Add gate</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search gate or location…" />
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(g) => g.gate_id} />

      <Modal title={editing ? `Edit gate #${editing.gate_id}` : "Add gate"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field label="Gate name"><input className="input" value={form.gate_name} onChange={(e) => setForm({ ...form, gate_name: e.target.value })} /></Field>
          <Field label="Location"><input className="input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type"><select className="input" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></Field>
            <Field label="Status"><select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{STATUSES.map((t) => <option key={t}>{t}</option>)}</select></Field>
          </div>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete gate" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete gate <b>{toDelete?.gate_name}</b>? All scans at this gate and their incidents are deleted too (ON DELETE CASCADE), with the linked MongoDB documents. This cannot be undone.</>} />
    </>
  );
}
