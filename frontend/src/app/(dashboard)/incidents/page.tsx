'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { SeverityBadge, StatusBadge } from '@/components/ui/Badge';
import { Incident } from '@/types';
import { ShieldAlert, Filter, RefreshCw, ChevronRight, AlertTriangle } from 'lucide-react';

const SEVERITIES = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const STATUSES = ['', 'NEW', 'ACKNOWLEDGED', 'UNDER_INVESTIGATION', 'RESOLVED', 'FALSE_POSITIVE'];
const TYPES = ['', 'TAILGATING', 'UNAUTHORIZED_ENTRY', 'LOW_CONFIDENCE', 'CONFIGURATION_ALERT'];

export default function IncidentsPage() {
  const router = useRouter();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [incidentType, setIncidentType] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (severity) params.set('severity', severity);
      if (status) params.set('status', status);
      if (incidentType) params.set('incident_type', incidentType);
      params.set('skip', String((page - 1) * pageSize));
      params.set('limit', String(pageSize));
      const data = await fetchApi<Incident[] | { items: Incident[] }>(`/api/incidents?${params}`);
      setIncidents(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [severity, status, incidentType, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [severity, status, incidentType]);

  return (
    <div className="flex flex-col h-full">
      <Header title="Incident Queue" subtitle="All detected tailgating and unauthorized entry incidents" />
      <div className="flex-1 overflow-y-auto">
        {/* Filters Bar */}
        <div className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur border-b border-slate-200 px-6 py-3 flex flex-wrap items-center gap-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={severity}
            onChange={e => setSeverity(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {SEVERITIES.map(s => <option key={s} value={s}>{s || 'All Severities'}</option>)}
          </select>
          <select
            value={status}
            onChange={e => setStatus(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATUSES.map(s => <option key={s} value={s}>{s || 'All Statuses'}</option>)}
          </select>
          <select
            value={incidentType}
            onChange={e => setIncidentType(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {TYPES.map(t => <option key={t} value={t}>{t || 'All Types'}</option>)}
          </select>
          <button
            onClick={load}
            className="ml-auto flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Table */}
        <div className="p-6">
          {error && (
            <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-4">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Severity</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Risk</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Gate</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden lg:table-cell">Auth/Obs</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden xl:table-cell">Time</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  [...Array(8)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(7)].map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-slate-100 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : incidents.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center">
                      <ShieldAlert className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                      <p className="text-slate-400 text-sm">No incidents match current filters</p>
                    </td>
                  </tr>
                ) : (
                  incidents.map(inc => (
                    <tr
                      key={inc.id}
                      onClick={() => router.push(`/incidents/${inc.id}`)}
                      className="hover:bg-blue-50/50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <SeverityBadge severity={inc.severity} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                inc.risk_score >= 80 ? 'bg-red-500' :
                                inc.risk_score >= 60 ? 'bg-orange-500' :
                                inc.risk_score >= 35 ? 'bg-amber-400' : 'bg-blue-400'
                              }`}
                              style={{ width: `${inc.risk_score}%` }}
                            />
                          </div>
                          <span className="text-xs font-bold text-slate-700">{inc.risk_score}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-medium text-slate-800 truncate max-w-[140px]">{inc.gate_name ?? '—'}</p>
                        <p className="text-xs text-slate-400 truncate max-w-[140px]">{inc.site_name}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-600 font-medium">
                          {inc.incident_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={inc.status} />
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        <span className="text-xs text-slate-600">
                          {inc.authorized_count} auth / {inc.observed_count} obs
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden xl:table-cell text-xs text-slate-400">
                        {new Date(inc.created_at).toLocaleString([], {
                          month: 'short', day: 'numeric',
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight className="w-4 h-4 text-slate-300" />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4 text-xs text-slate-500">
            <span>Showing page {page}</span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
              >
                ← Prev
              </button>
              <button
                disabled={incidents.length < pageSize}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
