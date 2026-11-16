'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card, StatCard } from '@/components/ui/Card';
import { SeverityBadge } from '@/components/ui/Badge';
import {
  OverviewStats, TrendPoint, GateStat, SeverityBreakdown, Incident
} from '@/types';
import {
  ShieldAlert, TrendingUp, Users, Activity, AlertTriangle,
  CheckCircle, Clock, Zap
} from 'lucide-react';

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [gates, setGates] = useState<GateStat[]>([]);
  const [severity, setSeverity] = useState<SeverityBreakdown | null>(null);
  const [recentIncidents, setRecentIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [s, t, g, sv, inc] = await Promise.all([
        fetchApi<OverviewStats>('/api/analytics/overview'),
        fetchApi<TrendPoint[]>('/api/analytics/trends'),
        fetchApi<GateStat[]>('/api/analytics/gates'),
        fetchApi<SeverityBreakdown>('/api/analytics/severity'),
        fetchApi<Incident[]>('/api/incidents?limit=5'),
      ]);
      setStats(s);
      setTrends(t);
      setGates(g);
      setSeverity(sv);
      setRecentIncidents(Array.isArray(inc) ? inc : (inc as any).items ?? []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={loadAll} />;

  const totalIncidents = (severity?.critical ?? 0) + (severity?.high ?? 0) +
    (severity?.medium ?? 0) + (severity?.low ?? 0);
  const maxSeverity = Math.max(
    severity?.critical ?? 0, severity?.high ?? 0,
    severity?.medium ?? 0, severity?.low ?? 0, 1
  );
  const maxTrend = Math.max(...trends.map(t => t.incidents_count), 1);

  return (
    <div className="flex flex-col">
      <Header
        title="Security Overview"
        subtitle="Real-time summary of access events, incidents and system health"
      />
      <div className="flex-1 p-6 space-y-6 overflow-y-auto">

        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Total Access Events"
            value={stats?.total_access_events ?? 0}
            icon={<Activity className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            title="Tailgating Incidents"
            value={stats?.tailgating_incidents ?? 0}
            icon={<ShieldAlert className="w-5 h-5" />}
            color="red"
          />
          <StatCard
            title="Critical Incidents"
            value={stats?.critical_incidents ?? 0}
            icon={<AlertTriangle className="w-5 h-5" />}
            color="orange"
          />
          <StatCard
            title="Avg Risk Score"
            value={(stats?.average_risk_score ?? 0).toFixed(1)}
            icon={<Zap className="w-5 h-5" />}
            color="purple"
          />
        </div>

        {/* Second KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Successful Entries"
            value={stats?.successful_entries ?? 0}
            icon={<CheckCircle className="w-5 h-5" />}
            color="green"
          />
          <StatCard
            title="Denied Entries"
            value={stats?.denied_entries ?? 0}
            icon={<AlertTriangle className="w-5 h-5" />}
            color="orange"
          />
          <StatCard
            title="Observed Crossings"
            value={stats?.total_observed_crossings ?? 0}
            icon={<Users className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            title="Avg Resolution (hrs)"
            value={(stats?.average_resolution_hours ?? 0).toFixed(1)}
            icon={<Clock className="w-5 h-5" />}
            color="purple"
          />
        </div>

        {/* Middle Row: Trend + Severity */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 7-Day Trend */}
          <Card className="md:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-800 text-sm">7-Day Incident Trend</h3>
                <p className="text-xs text-slate-500 mt-0.5">Daily incident counts by type</p>
              </div>
              <TrendingUp className="w-4 h-4 text-slate-400" />
            </div>
            {trends.length === 0 ? (
              <div className="h-32 flex items-center justify-center text-slate-400 text-sm">No trend data available</div>
            ) : (
              <div className="space-y-2">
                {trends.map(t => (
                  <div key={t.date} className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-20 shrink-0">
                      {new Date(t.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                    <div className="flex-1 relative h-6 bg-slate-100 rounded overflow-hidden">
                      <div
                        className="absolute left-0 top-0 h-full bg-blue-500/80 rounded transition-all"
                        style={{ width: `${(t.incidents_count / maxTrend) * 100}%` }}
                      />
                      <div
                        className="absolute left-0 top-0 h-full bg-orange-500/60 rounded transition-all"
                        style={{ width: `${(t.tailgating_count / maxTrend) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-slate-700 w-6 text-right">{t.incidents_count}</span>
                  </div>
                ))}
                <div className="flex gap-4 mt-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-2 rounded-sm bg-blue-500/80" /> All Incidents
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-2 rounded-sm bg-orange-500/60" /> Tailgating
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Severity Breakdown */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-800 text-sm">Severity Breakdown</h3>
                <p className="text-xs text-slate-500 mt-0.5">{totalIncidents} total incidents</p>
              </div>
            </div>
            <div className="space-y-3">
              {[
                { label: 'CRITICAL', count: severity?.critical ?? 0, color: 'bg-red-500', text: 'text-red-700' },
                { label: 'HIGH', count: severity?.high ?? 0, color: 'bg-orange-500', text: 'text-orange-700' },
                { label: 'MEDIUM', count: severity?.medium ?? 0, color: 'bg-amber-400', text: 'text-amber-700' },
                { label: 'LOW', count: severity?.low ?? 0, color: 'bg-blue-400', text: 'text-blue-700' },
              ].map(({ label, count, color, text }) => (
                <div key={label}>
                  <div className="flex justify-between items-center mb-1">
                    <span className={`text-xs font-semibold ${text}`}>{label}</span>
                    <span className="text-xs text-slate-600 font-medium">{count}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${color} rounded-full transition-all duration-500`}
                      style={{ width: `${(count / maxSeverity) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Bottom Row: Top Gates + Recent Incidents */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Top Gates by Incidents */}
          <Card>
            <h3 className="font-semibold text-slate-800 text-sm mb-4">Top Gates by Incidents</h3>
            {gates.length === 0 ? (
              <div className="text-slate-400 text-sm text-center py-6">No gate data</div>
            ) : (
              <div className="divide-y divide-slate-100">
                {gates.slice(0, 5).map((g, i) => (
                  <div key={g.gate_id} className="flex items-center gap-3 py-2.5">
                    <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center shrink-0">
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">{g.gate_name}</p>
                      <p className="text-xs text-slate-400 truncate">{g.site_name} · {g.gate_code}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-slate-800">{g.incident_count}</p>
                      <p className="text-xs text-slate-400">avg {(g.avg_risk ?? 0).toFixed(0)} risk</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Recent Incidents */}
          <Card>
            <h3 className="font-semibold text-slate-800 text-sm mb-4">Recent Incidents</h3>
            {recentIncidents.length === 0 ? (
              <div className="text-slate-400 text-sm text-center py-6">No incidents yet</div>
            ) : (
              <div className="divide-y divide-slate-100">
                {recentIncidents.map(inc => (
                  <div key={inc.id} className="py-2.5 flex items-start gap-3">
                    <SeverityBadge severity={inc.severity} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-700 truncate">{inc.gate_name ?? 'Unknown Gate'}</p>
                      <p className="text-xs text-slate-400 truncate mt-0.5">{inc.summary}</p>
                    </div>
                    <span className="text-xs text-slate-400 shrink-0 mt-0.5">
                      {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col">
      <div className="h-16 bg-white border-b border-slate-200 flex items-center px-8">
        <div className="h-5 w-48 bg-slate-200 rounded animate-pulse" />
      </div>
      <div className="p-6 grid grid-cols-4 gap-4">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-24 bg-white rounded-xl border border-slate-200 animate-pulse" />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col">
      <div className="h-16 bg-white border-b border-slate-200 flex items-center px-8">
        <h1 className="text-lg font-bold text-slate-900">Security Overview</h1>
      </div>
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="text-center">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600 text-sm mb-4">Failed to load: {message}</p>
          <button onClick={onRetry} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}
