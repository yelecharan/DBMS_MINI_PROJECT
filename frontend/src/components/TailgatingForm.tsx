"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { METHODS } from "@/lib/types";
import { Field, Modal } from "./ui";


interface Scan { scan_id: number; gate_name: string; employee: string; card_no: string; scan_time: string }

/** Guard compares the people observed with the authorised scans for one card scan.
 *  Backend: fn_report_tailgating() (PostgreSQL) + Observation & Alert documents (MongoDB). */
export function TailgatingForm({ scan, onClose, onDone }: { scan: Scan | null; onClose: () => void; onDone: (msg: string) => void }) {
  const [authorized, setAuthorized] = useState<number | null>(null);
  const [observed, setObserved] = useState("");
  const [method, setMethod] = useState(METHODS[0]);
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!scan) return;
    setObserved(""); setNotes(""); setErr(null); setAuthorized(null);
    api.get<{ authorized_count: number }>(`/api/access-logs/${scan.scan_id}/authorized-count`)
      .then((r) => setAuthorized(r.authorized_count))
      .catch((e) => setErr(e.message));
  }, [scan]);

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const n = Number(observed);
    if (!Number.isInteger(n) || n < 1 || n > 100) return setErr("Observed people must be a whole number between 1 and 100.");
    if (authorized !== null && n <= authorized) return setErr(`No tailgating: ${n} observed vs ${authorized} authorised scan(s).`);
    setBusy(true);
    try {
      const r = await api.post<{ incident: { incident_id: number; severity: string } }>("/api/incidents/report-tailgating", {
        scan_id: scan!.scan_id, observed_count: n, authorized_count: authorized, method, notes,
      });
      onDone(`Incident #${r.incident.incident_id} (${r.incident.severity}) created in PostgreSQL; observation and alert stored in MongoDB.`);
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Report suspected tailgating" open={!!scan} onClose={onClose}>
      {scan && (
        <form onSubmit={submit} className="space-y-3" noValidate>
          <div className="rounded-md bg-slate-50 p-3 text-sm">
            Scan <b>#{scan.scan_id}</b> · {scan.card_no} ({scan.employee}) at <b>{scan.gate_name}</b>
            <div className="mt-1 text-slate-500">
              Authorised scans at this gate within ±10 s (fn_authorized_count):{" "}
              <b className="text-slate-900">{authorized ?? "…"}</b>
            </div>
          </div>
          <Field label="People observed passing through">
            <input className="input" type="number" min={1} value={observed} onChange={(e) => setObserved(e.target.value)} autoFocus />
          </Field>
          <Field label="Observation method">
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map((m) => <option key={m} value={m}>{m.replaceAll("_", " ")}</option>)}
            </select>
          </Field>
          <Field label="Notes"><textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} /></Field>
          {err && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={busy || authorized === null}>{busy ? "Saving…" : "Report incident"}</button>
          </div>
        </form>
      )}
    </Modal>
  );
}
