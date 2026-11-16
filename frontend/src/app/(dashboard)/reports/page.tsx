'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card, StatCard } from '@/components/ui/Card';
import { OverviewStats, TrendPoint, GateStat, SeverityBreakdown } from '@/types';
import { BarChart3, TrendingUp, Shield, AlertTriangle, Download } from 'lucide-react';

export default function ReportsPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [gates, setGates] = useState<GateStat[]>([]);
  const [severity, setSeverity] = useState<SeverityBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t, g, sv] = await Promise.all([
        fetchApi<OverviewStats>('/api/analytics/overview'),
        fetchApi<TrendPoint[]>('/api/analytics/trends'),
        fetchApi<GateStat[]>('/api/analytics/gates'),
        fetchApi<SeverityBreakdown>('/api/analytics/severity'),
      ]);
      setStats(s); setTrends(t); setGates(g); setSeverity(sv);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const maxCount = Math.max(...gates.map(g => g.incident_count), 1);
  const maxRisk = Math.max(...gates.map(g => g.avg_risk), 1);
  const totalIncidents = (severity?.critical ?? 0) + (severity?.high ?? 0) +
    (severity?.medium ?? 0) + (severity?.low ?? 0);

  const exportCSV = () => {
    if (!gates.length) return;
    const header = 'Gate,Code,Site,Incidents,Avg Risk';
    const rows = gates.map(g =>
      `"${g.gate_name}","${g.gate_code}","${g.site_name}",${g.incident_count},${(g.avg_risk ?? 0).toFixed(1)}`
    );
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'gatesentry_gate_report.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Security Reports" subtitle="Analytics summary and incident trends" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Summary KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Total Incidents" value={totalIncidents} icon={<Shield className="w-5 h-5" />} color="blue" />
          <StatCard title="Avg Risk Score" value={(stats?.average_risk_score ?? 0).toFixed(1)} icon={<AlertTriangle className="w-5 h-5" />} color="orange" />
          <StatCard title="Total Access Events" value={stats?.total_access_events ?? 0} icon={<BarChart3 className="w-5 h-5" />} color="purple" />
          <StatCard title="Avg Resolution (hrs)" value={(stats?.average_resolution_hours ?? 0).toFixed(1)} icon={<TrendingUp className="w-5 h-5" />} color="green" />
        </div>

        {/* Access Event Summary */}
        <Card>
          <h3 className="font-semibold text-slate-800 text-sm mb-4">Access Control Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Successful Entries', value: stats?.successful_entries ?? 0, color: 'text-emerald-700' },
              { label: 'Denied Entries', value: stats?.denied_entries ?? 0, color: 'text-red-700' },
              { label: 'Observed Crossings', value: stats?.total_observed_crossings ?? 0, color: 'text-blue-700' },
              { label: 'Unauthorized Entries', value: stats?.unauthorized_entry_incidents ?? 0, color: 'text-orange-700' },
            ].map(item => (
              <div key={item.label} className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
                <p className={`text-2xl font-black ${item.color}`}>{item.value}</p>
                <p className="text-xs text-slate-500 mt-1">{item.label}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* 7-Day Trend Full */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-800 text-sm">7-Day Incident Trend</h3>
          </div>
          {loading ? (
            <div className="h-32 bg-slate-100 rounded animate-pulse" />
          ) : trends.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">No trend data available</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-100">
                    <th className="text-left pb-2">Date</th>
                    <th className="text-right pb-2">Total</th>
                    <th className="text-right pb-2">Tailgating</th>
                    <th className="text-right pb-2">Unauthorized</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trends.map(t => (
                    <tr key={t.date} className="hover:bg-slate-50">
                      <td className="py-2 font-medium text-slate-700">
                        {new Date(t.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                      </td>
                      <td className="py-2 text-right font-bold text-blue-700">{t.incidents_count}</td>
                      <td className="py-2 text-right text-orange-600">{t.tailgating_count}</td>
                      <td className="py-2 text-right text-red-600">{t.unauthorized_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Gate Rankings */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-800 text-sm">Gate Incident Rankings</h3>
            <button
              onClick={exportCSV}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors text-slate-600"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-slate-100 rounded animate-pulse" />)}
            </div>
          ) : (
            <div className="space-y-3">
              {gates.map((g, i) => (
                <div key={g.gate_id} className="flex items-center gap-4">
                  <span className="w-5 text-xs font-bold text-slate-400 shrink-0">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-medium text-slate-700 truncate">{g.gate_name}</span>
                      <span className="text-xs text-slate-500 shrink-0 ml-2">{g.incident_count} incidents</span>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${(g.incident_count / maxCount) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400 shrink-0 w-16 text-right">
                        avg risk {(g.avg_risk ?? 0).toFixed(0)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Severity Breakdown table */}
        <Card>
          <h3 className="font-semibold text-slate-800 text-sm mb-4">Severity Distribution</h3>
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'CRITICAL', count: severity?.critical ?? 0, bg: 'bg-red-50 border-red-200', text: 'text-red-700', pct: totalIncidents },
              { label: 'HIGH', count: severity?.high ?? 0, bg: 'bg-orange-50 border-orange-200', text: 'text-orange-700', pct: totalIncidents },
              { label: 'MEDIUM', count: severity?.medium ?? 0, bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', pct: totalIncidents },
              { label: 'LOW', count: severity?.low ?? 0, bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700', pct: totalIncidents },
            ].map(({ label, count, bg, text, pct }) => (
              <div key={label} className={`p-4 rounded-xl border text-center ${bg}`}>
                <p className={`text-3xl font-black ${text}`}>{count}</p>
                <p className={`text-xs font-semibold ${text} mt-1`}>{label}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {pct > 0 ? ((count / pct) * 100).toFixed(0) : 0}%
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
