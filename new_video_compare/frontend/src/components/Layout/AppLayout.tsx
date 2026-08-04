import React from 'react';
import { clsx } from 'clsx';

interface AppLayoutProps {
  children: React.ReactNode;
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  className?: string;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  children,
  sidebar,
  header,
  className
}) => {
  return (
    <div className={clsx('min-h-screen bg-slate-50 dark:bg-[#0d0e15] text-slate-900 dark:text-slate-100 transition-colors', className)}>
      {/* Header */}
      {header && (
        <div className="bg-white dark:bg-[#12131c] shadow-sm border-b border-slate-200 dark:border-white/10">
          {header}
        </div>
      )}

      <div className="flex">
        {/* Sidebar */}
        {sidebar && (
          <div className="w-80 bg-white dark:bg-[#161824] shadow-sm border-r border-slate-200 dark:border-white/10 min-h-screen">
            {sidebar}
          </div>
        )}

        {/* Main Content */}
        <div className="flex-1 p-6">
          {children}
        </div>
      </div>
    </div>
  );
};
