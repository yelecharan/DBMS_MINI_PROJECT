'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { LiveGateStatus } from '@/types';
import { Radio, Shield, Camera, Clock, AlertTriangle, CheckCircle, XCircle, Wifi, WifiOff } from 'lucide-react';

export default function MonitoringPage() {
  const [gates, setGates] = useState<LiveGateStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadGates = useCallback(async () => {
    try {
      const data = await fetchApi<LiveGateStatus[]>('/api/analytics/live-gates');
      setGates(data);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('Live gate poll failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGates();
    const interval = setInterval(loadGates, 10000);
    return () => clearInterval(interval);
  }, [loadGates]);

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Live Gate Monitoring"
        subtitle="Real-time access control status · auto-refresh every 10s"
      />
      <div className="flex-1 p-6 overflow-y-auto">
        {/* Status Bar */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-500 animate-pulse" />
            <span className="text-sm font-medium text-slate-600">
              {gates.length} gate{gates.length !== 1 ? 's' : ''} monitored
            </span>
          </div>
          {lastUpdated && (
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Clock className="w-3.5 h-3.5" />
              Last refreshed {lastUpdated.toLocaleTimeString()}
            </div>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-48 bg-white rounded-xl border border-slate-200 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {gates.map(gate => <GateCard key={gate.gate_id} gate={gate} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function GateCard({ gate }: { gate: LiveGateStatus }) {
  const hasAlert = gate.last_incident_severity === 'CRITICAL' || gate.last_incident_severity === 'HIGH';
  const isTailgating = gate.session_active && gate.observed_count > gate.authorized_count;

  const borderColor = !gate.is_active
    ? 'border-slate-200'
    : isTailgating
    ? 'border-red-400 shadow-red-100'
    : gate.session_active
    ? 'border-emerald-400 shadow-emerald-100'
    : 'border-slate-200';

  return (
    <Card className={`border-2 ${borderColor} shadow-md`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Shield className={`w-4 h-4 ${gate.is_active ? 'text-blue-500' : 'text-slate-300'}`} />
            <h3 className="text-sm font-bold text-slate-800">{gate.gate_name}</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{gate.site_name} · {gate.zone_name}</p>
          <p className="text-xs text-slate-400">{gate.gate_code} · {gate.direction}</p>
        </div>
        <div className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${
          gate.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-400'
        }`}>
          {gate.is_active ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {gate.is_active ? 'ACTIVE' : 'OFFLINE'}
        </div>
      </div>

      {/* Session Status */}
      <div className={`rounded-lg p-3 mb-3 ${gate.session_active ? (isTailgating ? 'bg-red-50 border border-red-200' : 'bg-emerald-50 border border-emerald-200') : 'bg-slate-50 border border-slate-200'}`}>
        <div className="flex items-center justify-between mb-2">
          <span className={`text-xs font-semibold ${gate.session_active ? (isTailgating ? 'text-red-700' : 'text-emerald-700') : 'text-slate-500'}`}>
            {gate.session_active ? (isTailgating ? '⚠ POTENTIAL TAILGATING' : '● Session Active') : '○ No Active Session'}
          </span>
        </div>
        {gate.session_active && (
          <div className="grid grid-cols-2 gap-2">
            <div className="text-center">
              <p className="text-xs text-slate-500">Authorized</p>
              <p className="text-lg font-bold text-blue-700">{gate.authorized_count}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-slate-500">Observed</p>
              <p className={`text-lg font-bold ${isTailgating ? 'text-red-600' : 'text-emerald-600'}`}>
                {gate.observed_count}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Camera Row */}
      <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
        <div className="flex items-center gap-1.5">
          <Camera className="w-3.5 h-3.5" />
          <span>{gate.camera_count} camera{gate.camera_count !== 1 ? 's' : ''}</span>
          <span className={`inline-flex items-center gap-0.5 font-medium ${
            gate.camera_status === 'ALL_ACTIVE' ? 'text-emerald-600' :
            gate.camera_status === 'PARTIAL' ? 'text-amber-600' : 'text-slate-400'
          }`}>
            · {gate.camera_status.replace('_', ' ')}
          </span>
        </div>
        {gate.last_access_decision && (
          <div className="flex items-center gap-1">
            {gate.last_access_decision === 'GRANTED' ? (
              <CheckCircle className="w-3 h-3 text-emerald-500" />
            ) : (
              <XCircle className="w-3 h-3 text-red-500" />
            )}
            <span className={gate.last_access_decision === 'GRANTED' ? 'text-emerald-600' : 'text-red-600'}>
              {gate.last_access_decision}
            </span>
          </div>
        )}
      </div>

      {/* Last Incident */}
      {gate.last_incident_severity && (
        <div className={`text-xs rounded-md px-2.5 py-1.5 mt-1 ${hasAlert ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-slate-50 text-slate-500 border border-slate-200'}`}>
          <div className="flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span className="font-semibold">{gate.last_incident_severity}</span>
            {gate.last_incident_time && (
              <span className="ml-auto text-[10px] text-slate-400">
                {new Date(gate.last_incident_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
          {gate.last_incident_summary && (
            <p className="mt-0.5 truncate text-[10px] text-slate-500">{gate.last_incident_summary}</p>
          )}
        </div>
      )}
    </Card>
  );
}
