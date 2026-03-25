'use client';

import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { ConfigPanel } from '@/components/config/ConfigPanel';
import { DiscussionPanel } from '@/components/discussion/DiscussionPanel';
import { SessionsPanel } from '@/components/sessions/SessionsPanel';
import { ArchivesPanel } from '@/components/archives/ArchivesPanel';
import { ReportPanel } from '@/components/report/ReportPanel';
import { useCouncilStore } from '@/stores/councilStore';

export default function Home() {
  const { viewMode } = useCouncilStore();

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="flex h-[calc(100vh-73px)]">
        {/* Sidebar - only show in discussion mode */}
        {viewMode === 'discussion' && <Sidebar />}

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          {viewMode === 'config' && <ConfigPanel />}
          {viewMode === 'discussion' && <DiscussionPanel />}
          {viewMode === 'sessions' && <SessionsPanel />}
          {viewMode === 'archives' && <ArchivesPanel />}
          {viewMode === 'report' && <ReportPanel />}
        </main>
      </div>
    </div>
  );
}
