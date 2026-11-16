import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  noPad?: boolean;
}

export function Card({ children, className = '', noPad = false }: CardProps) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200/80 shadow-sm ${noPad ? '' : 'p-5'} ${className}`}>
      {children}
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color?: 'blue' | 'green' | 'red' | 'orange' | 'purple';
  subtitle?: string;
  trend?: { value: number; label: string };
}

const colorMap = {
  blue: {
    bg: 'bg-blue-50',
    icon: 'bg-blue-100 text-blue-600',
    value: 'text-blue-900',
  },
  green: {
    bg: 'bg-emerald-50',
    icon: 'bg-emerald-100 text-emerald-600',
    value: 'text-emerald-900',
  },
  red: {
    bg: 'bg-red-50',
    icon: 'bg-red-100 text-red-600',
    value: 'text-red-900',
  },
  orange: {
    bg: 'bg-orange-50',
    icon: 'bg-orange-100 text-orange-600',
    value: 'text-orange-900',
  },
  purple: {
    bg: 'bg-purple-50',
    icon: 'bg-purple-100 text-purple-600',
    value: 'text-purple-900',
  },
};

export function StatCard({ title, value, icon, color = 'blue', subtitle, trend }: StatCardProps) {
  const c = colorMap[color];
  return (
    <div className={`rounded-xl border border-slate-200/80 shadow-sm p-5 ${c.bg}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
          <p className={`text-2xl font-bold mt-1.5 ${c.value}`}>{value}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
          {trend && (
            <p className={`text-xs mt-1.5 font-medium ${trend.value >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {trend.value >= 0 ? '↑' : '↓'} {Math.abs(trend.value)} {trend.label}
            </p>
          )}
        </div>
        <div className={`w-10 h-10 rounded-lg ${c.icon} flex items-center justify-center`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
