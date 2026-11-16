'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Gate } from '@/types';
import { DoorClosed, Camera, Shield, Wifi, WifiOff, ArrowRightLeft } from 'lucide-react';

export default function GatesPage() {
  const [gates, setGates] = useState<Gate[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<Gate[]>('/api/gates');
      setGates(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col h-full">
      <Header title="Gates & Portals" subtitle="Access control points and their monitoring configuration" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {loading ? (
            [...Array(4)].map((_, i) => (
              <div key={i} className="h-52 bg-white rounded-xl border border-slate-200 animate-pulse" />
            ))
          ) : gates.length === 0 ? (
            <div className="col-span-3 text-center py-16 text-slate-400">
              <DoorClosed className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No gates configured</p>
            </div>
          ) : (
            gates.map(gate => (
              <Card key={gate.id} className={`border-2 ${gate.is_active ? 'border-blue-200' : 'border-slate-200'}`}>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${gate.is_active ? 'bg-blue-50' : 'bg-slate-100'}`}>
                      <DoorClosed className={`w-5 h-5 ${gate.is_active ? 'text-blue-600' : 'text-slate-400'}`} />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800">{gate.gate_name}</h3>
                      <p className="text-xs text-slate-400 font-mono">{gate.gate_code}</p>
                    </div>
                  </div>
                  {gate.is_active
                    ? <Badge variant="success" size="sm"><Wifi className="w-3 h-3 mr-1" />ACTIVE</Badge>
                    : <Badge variant="default" size="sm"><WifiOff className="w-3 h-3 mr-1" />OFFLINE</Badge>}
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                    <span className="text-slate-500 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5" /> Zone
                    </span>
                    <span className="font-medium text-slate-700">{gate.zone_name ?? gate.zone_id}</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                    <span className="text-slate-500 flex items-center gap-1.5">
                      <ArrowRightLeft className="w-3.5 h-3.5" /> Direction
                    </span>
                    <span className="font-medium text-slate-700">{gate.direction}</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                    <span className="text-slate-500 flex items-center gap-1.5">
                      <Camera className="w-3.5 h-3.5" /> Min. Confidence
                    </span>
                    <span className="font-medium text-slate-700">
                      {(gate.minimum_detection_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                    <span className="text-slate-500">Session Window</span>
                    <span className="font-medium text-slate-700">{gate.session_window_seconds}s</span>
                  </div>
                </div>

                {gate.site_name && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <p className="text-xs text-slate-400">
                      Site: <span className="font-medium text-slate-600">{gate.site_name}</span>
                    </p>
                  </div>
                )}
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
