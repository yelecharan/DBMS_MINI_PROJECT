'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { SeverityBadge, StatusBadge, Badge } from '@/components/ui/Badge';
import { useAuth } from '@/context/AuthContext';
import { Incident } from '@/types';
import {
  ArrowLeft, ShieldAlert, Clock, User, MessageSquare,
  CheckCircle, XCircle, AlertTriangle, Eye, FileText,
  Send, ChevronDown
} from 'lucide-react';

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, hasRole } = useAuth();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [assignEmail, setAssignEmail] = useState('');
  const [showAssign, setShowAssign] = useState(false);
  const [showNote, setShowNote] = useState(false);
  const [resolveNote, setResolveNote] = useState('');
  const [showResolve, setShowResolve] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await fetchApi<Incident>(`/api/incidents/${id}`);
      setIncident(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const doAction = async (action: string, body: any = {}) => {
    setActionLoading(action);
    setActionFeedback(null);
    try {
      await fetchApi(`/api/investigations/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setActionFeedback({ type: 'success', msg: `Action '${action}' completed successfully.` });
      await load();
    } catch (e: any) {
      setActionFeedback({ type: 'error', msg: e.message });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <LoadingDetail />;
  if (error || !incident) return (
    <div className="p-10 text-center text-red-600">
      <AlertTriangle className="w-10 h-10 mx-auto mb-2" />
      <p>{error ?? 'Incident not found'}</p>
    </div>
  );

  const bd = incident.score_breakdown;
  const isSecurity = hasRole(['ADMIN', 'SECURITY_OFFICER']);

  return (
    <div className="flex flex-col h-full">
      <Header title="Incident Detail" subtitle={`Incident ${incident.id.slice(0, 8)}…`} />
      <div className="flex-1 overflow-y-auto p-6">
        <button
          onClick={() => router.push('/incidents')}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 mb-5 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Incident Queue
        </button>

        {actionFeedback && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm mb-4 border ${
            actionFeedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            {actionFeedback.type === 'success'
              ? <CheckCircle className="w-4 h-4 shrink-0" />
              : <XCircle className="w-4 h-4 shrink-0" />}
            {actionFeedback.msg}
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Main column */}
          <div className="xl:col-span-2 space-y-5">
            {/* Incident Header Card */}
            <Card>
              <div className="flex flex-wrap items-start gap-3 mb-4">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
                <span className="text-xs bg-slate-100 text-slate-600 border border-slate-200 px-2.5 py-1 rounded-full font-medium">
                  {incident.incident_type.replace('_', ' ')}
                </span>
                <span className="ml-auto text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(incident.created_at).toLocaleString()}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4 p-4 bg-slate-50 rounded-lg">
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Gate</p>
                  <p className="text-sm font-semibold text-slate-800">{incident.gate_name ?? '—'}</p>
                  <p className="text-xs text-slate-400">{incident.site_name}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Auth / Observed</p>
                  <p className="text-sm font-bold text-slate-800">{incident.authorized_count} / {incident.observed_count}</p>
                  <p className="text-xs text-red-600 font-medium">+{incident.unmatched_count} unmatched</p>
                </div>
                <div>
                  <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Confidence</p>
                  <p className="text-sm font-bold text-slate-800">
                    {(incident.average_confidence * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <FileText className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold text-blue-800 mb-1">Incident Summary</p>
                    <p className="text-sm text-blue-900">{incident.summary}</p>
                  </div>
                </div>
              </div>
            </Card>

            {/* Risk Score Breakdown */}
            {bd && (
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-slate-800 text-sm">Explainable Risk Score</h3>
                  <div className={`text-2xl font-black ${
                    bd.final_score >= 80 ? 'text-red-600' :
                    bd.final_score >= 60 ? 'text-orange-600' :
                    bd.final_score >= 35 ? 'text-amber-500' : 'text-blue-600'
                  }`}>
                    {bd.final_score} / 100
                  </div>
                </div>
                <div className="space-y-3 mb-4">
                  {[
                    { label: 'Unmatched Person Count', value: bd.components.unmatched_component, max: 100, color: 'bg-red-500' },
                    { label: 'Detection Confidence Factor', value: bd.components.confidence_component, max: 20, color: 'bg-orange-500' },
                    { label: 'Zone Sensitivity Bonus', value: bd.components.zone_sensitivity_bonus, max: 20, color: 'bg-purple-500' },
                    { label: 'Repeat Incident Bonus', value: bd.components.repeat_incident_bonus, max: 15, color: 'bg-amber-500' },
                  ].map(c => (
                    <div key={c.label}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs text-slate-600">{c.label}</span>
                        <span className="text-xs font-bold text-slate-800">+{c.value.toFixed(1)}</span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${c.color} rounded-full`}
                          style={{ width: `${Math.min((c.value / 50) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <p className="text-xs text-slate-600 italic">{bd.explanation}</p>
                </div>
              </Card>
            )}

            {/* Investigation Timeline */}
            <Card>
              <h3 className="font-semibold text-slate-800 text-sm mb-4">Investigation Timeline</h3>
              {!incident.actions || incident.actions.length === 0 ? (
                <div className="text-center py-6 text-slate-400 text-sm">
                  <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-50" />
                  No investigation actions yet
                </div>
              ) : (
                <div className="relative pl-5">
                  <div className="absolute left-2 top-0 bottom-0 w-px bg-slate-200" />
                  {incident.actions.map((action, i) => (
                    <div key={action.id} className={`relative mb-4 ${i === incident.actions!.length - 1 ? '' : ''}`}>
                      <div className="absolute -left-[13px] top-1 w-3 h-3 rounded-full border-2 border-blue-400 bg-white" />
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 ml-2">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-blue-700 uppercase tracking-wider">
                            {action.action_type.replace('_', ' ')}
                          </span>
                          <span className="text-xs text-slate-400">
                            {new Date(action.created_at).toLocaleString()}
                          </span>
                        </div>
                        {action.actor_name && (
                          <p className="text-xs text-slate-500 flex items-center gap-1 mb-1">
                            <User className="w-3 h-3" /> {action.actor_name}
                          </p>
                        )}
                        {action.description && (
                          <p className="text-sm text-slate-700">{action.description}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Sidebar column — Actions */}
          <div className="space-y-4">
            {isSecurity && (
              <Card>
                <h3 className="font-semibold text-slate-800 text-sm mb-4 flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-blue-500" />
                  Investigation Actions
                </h3>
                <div className="space-y-2">
                  {/* Acknowledge */}
                  {incident.status === 'NEW' && (
                    <button
                      onClick={() => doAction('acknowledge')}
                      disabled={actionLoading === 'acknowledge'}
                      className="w-full text-left px-3 py-2.5 bg-blue-50 border border-blue-200 text-blue-700 rounded-lg text-xs font-semibold hover:bg-blue-100 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === 'acknowledge' ? '…' : '✓ Acknowledge Incident'}
                    </button>
                  )}

                  {/* Assign */}
                  <button
                    onClick={() => setShowAssign(v => !v)}
                    className="w-full text-left px-3 py-2.5 bg-purple-50 border border-purple-200 text-purple-700 rounded-lg text-xs font-semibold hover:bg-purple-100 transition-colors flex items-center justify-between"
                  >
                    <span>👤 Assign to Officer</span>
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAssign ? 'rotate-180' : ''}`} />
                  </button>
                  {showAssign && (
                    <div className="flex gap-2 px-1">
                      <input
                        value={assignEmail}
                        onChange={e => setAssignEmail(e.target.value)}
                        placeholder="Officer email…"
                        className="flex-1 text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-400"
                      />
                      <button
                        onClick={() => { doAction('assign', { assignee_email: assignEmail }); setShowAssign(false); }}
                        disabled={!assignEmail}
                        className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700 disabled:opacity-50"
                      >
                        <Send className="w-3 h-3" />
                      </button>
                    </div>
                  )}

                  {/* Add Note */}
                  <button
                    onClick={() => setShowNote(v => !v)}
                    className="w-full text-left px-3 py-2.5 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg text-xs font-semibold hover:bg-amber-100 transition-colors flex items-center justify-between"
                  >
                    <span>📝 Add Investigation Note</span>
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showNote ? 'rotate-180' : ''}`} />
                  </button>
                  {showNote && (
                    <div className="space-y-2 px-1">
                      <textarea
                        value={noteText}
                        onChange={e => setNoteText(e.target.value)}
                        rows={3}
                        placeholder="Enter investigation notes…"
                        className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-none"
                      />
                      <button
                        onClick={() => { doAction('add-action', { action_type: 'NOTE_ADDED', description: noteText }); setNoteText(''); setShowNote(false); }}
                        disabled={!noteText.trim()}
                        className="w-full px-3 py-1.5 bg-amber-500 text-white rounded-lg text-xs font-medium hover:bg-amber-600 disabled:opacity-50"
                      >
                        Save Note
                      </button>
                    </div>
                  )}

                  {/* Resolve */}
                  {!['RESOLVED', 'FALSE_POSITIVE'].includes(incident.status) && (
                    <>
                      <button
                        onClick={() => setShowResolve(v => !v)}
                        className="w-full text-left px-3 py-2.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg text-xs font-semibold hover:bg-emerald-100 transition-colors flex items-center justify-between"
                      >
                        <span>✅ Resolve Incident</span>
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showResolve ? 'rotate-180' : ''}`} />
                      </button>
                      {showResolve && (
                        <div className="space-y-2 px-1">
                          <textarea
                            value={resolveNote}
                            onChange={e => setResolveNote(e.target.value)}
                            rows={2}
                            placeholder="Resolution notes…"
                            className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                          />
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              onClick={() => { doAction('resolve', { resolution_notes: resolveNote }); setShowResolve(false); }}
                              className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700"
                            >
                              Resolve
                            </button>
                            <button
                              onClick={() => { doAction('false-positive', { resolution_notes: resolveNote || 'Marked as false positive' }); setShowResolve(false); }}
                              className="px-3 py-1.5 bg-slate-500 text-white rounded-lg text-xs font-medium hover:bg-slate-600"
                            >
                              False +ve
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </Card>
            )}

            {/* Evidence */}
            <Card>
              <h3 className="font-semibold text-slate-800 text-sm mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-slate-400" />
                Evidence Assets
              </h3>
              {!incident.evidence || incident.evidence.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-4">No evidence attached</p>
              ) : (
                <div className="space-y-2">
                  {incident.evidence.map(ev => (
                    <div key={ev.id} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-slate-700 truncate">{ev.media_type}</span>
                        {ev.is_redacted && <Badge variant="default" size="sm">REDACTED</Badge>}
                      </div>
                      <p className="text-xs text-slate-400 truncate mt-0.5">{ev.object_reference}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Assignment */}
            {incident.assigned_to && (
              <Card>
                <h3 className="font-semibold text-slate-800 text-sm mb-2 flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-400" />
                  Assigned To
                </h3>
                <p className="text-sm text-slate-700">{incident.assigned_officer_name ?? incident.assigned_to}</p>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingDetail() {
  return (
    <div className="flex flex-col h-full">
      <div className="h-16 bg-white border-b border-slate-200 flex items-center px-8">
        <div className="h-5 w-48 bg-slate-200 rounded animate-pulse" />
      </div>
      <div className="p-6 grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-4">
          {[...Array(3)].map((_, i) => <div key={i} className="h-48 bg-white rounded-xl border border-slate-200 animate-pulse" />)}
        </div>
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => <div key={i} className="h-32 bg-white rounded-xl border border-slate-200 animate-pulse" />)}
        </div>
      </div>
    </div>
  );
}
