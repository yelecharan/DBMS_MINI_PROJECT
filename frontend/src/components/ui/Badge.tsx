import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'critical' | 'info';
  size?: 'sm' | 'md';
}

export function Badge({ children, variant = 'default', size = 'md' }: BadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-semibold';
  
  let variantClasses = 'bg-slate-100 text-slate-700 border-slate-200';
  if (variant === 'success') {
    variantClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (variant === 'warning') {
    variantClasses = 'bg-amber-50 text-amber-700 border-amber-200';
  } else if (variant === 'danger') {
    variantClasses = 'bg-orange-50 text-orange-700 border-orange-200';
  } else if (variant === 'critical') {
    variantClasses = 'bg-red-100 text-red-800 border-red-300 font-bold animate-pulse';
  } else if (variant === 'info') {
    variantClasses = 'bg-blue-50 text-blue-700 border-blue-200';
  }

  return (
    <span className={`inline-flex items-center rounded-full border ${sizeClasses} ${variantClasses}`}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const s = severity?.toUpperCase();
  if (s === 'CRITICAL') return <Badge variant="critical">CRITICAL</Badge>;
  if (s === 'HIGH') return <Badge variant="danger">HIGH</Badge>;
  if (s === 'MEDIUM') return <Badge variant="warning">MEDIUM</Badge>;
  return <Badge variant="info">LOW</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const s = status?.toUpperCase();
  if (s === 'NEW') return <Badge variant="critical">NEW</Badge>;
  if (s === 'ACKNOWLEDGED') return <Badge variant="info">ACKNOWLEDGED</Badge>;
  if (s === 'UNDER_INVESTIGATION') return <Badge variant="warning">INVESTIGATING</Badge>;
  if (s === 'RESOLVED') return <Badge variant="success">RESOLVED</Badge>;
  if (s === 'FALSE_POSITIVE') return <Badge variant="default">FALSE POSITIVE</Badge>;
  return <Badge variant="default">{status}</Badge>;
}
