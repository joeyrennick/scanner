import { useState } from 'react';
import type { ReactNode } from 'react';
import { usePlatform } from '../platform/PlatformProvider';

type Props = { children: ReactNode; className?: string } & (
  { reportId: string; preview?: boolean; jobId?: never; outputName?: never }
  | { jobId: string; outputName: string; reportId?: never; preview?: never }
);

export function FileActionButton(props: Props) {
  const { files } = usePlatform();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function openFile() {
    setBusy(true);
    setError('');
    try {
      if (props.reportId !== undefined) {
        await (props.preview ? files.previewReport(props.reportId) : files.downloadReport(props.reportId));
      } else await files.downloadJobOutput(props.jobId, props.outputName);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'File could not be opened. Try again.');
    } finally { setBusy(false); }
  }
  return <span>
    <button type="button" className={props.className ?? 'link-button'} disabled={busy} onClick={() => { void openFile(); }}>
      {busy ? 'Opening…' : props.children}
    </button>
    {error && <span role="alert"> {error}</span>}
  </span>;
}
