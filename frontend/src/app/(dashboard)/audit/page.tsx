'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { AuditLog } from '@/types';
import { FileText, User, Clock, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [entityFilter, setEntityFilter] = useState('');
  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (entityFilter) params.set('entity_type', entityFilter);
      params.set('skip', String((page - 1) * pageSize));
      params.set('limit', String(pageSize));
      const data = await fetchApi<AuditLog[]>(`/api/audit-logs?${params}`);
      setLogs(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [entityFilter, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [entityFilter]);

  const actionColor = (action: string) => {
    if (action.includes('CREATE')) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
    if (action.includes('UPDATE') || action.includes('STATUS_CHANGE')) return 'text-blue-700 bg-blue-50 border-blue-200';
    if (action.includes('DELETE')) return 'text-red-700 bg-red-50 border-red-200';
    if (action.includes('LOGIN') || action.includes('LOGOUT')) return 'text-purple-700 bg-purple-50 border-purple-200';
    return 'text-slate-600 bg-slate-50 border-slate-200';
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Audit Trail" subtitle="Immutable log of all system operations and user actions" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex gap-3 mb-5">
          <select
            value={entityFilter}
            onChange={e => setEntityFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Entity Types</option>
            {['Incident', 'User', 'Employee', 'Gate', 'Session', 'Auth'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button
            onClick={load}
            className="ml-auto flex items-center gap-1.5 text-xs px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="space-y-2">
          {loading ? (
            [...Array(8)].map((_, i) => (
              <div key={i} className="h-14 bg-white rounded-xl border border-slate-200 animate-pulse" />
            ))
          ) : logs.length === 0 ? (
            <Card className="text-center py-10">
              <FileText className="w-6 h-6 text-slate-300 mx-auto mb-2" />
              <p className="text-slate-400 text-sm">No audit logs found</p>
            </Card>
          ) : (
            logs.map(log => (
              <Card key={log.id} noPad>
                <div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 rounded-xl transition-colors"
                  onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                >
                  <div className="shrink-0">
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${actionColor(log.action)}`}>
                      {log.action}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <span className="font-medium text-slate-800">{log.entity_type}</span>
                      <span className="text-slate-300">·</span>
                      <span className="font-mono text-slate-500 truncate">{log.entity_id}</span>
                    </div>
                    {log.actor_name && (
                      <div className="flex items-center gap-1 text-xs text-slate-400 mt-0.5">
                        <User className="w-3 h-3" /> {log.actor_name}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-xs text-slate-400">
                    <Clock className="w-3.5 h-3.5" />
                    {new Date(log.occurred_at).toLocaleString()}
                    {expanded === log.id
                      ? <ChevronUp className="w-3.5 h-3.5" />
                      : <ChevronDown className="w-3.5 h-3.5" />}
                  </div>
                </div>
                {expanded === log.id && (log.old_values || log.new_values) && (
                  <div className="border-t border-slate-100 px-4 py-3 grid grid-cols-2 gap-4">
                    {log.old_values && (
                      <div>
                        <p className="text-xs font-semibold text-slate-500 mb-1">Before</p>
                        <pre className="text-xs bg-red-50 border border-red-100 rounded p-2 overflow-x-auto text-red-800">
                          {JSON.stringify(log.old_values, null, 2)}
                        </pre>
                      </div>
                    )}
                    {log.new_values && (
                      <div>
                        <p className="text-xs font-semibold text-slate-500 mb-1">After</p>
                        <pre className="text-xs bg-emerald-50 border border-emerald-100 rounded p-2 overflow-x-auto text-emerald-800">
                          {JSON.stringify(log.new_values, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            ))
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 text-xs text-slate-500">
          <span>Page {page}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
            >
              ← Prev
            </button>
            <button
              disabled={logs.length < pageSize}
              onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg disabled:opacity-40 hover:bg-slate-50 transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
