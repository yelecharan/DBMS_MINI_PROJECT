"use client";

import { useState } from "react";
import { api, fmtDate } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { Badge, ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";

interface Card {
  card_id: number; card_no: string; emp_id: number; employee: string; department: string;
  issue_date: string; expiry_date: string; status: string; days_to_expiry: number; scan_count: number;
}
interface Emp { emp_id: number; name: string }
const STATUSES = ["ACTIVE", "INACTIVE", "EXPIRED", "LOST"];
type Form = { emp_id: string; card_no: string; issue_date: string; expiry_date: string; status: string };

export default function CardsPage() {
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Card[]>("/api/cards", { search: q, status });
  const { data: emps } = useApi<Emp[]>("/api/employees", { sort: "name" });

  const [editing, setEditing] = useState<Card | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Form>({ emp_id: "", card_no: "", issue_date: "", expiry_date: "", status: "ACTIVE" });
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Card | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const today = new Date().toISOString().slice(0, 10);
  const openNew = () => {
    setEditing(null);
    setForm({ emp_id: "", card_no: "", issue_date: today, expiry_date: new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10), status: "ACTIVE" });
    setFormErr(null); setOpen(true);
  };
  const openEdit = (c: Card) => {
    setEditing(c);
    setForm({ emp_id: String(c.emp_id), card_no: c.card_no, issue_date: c.issue_date, expiry_date: c.expiry_date, status: c.status });
    setFormErr(null); setOpen(true);
  };

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    if (!form.emp_id) return setFormErr("Choose the employee who owns this card.");
    if (form.card_no.trim().length < 3) return setFormErr("Card number must have at least 3 characters.");
    if (!form.expiry_date || (form.issue_date && form.expiry_date <= form.issue_date)) return setFormErr("Expiry date must be after the issue date.");
    setBusy(true);
    try {
      const body = { ...form, emp_id: Number(form.emp_id), issue_date: form.issue_date || null };
      if (editing) await api.put(`/api/cards/${editing.card_id}`, body);
      else await api.post("/api/cards", body);
      setMsg(editing ? `Card ${form.card_no} updated.` : `Card ${form.card_no.toUpperCase()} issued.`);
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
      await api.del(`/api/cards/${toDelete.card_id}`);
      setMsg(`Card ${toDelete.card_no} deleted.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Card>[] = [
    { key: "card_id", label: "ID" },
    { key: "card_no", label: "Card no.", render: (c) => <span className="font-mono font-medium">{c.card_no}</span> },
    { key: "employee", label: "Employee", render: (c) => <>{c.employee} <span className="text-xs text-slate-400">#{c.emp_id}</span></> },
    { key: "department", label: "Department" },
    { key: "issue_date", label: "Issued", render: (c) => fmtDate(c.issue_date) },
    { key: "expiry_date", label: "Expires", render: (c) => <>{fmtDate(c.expiry_date)}{c.days_to_expiry >= 0 && c.days_to_expiry <= 60 && <span className="ml-1 text-xs text-amber-600">({c.days_to_expiry} d)</span>}</> },
    { key: "status", label: "Status", render: (c) => <Badge value={c.status} /> },
    { key: "scan_count", label: "Scans" },
  ];
  if (isAdmin)
    columns.push({
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (c) => (
        <div className="flex justify-end gap-1">
          <button className="btn-ghost" onClick={() => openEdit(c)}>Edit</button>
          <button className="btn-ghost text-rose-600" onClick={() => setToDelete(c)}>Delete</button>
        </div>
      ),
    });

  return (
    <>
      <PageHeader title="Access Cards" subtitle="R2 Cards · expired cards are flagged automatically by trigger trg_card_auto_expire"
        actions={isAdmin && <button className="btn-primary" onClick={openNew}>+ Issue card</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search card no. or employee…" />
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(c) => c.card_id} />

      <Modal title={editing ? `Edit card ${editing.card_no}` : "Issue card"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field label="Employee">
            <select className="input" value={form.emp_id} onChange={(e) => setForm({ ...form, emp_id: e.target.value })}>
              <option value="">Select employee…</option>
              {emps?.map((e) => <option key={e.emp_id} value={e.emp_id}>{e.name} (#{e.emp_id})</option>)}
            </select>
          </Field>
          <Field label="Card number"><input className="input font-mono" value={form.card_no} onChange={(e) => setForm({ ...form, card_no: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Issue date"><input type="date" className="input" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} /></Field>
            <Field label="Expiry date"><input type="date" className="input" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></Field>
          </div>
          <Field label="Status">
            <select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete card" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete card <b>{toDelete?.card_no}</b>? Cards with scan history are protected (ON DELETE RESTRICT) and an employee&apos;s last card cannot be removed (total participation).</>} />
    </>
  );
}
