'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useAuth } from '@/context/AuthContext';
import { User } from '@/types';
import { UserCheck, Shield, Mail, Calendar, AlertTriangle, Plus, X } from 'lucide-react';

const ROLES = ['ADMIN', 'SECURITY_OFFICER', 'AUDITOR'];

export default function UsersPage() {
  const { hasRole } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'SECURITY_OFFICER' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<User[]>('/api/users');
      setUsers(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const createUser = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      await fetchApi('/api/users', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      setShowCreate(false);
      setForm({ full_name: '', email: '', password: '', role: 'SECURITY_OFFICER' });
      await load();
    } catch (e: any) {
      setCreateError(e.message);
    } finally {
      setCreating(false);
    }
  };

  if (!hasRole(['ADMIN'])) {
    return (
      <div className="flex flex-col h-full">
        <Header title="User Management" subtitle="Administrator access required" />
        <div className="flex-1 flex items-center justify-center p-10">
          <div className="text-center">
            <Shield className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">You don&apos;t have permission to access this page.</p>
          </div>
        </div>
      </div>
    );
  }

  const roleColor = (role: string) => {
    if (role === 'ADMIN') return 'danger';
    if (role === 'SECURITY_OFFICER') return 'warning';
    return 'info';
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="User Management" subtitle="System users and their assigned roles" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="flex justify-between items-center mb-5">
          <div className="flex gap-3">
            {ROLES.map(role => (
              <div key={role} className="flex items-center gap-1.5 text-xs text-slate-500">
                <Badge variant={roleColor(role) as any} size="sm">{role.replace('_', ' ')}</Badge>
                <span>({users.filter(u => u.role === role).length})</span>
              </div>
            ))}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 text-xs px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <Plus className="w-3.5 h-3.5" /> New User
          </button>
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <Card className="w-full max-w-md">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-slate-800">Create New User</h3>
                <button onClick={() => setShowCreate(false)} className="p-1 hover:bg-slate-100 rounded">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>
              {createError && (
                <div className="mb-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  {createError}
                </div>
              )}
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Full Name</label>
                  <input
                    value={form.full_name}
                    onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Jane Smith"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="jane@gatesentry.internal"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Password</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Min 8 characters"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Role</label>
                  <select
                    value={form.role}
                    onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                    className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {ROLES.map(r => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <button
                  onClick={createUser}
                  disabled={creating || !form.full_name || !form.email || !form.password}
                  className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {creating ? 'Creating…' : 'Create User'}
                </button>
              </div>
            </Card>
          </div>
        )}

        <Card noPad>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Role</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden md:table-cell">Email</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden lg:table-cell">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                [...Array(4)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(5)].map((_, j) => (
                      <td key={j} className="px-5 py-3">
                        <div className="h-4 bg-slate-100 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : users.map(u => (
                <tr key={u.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center text-xs font-bold shrink-0">
                        {u.full_name.charAt(0)}
                      </div>
                      <span className="text-sm font-medium text-slate-800">{u.full_name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={roleColor(u.role) as any} size="sm">{u.role.replace('_', ' ')}</Badge>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-500 hidden md:table-cell">
                    <div className="flex items-center gap-1">
                      <Mail className="w-3 h-3 shrink-0" />{u.email}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {u.is_active
                      ? <Badge variant="success" size="sm">ACTIVE</Badge>
                      : <Badge variant="default" size="sm">INACTIVE</Badge>}
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-400 hidden lg:table-cell">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 shrink-0" />
                      {new Date(u.created_at).toLocaleDateString()}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
