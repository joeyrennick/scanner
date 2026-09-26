import { useQuery } from '@tanstack/react-query';
import { usePlatform } from '../../platform/PlatformProvider';

export function RuntimeReadiness() {
  const runtime = usePlatform();
  const query = useQuery({ queryKey: ['runtime', 'v1', runtime.kind], queryFn: () => runtime.readInfo(), retry: false });
  return <section className="panel" aria-labelledby="runtime-readiness-title">
    <div className="panel-header"><div><h2 id="runtime-readiness-title">Application Runtime</h2>
      <p>Connection capabilities and backend-resolved storage locations.</p></div></div>
    <div className="settings-form">
      {query.isPending && <p>Checking runtime…</p>}
      {query.isError && <><p role="alert">Runtime information is unavailable. {query.error.message}</p>
        <button type="button" onClick={() => { void query.refetch(); }}>Retry runtime check</button></>}
      {query.data && <>
        <p>Connected: {query.data.mode} · API version {query.data.api_versions.join(', ')}</p>
        <p>{query.data.capabilities.report_files ? 'Report downloads are available through the API.' : 'Report downloads are not available in this runtime.'}</p>
        <p>{query.data.capabilities.native_keychain ? 'Native credential storage is available.' : 'Native Keychain integration is not yet enabled.'}</p>
        <dl>{Object.entries(query.data.paths).map(([label, path]) => <div key={label}>
          <dt>{label.charAt(0).toUpperCase() + label.slice(1)}</dt><dd style={{ overflowWrap: 'anywhere' }}>{path}</dd>
        </div>)}</dl>
      </>}
    </div>
  </section>;
}
