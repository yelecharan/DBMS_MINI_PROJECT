"use client";

import { useEffect, useMemo, useState } from "react";

/* ---------------- Badge / status indicator ---------------- */
const TONES: Record<string, string> = {
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  GRANTED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  ACKNOWLEDGED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  LOW: "bg-sky-50 text-sky-700 ring-sky-200",
  INVESTIGATING: "bg-sky-50 text-sky-700 ring-sky-200",
  MEDIUM: "bg-amber-50 text-amber-700 ring-amber-200",
  MAINTENANCE: "bg-amber-50 text-amber-700 ring-amber-200",
  PENDING: "bg-amber-50 text-amber-700 ring-amber-200",
  OPEN: "bg-orange-50 text-orange-700 ring-orange-200",
  HIGH: "bg-orange-50 text-orange-700 ring-orange-200",
  CRITICAL: "bg-rose-50 text-rose-700 ring-rose-200",
  DENIED: "bg-rose-50 text-rose-700 ring-rose-200",
  LOST: "bg-rose-50 text-rose-700 ring-rose-200",
  EXPIRED: "bg-rose-50 text-rose-700 ring-rose-200",
  ESCALATION: "bg-rose-50 text-rose-700 ring-rose-200",
};

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-slate-400">—</span>;
  const tone = TONES[value] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${tone}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

/* ---------------- Page header ---------------- */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  );
}

/* ---------------- Alert banner ---------------- */
export function Notice({ kind = "error", children, onClose }: { kind?: "error" | "success"; children: React.ReactNode; onClose?: () => void }) {
  const style = kind === "error" ? "border-rose-200 bg-rose-50 text-rose-800" : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return (
    <div className={`mb-4 flex items-start justify-between gap-3 rounded-md border px-4 py-3 text-sm ${style}`}>
      <span>{children}</span>
      {onClose && (
        <button onClick={onClose} className="font-bold opacity-60 hover:opacity-100" aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  );
}

/* ---------------- Modal ---------------- */
export function Modal({ title, open, onClose, children, wide }: { title: string; open: boolean; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 pt-16" onMouseDown={onClose}>
      <div className={`card w-full ${wide ? "max-w-3xl" : "max-w-lg"} p-6`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="btn-ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ---------------- Confirmation dialog ---------------- */
export function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onCancel, busy }: {
  open: boolean; title: string; message: React.ReactNode; confirmLabel?: string; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  return (
    <Modal title={title} open={open} onClose={onCancel}>
      <div className="text-sm text-slate-600">{message}</div>
      <div className="mt-6 flex justify-end gap-2">
        <button className="btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className="btn-danger" onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button>
      </div>
    </Modal>
  );
}

/* ---------------- Form field ---------------- */
export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

/* ---------------- Data table with client-side sorting ---------------- */
export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
  sortable?: boolean;
}

export function DataTable<T extends object>({ rows, columns, loading, empty = "No records found.", rowKey }: {
  rows: T[]; columns: Column<T>[]; loading?: boolean; empty?: string; rowKey: (row: T) => string | number;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    const val = (r: T) => (col?.sortValue ? col.sortValue(r) : ((r as Record<string, unknown>)[sort.key] as string | number));
    return [...rows].sort((a, b) => {
      const x = val(a), y = val(b);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * sort.dir;
    });
  }, [rows, sort, columns]);

  const toggle = (key: string) =>
    setSort((s) => (s?.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }));

  return (
    <div className="card overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 ${c.className ?? ""}`}>
                {c.sortable === false ? (
                  c.label
                ) : (
                  <button className="inline-flex items-center gap-1 hover:text-slate-900" onClick={() => toggle(c.key)}>
                    {c.label}
                    <span className="text-[10px]">{sort?.key === c.key ? (sort.dir === 1 ? "▲" : "▼") : "↕"}</span>
                  </button>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {loading ? (
            <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-slate-400">Loading…</td></tr>
          ) : sorted.length === 0 ? (
            <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-slate-400">{empty}</td></tr>
          ) : (
            sorted.map((r) => (
              <tr key={rowKey(r)} className="hover:bg-slate-50">
                {columns.map((c) => (
                  <td key={c.key} className={`px-4 py-2.5 align-top ${c.className ?? ""}`}>
                    {c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {!loading && <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-400">{rows.length} record(s)</div>}
    </div>
  );
}

/* ---------------- Filter bar helpers ---------------- */
export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input className="input max-w-xs" placeholder={placeholder ?? "Search…"} value={value} onChange={(e) => onChange(e.target.value)} />
  );
}

export function Select({ value, onChange, options, placeholder }: {
  value: string; onChange: (v: string) => void; options: (string | { value: string; label: string })[]; placeholder?: string;
}) {
  return (
    <select className="input w-auto" value={value} onChange={(e) => onChange(e.target.value)}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => {
        const opt = typeof o === "string" ? { value: o, label: o.replaceAll("_", " ") } : o;
        return <option key={opt.value} value={opt.value}>{opt.label}</option>;
      })}
    </select>
  );
}

/* debounce a value (used for search boxes that hit the API) */
export function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
