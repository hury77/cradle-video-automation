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
    <div className={clsx('min-h-screen bg-gray-100', className)}>
      {/* Header */}
      {header && (
        <div className="bg-white shadow-sm border-b border-gray-200">
          {header}
        </div>
      )}

      <div className="flex">
        {/* Sidebar */}
        {sidebar && (
          <div className="w-80 bg-white shadow-sm border-r border-gray-200 min-h-screen">
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
