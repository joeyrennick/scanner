import { useState, useSyncExternalStore } from 'react';
import { createBrowserExport, isMigrationPaused, setMigrationPaused, subscribeMigrationPause } from '../../lib/browserExport';
import { checkImportedBrowserRecords, resumeImportedBrowserRecords } from '../../lib/businessMigration';
import { usePlatform } from '../../platform/PlatformProvider';

export function BrowserExportPage() {
  const { files } = usePlatform();
  const paused = useSyncExternalStore(subscribeMigrationPause, isMigrationPaused);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [reviewed, setReviewed] = useState(false);

  async function checkImport(resume = false) {
    setBusy(true);
    setMessage('');
    setReviewed(false);
    try {
      if (resume) {
        await resumeImportedBrowserRecords();
        window.location.assign('/journal');
      } else {
        const { counts } = await checkImportedBrowserRecords();
        setReviewed(true);
        setMessage(`Database connection verified: ${counts.plannedTrades} Planned Trades, ${counts.candidateEdits} candidate edits, ${counts.valuationAssumptions} valuation assumptions, ${counts.browserSettings} settings groups. Original browser records are preserved. You can now resume using the database.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Import check failed. Keep editing paused.');
    } finally { setBusy(false); }
  }

  async function exportData() {
    setBusy(true);
    setMessage('');
    setReviewed(false);
    try {
      setMigrationPaused(true);
      const data = await createBrowserExport();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      await files.save(blob, `scanner-browser-export-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
      const { counts } = JSON.parse(data.payloadJson);
      setMessage(`Export prepared: ${counts.plannedTrades} Planned Trades, ${counts.candidateEdits} candidate edits, ${counts.valuationAssumptions} valuation assumptions, ${counts.browserSettings} settings groups. Check that the file was saved. Keep editing paused until the coordinated backup and restore check finishes.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Export failed. Your original data is retained.');
    } finally { setBusy(false); }
  }

  return (
    <main style={{ maxWidth: 760, margin: '48px auto', padding: 24 }}>
      <section className="panel" aria-labelledby="browser-export-title">
        <div className="panel-header"><h1 id="browser-export-title">Browser migration and recovery</h1></div>
        <div className="settings-form">
          <p>Open this page in the browser and at the address where you used Swing Scanner. The original browser records are retained for recovery. After the database switch, this browser export is an archival copy, not a backup of new database edits.</p>
          <p>Current address: {window.location.origin}</p>
          <p>Let scanner jobs finish, then close every other scanner tab, including tabs in other windows. This export contains browser records; the database and reports will be backed up separately.</p>
          <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> Jobs have finished and I have closed other scanner tabs.</label>
          <button className="primary-button" disabled={!confirmed || busy} onClick={exportData}>
            {busy ? 'Preparing export…' : 'Pause editing and export records'}
          </button>
          {paused && <p>Browser editing is paused. Your original records remain stored in this browser.</p>}
          {message && <p role="status">{message}</p>}
          {paused ? <>
            <button className="secondary-button" disabled={!confirmed || busy} onClick={() => { void checkImport(); }}>Check imported database records</button>
            <button className="primary-button" disabled={!confirmed || busy || !reviewed} onClick={() => { void checkImport(true); }}>Resume with imported database</button>
            <p>Resuming requires a completed import and a successful check from this original browser. No recovery password is needed for this check.</p>
          </> : <button className="secondary-button" disabled={busy} onClick={() => window.location.assign('/settings')}>Return to settings</button>}
        </div>
      </section>
    </main>
  );
}
