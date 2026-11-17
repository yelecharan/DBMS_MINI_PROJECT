"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";

interface Employee {
  emp_id: number; name: string; department: string; phone: string | null;
  card_count: number; active_cards: number; scan_count: number; card_numbers: string | null;
}
type Form = { name: string; department: string; phone: string; card_no: string; expiry_date: string };

const nextYear = () => new Date(Date.now() + 365 * 864e5).toISOString().slice(0, 10);
const empty: Form = { name: "", department: "", phone: "", card_no: "", expiry_date: nextYear() };

function validate(f: Form, isNew: boolean): string | null {
  if (f.name.trim().length < 2) return "Name must have at least 2 characters.";
  if (f.department.trim().length < 2) return "Department is required.";
  if (!/^\+?[0-9]{10,13}$/.test(f.phone)) return "Phone must be 10–13 digits (optional leading +).";
  if (isNew) {
    if (f.card_no.trim().length < 3) return "A first access card number is required (every employee must own a card).";
    if (!f.expiry_date || f.expiry_date <= new Date().toISOString().slice(0, 10)) return "Card expiry must be in the future.";
  }
  return null;
}

export default function EmployeesPage() {
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState("");
  const [dept, setDept] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Employee[]>("/api/employees", { search: q, department: dept });
  const { data: departments } = useApi<string[]>("/api/employees/departments");

  const [editing, setEditing] = useState<Employee | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Form>(empty);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Employee | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const openNew = () => { setEditing(null); setForm({ ...empty, expiry_date: nextYear() }); setFormErr(null); setOpen(true); };
  const openEdit = (e: Employee) => { setEditing(e); setForm({ ...empty, name: e.name, department: e.department, phone: e.phone ?? "" }); setFormErr(null); setOpen(true); };

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    const v = validate(form, !editing);
    if (v) return setFormErr(v);
    setBusy(true);
    try {
      if (editing) {
        await api.put(`/api/employees/${editing.emp_id}`, { name: form.name, department: form.department, phone: form.phone });
        setMsg(`Employee #${editing.emp_id} updated.`);
      } else {
        const r = await api.post<{ emp_id: number }>("/api/employees", form);
        setMsg(`Employee #${r.emp_id} created with card ${form.card_no.toUpperCase()} (procedure sp_add_employee_with_card).`);
      }
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
      await api.del(`/api/employees/${toDelete.emp_id}`);
      setMsg(`Employee #${toDelete.emp_id} deleted.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  async function deactivate(e: Employee) {
    try {
      const r = await api.post<{ deactivated: number }>(`/api/employees/${e.emp_id}/deactivate-cards`);
      setMsg(`${r.deactivated} card(s) of ${e.name} deactivated (procedure sp_deactivate_employee_cards).`);
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const columns: Column<Employee>[] = [
    { key: "emp_id", label: "ID" },
    { key: "name", label: "Name", render: (e) => <span className="font-medium">{e.name}</span> },
    { key: "department", label: "Department" },
    { key: "phone", label: "Phone", render: (e) => e.phone ?? <span className="text-xs italic text-slate-400">hidden</span> },
    { key: "card_numbers", label: "Cards", render: (e) => <span className="text-xs">{e.card_numbers ?? "—"} <span className="text-slate-400">({e.active_cards} active)</span></span>, sortValue: (e) => e.card_count },
    { key: "scan_count", label: "Scans" },
  ];
  if (isAdmin)
    columns.push({
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (e) => (
        <div className="flex justify-end gap-1">
          <button className="btn-ghost" onClick={() => openEdit(e)}>Edit</button>
          <button className="btn-ghost" onClick={() => deactivate(e)} disabled={!e.active_cards}>Block cards</button>
          <button className="btn-ghost text-rose-600" onClick={() => setToDelete(e)}>Delete</button>
        </div>
      ),
    });

  return (
    <>
      <PageHeader title="Employees" subtitle="R1 Employees · every employee must own at least one card (total participation)"
        actions={isAdmin && <button className="btn-primary" onClick={openNew}>+ Add employee</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search name or phone…" />
        <Select value={dept} onChange={setDept} options={departments ?? []} placeholder="All departments" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(e) => e.emp_id} />

      <Modal title={editing ? `Edit employee #${editing.emp_id}` : "Add employee"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          <Field label="Full name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Department">
              <input className="input" list="depts" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
              <datalist id="depts">{departments?.map((d) => <option key={d} value={d} />)}</datalist>
            </Field>
            <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          </div>
          {!editing && (
            <div className="grid grid-cols-2 gap-3 rounded-md bg-slate-50 p-3">
              <Field label="First card number"><input className="input" placeholder="GS-2001" value={form.card_no} onChange={(e) => setForm({ ...form, card_no: e.target.value })} /></Field>
              <Field label="Card expiry"><input className="input" type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></Field>
            </div>
          )}
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete employee" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete <b>{toDelete?.name}</b> and their cards (ON DELETE CASCADE)? Employees whose cards have scan history cannot be deleted – the audit trail is protected by ON DELETE RESTRICT.</>} />
    </>
  );
}
