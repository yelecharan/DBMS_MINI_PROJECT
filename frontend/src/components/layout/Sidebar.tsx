'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
  LayoutDashboard,
  Radio,
  ShieldAlert,
  Search,
  Users,
  DoorClosed,
  UserCheck,
  FileText,
  BarChart3,
  Shield,
  LogOut,
  ChevronRight,
  Zap
} from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, hasRole } = useAuth();

  const navigation = [
    { name: 'Overview', href: '/overview', icon: LayoutDashboard },
    { name: 'Live Monitoring', href: '/monitoring', icon: Radio },
    { name: 'Incident Queue', href: '/incidents', icon: ShieldAlert },
    { name: 'Vector Intelligence', href: '/intelligence', icon: Search },
    { name: 'Employee Directory', href: '/employees', icon: Users },
    { name: 'Gates & Portals', href: '/gates', icon: DoorClosed },
    ...(hasRole(['ADMIN'])
      ? [{ name: 'User Management', href: '/users', icon: UserCheck }]
      : []),
    { name: 'Audit Trail', href: '/audit', icon: FileText },
    { name: 'Security Reports', href: '/reports', icon: BarChart3 },
    { name: 'Demo Runner', href: '/demo', icon: Zap },
  ];

  return (
    <aside className="w-64 bg-[#0d131f] text-slate-300 flex flex-col flex-shrink-0 min-h-screen border-r border-slate-800/80">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800/80 bg-[#090d16]">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <Shield className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="font-bold text-white tracking-wide text-sm flex items-center gap-1.5">
            GateSentry
            <span className="text-[10px] bg-blue-500/20 text-blue-400 font-semibold px-1.5 py-0.2 rounded border border-blue-500/30">
              v1.0
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Office Threat Defense</p>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Security Operations
        </div>
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span className="flex-1">{item.name}</span>
              {isActive && <ChevronRight className="w-3.5 h-3.5 text-white/70" />}
            </Link>
          );
        })}
      </div>

      {/* User Profile Card & Sign out */}
      <div className="p-3 border-t border-slate-800/80 bg-[#090d16]/70">
        <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-blue-400">
            {user?.full_name?.charAt(0) || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name || 'Active Officer'}</p>
            <p className="text-[10px] text-blue-400 font-medium tracking-wide uppercase truncate">
              {user?.role?.replace('_', ' ') || 'AUDITOR'}
            </p>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors border border-transparent hover:border-red-500/20"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
