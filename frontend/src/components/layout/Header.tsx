'use client';

import React from 'react';
import { useAuth } from '@/context/AuthContext';
import { Database, Cpu, Radio, ShieldCheck } from 'lucide-react';

export function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  const { user } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-8 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      <div>
        <h1 className="text-lg font-bold text-slate-900 tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Data layer label; live service health is not currently exposed by the API. */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs text-slate-600">
          <Database className="w-3.5 h-3.5 text-blue-600" />
          <span className="font-medium text-[11px]">PostgreSQL / SQLite</span>
        </div>

        {/* Vector store label; embedding provider depends on runtime configuration. */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs text-slate-600">
          <Cpu className="w-3.5 h-3.5 text-indigo-600" />
          <span className="font-medium text-[11px]">Qdrant Vector Search</span>
        </div>

        {/* Correlation capability label, not a live pipeline health signal. */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">
          <Radio className="w-3 h-3 text-emerald-600 animate-pulse" />
          <span className="font-medium text-[11px]">Explainable Correlation</span>
        </div>

        {/* User Role Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-blue-50 border border-blue-200/80 text-blue-800">
          <ShieldCheck className="w-4 h-4 text-blue-600" />
          <span className="font-semibold text-xs tracking-wide">{user?.role?.replace('_', ' ') || 'GUEST'}</span>
        </div>
      </div>
    </header>
  );
}
