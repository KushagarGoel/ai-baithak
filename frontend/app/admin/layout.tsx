'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const ADMIN_NAV_ITEMS = [
  { label: 'MCP Servers', path: '/admin/mcps', icon: '🔌' },
  { label: 'Agents', path: '/admin/agents', icon: '🤖' },
  { label: 'Permissions', path: '/admin/permissions', icon: '🔐' },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      {/* Admin Header */}
      <header className="border-b border-outline-variant/10 bg-surface-container-low/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo & Back Link */}
            <div className="flex items-center gap-4">
              <a
                href="/"
                className="flex items-center gap-3 hover:opacity-80 transition-opacity"
              >
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-container flex items-center justify-center shadow-glow-primary">
                  <span className="text-xl">🏛️</span>
                </div>
                <div>
                  <h1 className="text-headline-sm font-semibold text-on-surface">
                    Agent Council
                  </h1>
                  <p className="text-label-sm text-on-surface-variant">
                    AI Deliberation Platform
                  </p>
                </div>
              </a>
              <span className="text-outline-variant">/</span>
              <span className="text-label-md font-medium text-on-surface">Admin</span>
            </div>

            {/* Admin Navigation */}
            <nav className="flex items-center gap-1 bg-surface-container rounded-lg p-1">
              {ADMIN_NAV_ITEMS.map((item) => (
                <Link
                  key={item.path}
                  href={item.path}
                  className={cn(
                    'px-4 py-2 rounded-md text-label-md font-medium transition-all duration-200',
                    pathname === item.path
                      ? 'bg-surface-container-high text-primary shadow-sm'
                      : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                  )}
                >
                  <span className="mr-2">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </nav>

            {/* Back to App */}
            <a
              href="/"
              className="flex items-center gap-2 px-4 py-2 text-label-md font-medium text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span>←</span>
              Back to App
            </a>
          </div>
        </div>
      </header>

      {/* Page Content */}
      <main>{children}</main>
    </div>
  );
}
