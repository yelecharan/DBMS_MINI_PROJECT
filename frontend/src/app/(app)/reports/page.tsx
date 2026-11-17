"use client";

import Link from "next/link";
import { useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Report } from "@/lib/types";
import { ConfirmDialog, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced } from "@/components/ui";

const FILE_TYPES = ["application/pdf", "image/jpeg", "image/png", "text/plain"];

export default function ReportsPage() {
  const { isAdmin, user, canWrite } = useAuth();
  const [search, setSearch] = useState("");
  const [incident, setIncident] = useState("");
  const [order, setOrder] = useState("desc");
  const q = useDebounced(search);
  const qi = useDebounced(incident);
  const { data, loading, error, reload, setError } = useApi<Report[]>("/api/reports", { search: q, incident_id: qi, order });

  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Report | null>(null);
  const [form, setForm] = useState({ incident_id: "", description: "", file_name: "", file_type: FILE_TYPES[0] });
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Report | null>(null);
  const [attachFor, setAttachFor] = useState<Report | null>(null);
  const [att, setAtt] = useState({ file_name: "", file_type: FILE_TYPES[0], note: "" });

  async function save(ev: React.FormEvent) {
    ev.preventDefault();
    if (!editing && !(Number(form.incident_id) > 0)) return setFormErr("Enter the incident_id from PostgreSQL.");
    if (form.description.trim().length < 10) return setFormErr("Description must be at least 10 characters.");
    setBusy(true);
    try {
      if (editing) {
        await api.put(`/api/reports/${editing.report_id}`, { description: form.description });
        setMsg(`Report ${editing.report_id} updated.`);
      } else {
        const r = await api.post<Report>("/api/reports", {
          incident_id: Number(form.incident_id), description: form.description,
          attachments: form.file_name.trim() ? [{ file_name: form.file_name.trim(), file_type: form.file_type }] : [],
        });
        setMsg(`Report ${r.report_id} created.`);
      }
      setOpen(false);
      reload();
    } catch (e) {
      setFormErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addAttachment(ev: React.FormEvent) {
    ev.preventDefault();
    if (!att.file_name.trim()) return setFormErr("File name is required.");
    try {
      await api.post(`/api/reports/${attachFor!.report_id}/attachments`, att);
      setMsg(`Attachment added to ${attachFor!.report_id} ($push).`);
      setAttachFor(null);
      reload();
    } catch (e) {
      setFormErr((e as Error).message);
    }
  }

  async function removeAttachment(r: Report, file: string) {
    try {
      await api.del(`/api/reports/${r.report_id}/attachments/${encodeURIComponent(file)}`);
      setMsg(`Attachment ${file} removed ($pull).`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await api.del(`/api/reports/${toDelete.report_id}`);
      setMsg(`Report ${toDelete.report_id} deleted.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const canEdit = (r: Report) => isAdmin || r.reported_by.username === user?.username;

  return (
    <>
      <PageHeader title="Incident Reports" subtitle="MongoDB collection Report · nested reported_by document, attachments array, full-text index"
        actions={canWrite && <button className="btn-primary" onClick={() => { setEditing(null); setForm({ incident_id: "", description: "", file_name: "", file_type: FILE_TYPES[0] }); setFormErr(null); setOpen(true); }}>+ New report</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Full-text search ($text)…" />
        <input className="input w-36" type="number" min={1} placeholder="Incident #" value={incident} onChange={(e) => setIncident(e.target.value)} />
        <Select value={order} onChange={setOrder} options={[{ value: "desc", label: "Newest first" }, { value: "asc", label: "Oldest first" }]} />
      </div>

      {loading ? <p className="text-slate-400">Loading…</p> : data?.length === 0 ? <p className="card p-8 text-center text-slate-400">No reports found.</p> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data?.map((r) => (
            <article key={r.report_id} className="card p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-mono text-xs text-slate-500">{r.report_id}</span>
                  <span className="mx-2 text-slate-300">·</span>
                  <Link href={`/incidents/${r.incident_id}`} className="text-sm text-indigo-600 hover:underline">Incident #{r.incident_id}</Link>
                </div>
                <span className="text-xs text-slate-400">{fmtDateTime(r.timestamp)}</span>
              </div>
              <p className="mt-2 text-sm">{r.description}</p>
              <p className="mt-2 text-xs text-slate-500">Reported by <b>{r.reported_by.username}</b> ({r.reported_by.role}){r.updated_at && ` · edited ${fmtDateTime(r.updated_at)}`}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {r.attachments.map((a) => (
                  <span key={a.file_name} className="inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                    📎 {a.file_name}
                    {canEdit(r) && <button onClick={() => removeAttachment(r, a.file_name)} className="font-bold opacity-60 hover:opacity-100" aria-label="Remove attachment">×</button>}
                  </span>
                ))}
              </div>
              <div className="mt-3 flex gap-1 border-t border-slate-100 pt-2">
                {canEdit(r) && <button className="btn-ghost" onClick={() => { setEditing(r); setForm({ ...form, description: r.description }); setFormErr(null); setOpen(true); }}>Edit</button>}
                {canEdit(r) && <button className="btn-ghost" onClick={() => { setAttachFor(r); setAtt({ file_name: "", file_type: FILE_TYPES[0], note: "" }); setFormErr(null); }}>+ Attachment</button>}
                {isAdmin && <button className="btn-ghost text-rose-600" onClick={() => setToDelete(r)}>Delete</button>}
              </div>
            </article>
          ))}
        </div>
      )}

      <Modal title={editing ? `Edit ${editing.report_id}` : "New incident report"} open={open} onClose={() => setOpen(false)}>
        <form onSubmit={save} className="space-y-3" noValidate>
          {!editing && <Field label="Incident ID (PostgreSQL)"><input className="input" type="number" min={1} value={form.incident_id} onChange={(e) => setForm({ ...form, incident_id: e.target.value })} /></Field>}
          <Field label="Description"><textarea className="input" rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          {!editing && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Attachment (optional)"><input className="input" placeholder="logbook.pdf" value={form.file_name} onChange={(e) => setForm({ ...form, file_name: e.target.value })} /></Field>
              <Field label="Type"><select className="input" value={form.file_type} onChange={(e) => setForm({ ...form, file_type: e.target.value })}>{FILE_TYPES.map((t) => <option key={t}>{t}</option>)}</select></Field>
            </div>
          )}
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>Save</button></div>
        </form>
      </Modal>

      <Modal title={`Add attachment to ${attachFor?.report_id}`} open={!!attachFor} onClose={() => setAttachFor(null)}>
        <form onSubmit={addAttachment} className="space-y-3" noValidate>
          <Field label="File name"><input className="input" value={att.file_name} onChange={(e) => setAtt({ ...att, file_name: e.target.value })} /></Field>
          <Field label="Type"><select className="input" value={att.file_type} onChange={(e) => setAtt({ ...att, file_type: e.target.value })}>{FILE_TYPES.map((t) => <option key={t}>{t}</option>)}</select></Field>
          <Field label="Note"><input className="input" value={att.note} onChange={(e) => setAtt({ ...att, note: e.target.value })} /></Field>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn-secondary" onClick={() => setAttachFor(null)}>Cancel</button><button className="btn-primary">Add</button></div>
        </form>
      </Modal>

      <ConfirmDialog open={!!toDelete} title="Delete report" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete report <b>{toDelete?.report_id}</b> from MongoDB?</>} />
    </>
  );
}
