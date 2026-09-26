import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { loadSetup, saveSetup, type SetupStatus } from '../../api/setup';
import { useApplicationApi } from '../../platform/PlatformProvider';

const setupKey = ['application-setup', 'v1'] as const;

export function SECContactSetup() {
  const api = useApplicationApi();
  const client = useQueryClient();
  const [reload, setReload] = useState(0);
  const [saved, setSaved] = useState(false);
  const query = useQuery({
    queryKey: setupKey, queryFn: () => loadSetup(api), retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always'
  });
  return <section className="panel" aria-labelledby="sec-contact-title">
    <div className="panel-header"><div><h2 id="sec-contact-title">SEC Contact Setup</h2>
      <p>Contact details for downloading company fundamentals from SEC EDGAR.</p></div></div>
    <div className="settings-form">
      <p>This is not a password or an SEC login. Choose an application/organization name and an email where you can be contacted.
        Scanner saves them on this Mac and sends them to the SEC in the User-Agent header when requesting data.{' '}
        <a href="https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data" target="_blank" rel="noreferrer">SEC access guidance</a></p>
      {query.isFetching && <p>Loading saved setup…</p>}
      {query.isError && <><p role="alert">Setup could not be loaded. {query.error.message}</p>
        <button type="button" onClick={() => { void query.refetch(); }}>Retry loading setup</button></>}
      {!query.isFetching && !query.isError && query.data && <ContactForm
        key={`${query.data.configuration.revision}:${reload}`} status={query.data} saved={saved}
        onSaved={(status) => { client.setQueryData(setupKey, status); setSaved(true); }}
        onReload={async () => { setSaved(false); const result = await query.refetch(); if (!result.isError) setReload(value => value + 1); }} />}
    </div>
  </section>;
}

function ContactForm({ status, saved, onSaved, onReload }: {
  status: SetupStatus; saved: boolean; onSaved: (status: SetupStatus) => void; onReload: () => Promise<void>;
}) {
  const api = useApplicationApi();
  const original = status.configuration.sec_identity;
  const [name, setName] = useState(original?.application_name ?? 'Swing Scanner');
  const [email, setEmail] = useState(original?.contact_email ?? '');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = name !== (original?.application_name ?? 'Swing Scanner') || email !== (original?.contact_email ?? '');
  useEffect(() => {
    if (!dirty && !pending) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, pending]);

  async function submit() {
    if (pending || error) return;
    setPending(true);
    try {
      onSaved(await saveSetup(api, { application_name: name.trim(), contact_email: email.trim() }, status.configuration.revision));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unknown save error');
    } finally { setPending(false); }
  }

  return <form className="settings-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <p>{status.sec_configured ? `Contact configured (${status.sec_source}).` : 'SEC contact is not configured.'}</p>
    {status.sec_source === 'environment' && <p role="note">The backend launcher’s SEC_USER_AGENT overrides saved contact details.
      Saving here does not change that override; changing it requires restarting the backend.</p>}
    {status.sec_error && <p role="alert">{status.sec_error}</p>}
    {status.sec_user_agent && <p>Current request identity: <code>{status.sec_user_agent}</code></p>}
    <label>Application or organization name
      <input required maxLength={120} pattern="[ -~]+" value={name} disabled={pending}
        onChange={(event) => setName(event.target.value)} autoComplete="off" /></label>
    <label>Contact email
      <input type="email" required maxLength={254} value={email} disabled={pending} placeholder="you@example.com"
        onChange={(event) => setEmail(event.target.value)} autoComplete="email" /></label>
    <p>Saving makes no SEC request. New SEC provider instances use the saved identity; existing work keeps its original identity.
      Your Massive credential and backup recovery password are unchanged.</p>
    <button type="submit" disabled={pending || !!error || !name.trim() || !email.trim() || (!dirty && !!original)}>
      {pending ? 'Saving contact…' : 'Save SEC contact'}</button>
    {saved && !dirty && <p role="status">Contact saved on this Mac.{status.sec_source === 'environment' ? ' The launcher override still applies.' : ' New SEC requests can use it without restarting.'}</p>}
    {error && <p role="alert">Save was not confirmed. {error} Your draft remains in the fields. Do not retry until you reload saved setup.</p>}
    {(dirty || error) && <button type="button" disabled={pending} onClick={() => { void onReload(); }}>Discard draft and reload saved setup</button>}
  </form>;
}
