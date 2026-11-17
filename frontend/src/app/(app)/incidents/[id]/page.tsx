"use client";

import Link from "next/link";
import { use, useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { METHODS, type Alert, type Incident, type Observation, type Report } from "@/lib/types";
import { Badge, Field, Modal, Notice, PageHeader } from "@/components/ui";

interface Detail { incident: Incident; observations: Observation[]; reports: Report[]; alerts: Alert[] }

export default function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, canWrite } = useAuth();
  const { data, loading, error, reload, setError } = useApi<Detail>(`/api/incidents/${id}`);
  const [msg, setMsg] = useState<string | null>(null);
  const [repOpen, setRepOpen] = useState(false);
  const [obsOpen, setObsOpen] = useState(false);
  const [rep, setRep] = useState({ description: "", file_name: "", file_type: "application/pdf" });
  const [obs, setObs] = useState({ method: METHODS[0], observed_count: "", authorized_count: "", notes: "" });
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function addReport(ev: React.FormEvent) {
    ev.preventDefault();
    if (rep.description.trim().length < 10) return setFormErr("Description must be at least 10 characters.");
    setBusy(true);
    try {
      await api.post("/api/reports", {
        incident_id: Number(id), description: rep.description,
        attachments: rep.file_name.trim() ? [{ file_name: rep.file_name.trim(), file_type: rep.file_type }] : [],
      });
      setMsg("Report saved to MongoDB (Report collection).");
      setRepOpen(false);
      reload();
    } catch (e) {
      setFormErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addObservation(ev: React.FormEvent) {
    ev.preventDefault();
    const o = Number(obs.observed_count), a = Number(obs.authorized_count);
    if (!Number.isInteger(o) || !Number.isInteger(a) || o < 0 || a < 0 || obs.observed_count === "" || obs.authorized_count === "")
      return setFormErr("Counts must be whole numbers ≥ 0.");
    setBusy(true);
    try {
      await api.post("/api/observations", { incident_id: Number(id), method: obs.method, observed_count: o, authorized_count: a, notes: obs.notes });
      setMsg("Observation saved to MongoDB (Observations collection).");
      setObsOpen(false);
      reload();
    } catch (e) {
      setFormErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function ack(a: Alert) {
    try {
      await api.patch(`/api/alerts/${a.alert_id}/ack`, { comment: "Acknowledged from incident page" });
      setMsg(`Alert ${a.alert_id} acknowledged by ${user?.username}.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (loading && !data) return <p className="text-slate-400">Loading…</p>;
  if (!data) return <Notice>{error ?? "Incident not found"}</Notice>;
  const i = data.incident;

  return (
    <>
      <PageHeader title={`Incident #${i.incident_id}`} subtitle="PostgreSQL row + every MongoDB document referencing this incident_id"
        actions={<>
          <Link href="/incidents" className="btn-secondary">← All incidents</Link>
          {canWrite && <button className="btn-secondary" onClick={() => { setObs({ method: METHODS[0], observed_count: "", authorized_count: "", notes: "" }); setFormErr(null); setObsOpen(true); }}>+ Observation</button>}
          {canWrite && <button className="btn-primary" onClick={() => { setRep({ description: "", file_name: "", file_type: "application/pdf" }); setFormErr(null); setRepOpen(true); }}>+ Incident report</button>}
        </>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}

      <section className="card mb-6 grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <Info label="Severity"><Badge value={i.severity} /></Info>
        <Info label="Status"><Badge value={i.status} /></Info>
        <Info label="Detected">{fmtDateTime(i.detected_time)}</Info>
        <Info label="Gate">{i.gate_name}<div className="text-xs text-slate-400">{i.location}</div></Info>
        <Info label="Scan">#{i.scan_id} · {fmtDateTime(i.scan_time)} <Badge value={i.access_result} /></Info>
        <Info label="Card">{i.card_no}</Info>
        <Info label="Card holder">{i.employee}<div className="text-xs text-slate-400">{i.department}</div></Info>
        <Info label="Source">PostgreSQL · 5-table JOIN</Info>
      </section>

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="card p-5">
          <h2 className="mb-3 font-semibold">Observations <span className="text-xs font-normal text-slate-400">MongoDB</span></h2>
          {data.observations.length === 0 && <p className="text-sm text-slate-400">None yet.</p>}
          <ul className="space-y-3">
            {data.observations.map((o) => (
              <li key={o.obs_id} className="rounded-md border border-slate-100 p-3 text-sm">
                <div className="flex justify-between"><span className="font-mono text-xs">{o.obs_id}</span><span className="text-xs text-slate-400">{fmtDateTime(o.timestamp)}</span></div>
                <p className="mt-1"><b>{o.observed_count}</b> observed vs <b>{o.authorized_count}</b> authorised → <b className="text-rose-600">+{o.observed_count - o.authorized_count}</b></p>
                <p className="text-xs text-slate-500">{o.method.replaceAll("_", " ")} · by {o.observed_by}</p>
                {o.notes && <p className="mt-1 text-xs text-slate-600">{o.notes}</p>}
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          <h2 className="mb-3 font-semibold">Reports <span className="text-xs font-normal text-slate-400">MongoDB</span></h2>
          {data.reports.length === 0 && <p className="text-sm text-slate-400">None yet.</p>}
          <ul className="space-y-3">
            {data.reports.map((r) => (
              <li key={r.report_id} className="rounded-md border border-slate-100 p-3 text-sm">
                <div className="flex justify-between"><span className="font-mono text-xs">{r.report_id}</span><span className="text-xs text-slate-400">{fmtDateTime(r.timestamp)}</span></div>
                <p className="mt-1">{r.description}</p>
                <p className="mt-1 text-xs text-slate-500">by {r.reported_by.username} ({r.reported_by.role})</p>
                {r.attachments.length > 0 && <p className="mt-1 text-xs text-indigo-600">📎 {r.attachments.map((a) => a.file_name).join(", ")}</p>}
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          <h2 className="mb-3 font-semibold">Alerts <span className="text-xs font-normal text-slate-400">MongoDB</span></h2>
          {data.alerts.length === 0 && <p className="text-sm text-slate-400">None.</p>}
          <ul className="space-y-3">
            {data.alerts.map((a) => (
              <li key={a.alert_id} className="rounded-md border border-slate-100 p-3 text-sm">
                <div className="flex items-center justify-between"><Badge value={a.alert_type} /><Badge value={a.ack_status} /></div>
                <p className="mt-2">{a.message}</p>
                <p className="mt-1 text-xs text-slate-400">{fmtDateTime(a.alert_time)}{a.acknowledged && ` · ack by ${a.acknowledged.by}`}</p>
                {canWrite && a.ack_status === "PENDING" && <button className="btn-secondary mt-2" onClick={() => ack(a)}>Acknowledge</button>}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <Modal title="New incident report" open={repOpen} onClose={() => setRepOpen(false)}>
        <form onSubmit={addReport} className="space-y-3" noValidate>
          <Field label="Description"><textarea className="input" rows={4} value={rep.description} onChange={(e) => setRep({ ...rep, description: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Attachment name (optional)"><input className="input" placeholder="logbook.pdf" value={rep.file_name} onChange={(e) => setRep({ ...rep, file_name: e.target.value })} /></Field>
            <Field label="Type"><select className="input" value={rep.file_type} onChange={(e) => setRep({ ...rep, file_type: e.target.value })}><option>application/pdf</option><option>image/jpeg</option><option>image/png</option><option>text/plain</option></select></Field>
          </div>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setRepOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>Save report</button></div>
        </form>
      </Modal>

      <Modal title="Add observation" open={obsOpen} onClose={() => setObsOpen(false)}>
        <form onSubmit={addObservation} className="space-y-3" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <Field label="People observed"><input className="input" type="number" min={0} value={obs.observed_count} onChange={(e) => setObs({ ...obs, observed_count: e.target.value })} /></Field>
            <Field label="Authorised scans"><input className="input" type="number" min={0} value={obs.authorized_count} onChange={(e) => setObs({ ...obs, authorized_count: e.target.value })} /></Field>
          </div>
          <Field label="Method"><select className="input" value={obs.method} onChange={(e) => setObs({ ...obs, method: e.target.value })}>{METHODS.map((m) => <option key={m} value={m}>{m.replaceAll("_", " ")}</option>)}</select></Field>
          <Field label="Notes"><textarea className="input" rows={2} value={obs.notes} onChange={(e) => setObs({ ...obs, notes: e.target.value })} /></Field>
          {formErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{formErr}</p>}
          <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setObsOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>Save</button></div>
        </form>
      </Modal>
    </>
  );
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <div className="mt-1 text-sm">{children}</div>
    </div>
  );
}
