'use client';

import React, { useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import {
  Zap, Play, RefreshCw, AlertTriangle, CheckCircle,
  ExternalLink, Shield, Trash2
} from 'lucide-react';

interface Scenario {
  id: string;
  name: string;
  description: string;
  details: string;
  icon: string;
  color: string;
  endpoint: string;
}

const SCENARIOS: Scenario[] = [
  {
    id: 'tailgating',
    name: 'Classic Tailgating',
    description: 'One employee swipes in, two people observed crossing the threshold.',
    details: 'Triggers the core detection: 1 authorized entry vs 2 observed crossings → 1 unmatched → incident created.',
    icon: '👥',
    color: 'border-red-300 bg-red-50',
    endpoint: '/api/demo/scenarios/tailgating',
  },
  {
    id: 'unauthorized-entry',
    name: 'Unauthorized Entry',
    description: 'No badge swipe, one person crosses the entrance.',
    details: 'Zero authorized entries, one detected crossing — classic unauthorized access scenario.',
    icon: '🚫',
    color: 'border-orange-300 bg-orange-50',
    endpoint: '/api/demo/scenarios/unauthorized-entry',
  },
  {
    id: 'low-confidence',
    name: 'Low Confidence Detection',
    description: 'CCTV detection confidence below threshold, possible ghost event.',
    details: 'Demonstrates the minimum confidence filter — detections below threshold are excluded from correlation.',
    icon: '📡',
    color: 'border-amber-300 bg-amber-50',
    endpoint: '/api/demo/scenarios/low-confidence',
  },
  {
    id: 'mass-tailgating',
    name: 'Mass Tailgating Event',
    description: 'One badge swipe, four people observed entering simultaneously.',
    details: 'High unmatched count → CRITICAL risk score. Tests score clamping and repeat bonus calculation.',
    icon: '🚨',
    color: 'border-red-500 bg-red-100',
    endpoint: '/api/demo/scenarios/mass-tailgating',
  },
  {
    id: 'false-positive',
    name: 'False Positive Flow',
    description: 'Create an incident and immediately mark it as a false positive.',
    details: 'Demonstrates the full investigation lifecycle: auto-incident → acknowledge → false positive → audit log.',
    icon: '✅',
    color: 'border-emerald-300 bg-emerald-50',
    endpoint: '/api/demo/scenarios/false-positive',
  },
  {
    id: 'restricted-zone',
    name: 'Restricted Zone Entry',
    description: 'Tailgating incident in a high-sensitivity restricted zone.',
    details: 'Zone sensitivity bonus (+20) pushes the risk score higher. Demonstrates the explainable scoring system.',
    icon: '🔒',
    color: 'border-purple-300 bg-purple-50',
    endpoint: '/api/demo/scenarios/restricted-zone',
  },
];

interface RunResult {
  scenarioId: string;
  data: any;
  error?: string;
}

export default function DemoPage() {
  const { hasRole } = useAuth();
  const router = useRouter();
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, RunResult>>({});
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  const runScenario = async (scenario: Scenario) => {
    setRunning(scenario.id);
    try {
      const data = await fetchApi(scenario.endpoint, { method: 'POST' });
      setResults(prev => ({ ...prev, [scenario.id]: { scenarioId: scenario.id, data } }));
    } catch (e: any) {
      setResults(prev => ({
        ...prev,
        [scenario.id]: { scenarioId: scenario.id, data: null, error: e.message }
      }));
    } finally {
      setRunning(null);
    }
  };

  const resetAndSeed = async () => {
    setResetting(true);
    setResetMsg(null);
    try {
      await fetchApi('/api/demo/reset', { method: 'POST' });
      setResetMsg('Database reset and re-seeded successfully.');
      setResults({});
    } catch (e: any) {
      setResetMsg(`Reset failed: ${e.message}`);
    } finally {
      setResetting(false);
    }
  };

  if (!hasRole(['ADMIN', 'SECURITY_OFFICER'])) {
    return (
      <div className="flex flex-col h-full">
        <Header title="Demo Runner" subtitle="Security access required" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">Admin or Security Officer role required.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Demo Scenario Runner"
        subtitle="Trigger live demonstration scenarios · results appear in Incident Queue"
      />
      <div className="flex-1 overflow-y-auto p-6">
        {/* Controls */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl flex-1 mr-4">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-800">Demonstration Mode</p>
              <p className="text-xs text-amber-600">
                These scenarios create synthetic events using realistic data.
                All incidents are real database entries and can be investigated normally.
              </p>
            </div>
          </div>
          <button
            onClick={resetAndSeed}
            disabled={resetting}
            className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white rounded-xl text-sm font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {resetting
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <Trash2 className="w-4 h-4" />}
            Reset & Re-seed DB
          </button>
        </div>

        {resetMsg && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm mb-5 border ${
            resetMsg.includes('failed')
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-emerald-50 border-emerald-200 text-emerald-700'
          }`}>
            {resetMsg.includes('failed')
              ? <AlertTriangle className="w-4 h-4 shrink-0" />
              : <CheckCircle className="w-4 h-4 shrink-0" />}
            {resetMsg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {SCENARIOS.map(scenario => {
            const result = results[scenario.id];
            return (
              <div key={scenario.id} className={`bg-white rounded-xl border-2 shadow-sm overflow-hidden ${scenario.color}`}>
                <div className="p-5">
                  <div className="flex items-start gap-3 mb-3">
                    <span className="text-3xl">{scenario.icon}</span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800">{scenario.name}</h3>
                      <p className="text-xs text-slate-600 mt-0.5">{scenario.description}</p>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed mb-4">{scenario.details}</p>
                  <button
                    onClick={() => runScenario(scenario)}
                    disabled={running === scenario.id}
                    className="w-full flex items-center justify-center gap-2 py-2.5 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-700 disabled:opacity-60 transition-colors"
                  >
                    {running === scenario.id ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Running…
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" />
                        Run Scenario
                      </>
                    )}
                  </button>
                </div>

                {/* Result */}
                {result && (
                  <div className="border-t border-slate-200 bg-slate-900 p-4">
                    {result.error ? (
                      <div className="text-red-400 text-xs flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        {result.error}
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                            <CheckCircle className="w-3.5 h-3.5" />
                            Success
                          </div>
                          {result.data?.incident_id && (
                            <button
                              onClick={() => router.push(`/incidents/${result.data.incident_id}`)}
                              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                            >
                              View Incident <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                        <pre className="text-xs text-slate-300 overflow-x-auto max-h-40 leading-relaxed">
                          {JSON.stringify(result.data, null, 2)}
                        </pre>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick Links */}
        <Card className="mt-6">
          <h3 className="font-semibold text-slate-800 text-sm mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-500" />
            After running scenarios
          </h3>
          <div className="flex flex-wrap gap-2">
            {[
              { label: '→ Incident Queue', href: '/incidents' },
              { label: '→ Live Monitoring', href: '/monitoring' },
              { label: '→ Vector Search', href: '/intelligence' },
              { label: '→ Audit Trail', href: '/audit' },
              { label: '→ Reports', href: '/reports' },
            ].map(link => (
              <button
                key={link.href}
                onClick={() => router.push(link.href)}
                className="px-3 py-1.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors font-medium"
              >
                {link.label}
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
