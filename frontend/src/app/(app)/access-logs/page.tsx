"use client";

import Link from "next/link";
import { useState } from "react";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { Badge, ConfirmDialog, DataTable, Field, Modal, Notice, PageHeader, SearchBox, Select, useDebounced, type Column } from "@/components/ui";
import { TailgatingForm } from "@/components/TailgatingForm";

interface Log {
  scan_id: number; scan_time: string; access_result: string; card_id: number; card_no: string;
  emp_id: number; employee: string; department: string; gate_id: number; gate_name: string; incident_count: number;
}
interface Cascade { incidents_removed: number; mongo_documents_removed: Record<string, number> }
interface Gate { gate_id: number; gate_name: string; status: string }

export default function AccessLogsPage() {
  const { isAdmin, canWrite } = useAuth();
  const [search, setSearch] = useState("");
  const [gate, setGate] = useState("");
  const [result, setResult] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const q = useDebounced(search);
  const { data, loading, error, reload, setError } = useApi<Log[]>("/api/access-logs", { search: q, gate_id: gate, result, date_from: from, date_to: to });
  const { data: gates } = useApi<Gate[]>("/api/gates");

  const [scanOpen, setScanOpen] = useState(false);
  const [scanForm, setScanForm] = useState({ card_no: "", gate_id: "" });
  const [scanErr, setScanErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [tailgate, setTailgate] = useState<Log | null>(null);
  const [toDelete, setToDelete] = useState<Log | null>(null);

  async function recordScan(ev: React.FormEvent) {
    ev.preventDefault();
    if (scanForm.card_no.trim().length < 3) return setScanErr("Enter the card number that was scanned.");
    if (!scanForm.gate_id) return setScanErr("Choose a gate.");
    setBusy(true);
    try {
      const r = await api.post<{ scan_id: number; access_result: string }>("/api/access-logs", { card_no: scanForm.card_no, gate_id: Number(scanForm.gate_id) });
      setMsg(`Scan #${r.scan_id} recorded → ${r.access_result} (decided by trigger trg_validate_access_log).`);
      setScanOpen(false);
      reload();
    } catch (e) {
      setScanErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      const r = await api.del<Cascade>(`/api/access-logs/${toDelete.scan_id}`);
      setMsg(`Scan #${toDelete.scan_id} deleted; ` + `${r.incidents_removed} incident(s) and ${Object.values(r.mongo_documents_removed).reduce((a, b) => a + b, 0)} MongoDB document(s) removed with it.`);
      reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  const columns: Column<Log>[] = [
    { key: "scan_id", label: "Scan" },
    { key: "scan_time", label: "Time", render: (l) => fmtDateTime(l.scan_time) },
    { key: "employee", label: "Employee", render: (l) => <>{l.employee}<div className="text-xs text-slate-400">{l.department}</div></> },
    { key: "card_no", label: "Card", render: (l) => <span className="font-mono">{l.card_no}</span> },
    { key: "gate_name", label: "Gate" },
    { key: "access_result", label: "Result", render: (l) => <Badge value={l.access_result} /> },
    { key: "incident_count", label: "Incidents", render: (l) => l.incident_count ? <Link href={`/incidents?search=${encodeURIComponent(l.card_no)}`} className="font-semibold text-orange-600">{l.incident_count}</Link> : <span className="text-slate-300">0</span> },
    {
      key: "actions", label: "", sortable: false, className: "text-right",
      render: (l) => (
        <div className="flex justify-end gap-1">
          {canWrite && <button className="btn-ghost text-orange-600" onClick={() => setTailgate(l)}>Report tailgating</button>}
          {isAdmin && <button className="btn-ghost text-rose-600" onClick={() => setToDelete(l)}>Delete</button>}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Access Logs" subtitle="R4 Access_Logs · 4-table JOIN (logs ⋈ cards ⋈ employees ⋈ gates)"
        actions={canWrite && <button className="btn-primary" onClick={() => { setScanForm({ card_no: "", gate_id: "" }); setScanErr(null); setScanOpen(true); }}>+ Record card scan</button>} />
      {msg && <Notice kind="success" onClose={() => setMsg(null)}>{msg}</Notice>}
      {error && <Notice onClose={() => setError(null)}>{error}</Notice>}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SearchBox value={search} onChange={setSearch} placeholder="Search employee or card…" />
        <Select value={gate} onChange={setGate} options={(gates ?? []).map((g) => ({ value: String(g.gate_id), label: g.gate_name }))} placeholder="All gates" />
        <Select value={result} onChange={setResult} options={["GRANTED", "DENIED"]} placeholder="All results" />
        <input type="date" className="input w-auto" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From date" />
        <span className="text-slate-400">to</span>
        <input type="date" className="input w-auto" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To date" />
      </div>
      <DataTable rows={data ?? []} columns={columns} loading={loading} rowKey={(l) => l.scan_id} />

      <Modal title="Record card scan" open={scanOpen} onClose={() => setScanOpen(false)}>
        <form onSubmit={recordScan} className="space-y-3" noValidate>
          <Field label="Card number" hint="Inactive, lost or expired cards and gates not ACTIVE are automatically DENIED">
            <input className="input font-mono" placeholder="GS-1001" value={scanForm.card_no} onChange={(e) => setScanForm({ ...scanForm, card_no: e.target.value })} />
          </Field>
          <Field label="Gate">
            <select className="input" value={scanForm.gate_id} onChange={(e) => setScanForm({ ...scanForm, gate_id: e.target.value })}>
              <option value="">Select gate…</option>
              {gates?.map((g) => <option key={g.gate_id} value={g.gate_id}>{g.gate_name} ({g.status})</option>)}
            </select>
          </Field>
          {scanErr && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{scanErr}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setScanOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Record scan"}</button>
          </div>
        </form>
      </Modal>

      <TailgatingForm scan={tailgate} onClose={() => setTailgate(null)} onDone={(m) => { setMsg(m); reload(); }} />

      <ConfirmDialog open={!!toDelete} title="Delete scan" busy={busy} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={<>Delete scan <b>#{toDelete?.scan_id}</b>? Its incidents are deleted too (ON DELETE CASCADE), with the linked MongoDB documents.</>} />
    </>
  );
}
