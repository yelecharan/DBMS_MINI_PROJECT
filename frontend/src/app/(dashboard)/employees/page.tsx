'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '@/lib/api';
import { Header } from '@/components/layout/Header';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Employee } from '@/types';
import { Users, Search, UserCheck, UserX, Building2 } from 'lucide-react';

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      const data = await fetchApi<Employee[]>(`/api/employees?${params}`);
      setEmployees(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(() => load(), 300);
    return () => clearTimeout(timer);
  }, [load]);

  const departments = Array.from(new Set(employees.map(e => e.department).filter(Boolean))).sort();
  const filtered = deptFilter ? employees.filter(e => e.department === deptFilter) : employees;

  return (
    <div className="flex flex-col h-full">
      <Header title="Employee Directory" subtitle="All registered employees and their access credentials" />
      <div className="flex-1 overflow-y-auto p-6">
        {/* Controls */}
        <div className="flex gap-3 mb-5">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by name, code or email…"
              className="w-full pl-9 pr-4 py-2.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={deptFilter}
            onChange={e => setDeptFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Departments</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-4 mb-5">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-blue-500" />
              <div>
                <p className="text-xs text-slate-400">Total Employees</p>
                <p className="text-2xl font-bold text-slate-800">{employees.length}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-emerald-500" />
              <div>
                <p className="text-xs text-slate-400">Active</p>
                <p className="text-2xl font-bold text-slate-800">{employees.filter(e => e.is_active).length}</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-purple-500" />
              <div>
                <p className="text-xs text-slate-400">Departments</p>
                <p className="text-2xl font-bold text-slate-800">{departments.length}</p>
              </div>
            </div>
          </div>
        </div>

        <Card noPad>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Employee</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Code</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Department</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden md:table-cell">Email</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider hidden lg:table-cell">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(6)].map((_, j) => (
                      <td key={j} className="px-5 py-3">
                        <div className="h-4 bg-slate-100 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-400 text-sm">
                    <Users className="w-6 h-6 mx-auto mb-2 opacity-50" />
                    No employees found
                  </td>
                </tr>
              ) : (
                filtered.map(emp => (
                  <tr key={emp.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold shrink-0">
                          {emp.full_name.charAt(0)}
                        </div>
                        <span className="text-sm font-medium text-slate-800">{emp.full_name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-slate-600">{emp.employee_code}</td>
                    <td className="px-5 py-3 text-xs text-slate-600">{emp.department}</td>
                    <td className="px-5 py-3 text-xs text-slate-400 hidden md:table-cell">{emp.email}</td>
                    <td className="px-5 py-3">
                      {emp.is_active
                        ? <Badge variant="success" size="sm">ACTIVE</Badge>
                        : <Badge variant="default" size="sm">INACTIVE</Badge>}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400 hidden lg:table-cell">
                      {new Date(emp.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
