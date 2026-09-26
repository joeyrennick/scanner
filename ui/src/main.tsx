import { StrictMode, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { isTauri } from '@tauri-apps/api/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { DesktopProofOfConcept } from './desktop/DesktopProofOfConcept';
import { BrowserExportPage } from './features/migration/BrowserExportPage';
import { BusinessRecordsGate, BusinessRecordsProvider } from './features/business/BusinessRecordsProvider';
import { isMigrationPaused, subscribeMigrationPause } from './lib/browserExport';
import { PlatformProvider } from './platform/PlatformProvider';
import { browserRuntime } from './platform/runtime';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false
    }
  }
});

function BrowserApplication() {
  const paused = useSyncExternalStore(subscribeMigrationPause, isMigrationPaused);
  if (paused || window.location.pathname === '/migration') return <BrowserExportPage />;
  return <QueryClientProvider client={queryClient}>
    <BusinessRecordsGate><BrowserRouter><App /></BrowserRouter></BusinessRecordsGate>
  </QueryClientProvider>;
}

const application = isTauri() ? (
  <DesktopProofOfConcept />
) : (
  <PlatformProvider runtime={browserRuntime}><BusinessRecordsProvider><BrowserApplication /></BusinessRecordsProvider></PlatformProvider>
);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {application}
  </StrictMode>
);
