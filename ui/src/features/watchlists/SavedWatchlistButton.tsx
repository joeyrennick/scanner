import { useState } from 'react';
import { BookmarkPlus, LoaderCircle, Plus } from 'lucide-react';
import type { WatchlistRow } from '../../api/types';
import {
  useAddSavedWatchlistItem,
  useCreateSavedWatchlist,
  useRemoveSavedWatchlistItem,
  useSavedWatchlists
} from '../../api/savedWatchlists';

export function SavedWatchlistButton({
  ticker,
  source,
  data,
  label = 'Watchlists'
}: {
  ticker: string;
  source: string;
  data: WatchlistRow;
  label?: string;
}) {
  const watchlists = useSavedWatchlists();
  const addItem = useAddSavedWatchlistItem();
  const removeItem = useRemoveSavedWatchlistItem();
  const createWatchlist = useCreateSavedWatchlist();
  const [newName, setNewName] = useState('');
  const normalizedTicker = ticker.trim().toUpperCase();
  const lists = watchlists.data?.watchlists ?? [];
  const membershipCount = lists.filter((watchlist) =>
    watchlist.tickers.includes(normalizedTicker)
  ).length;
  const pending = addItem.isPending || removeItem.isPending || createWatchlist.isPending;
  const error = addItem.error ?? removeItem.error ?? createWatchlist.error ?? watchlists.error;

  async function toggleMembership(watchlistId: number, member: boolean) {
    if (member) {
      await removeItem.mutateAsync({ watchlistId, ticker: normalizedTicker });
    } else {
      await addItem.mutateAsync({
        watchlistId,
        ticker: normalizedTicker,
        source,
        data: { ...data, Ticker: normalizedTicker }
      });
    }
  }

  async function createAndAdd() {
    const name = newName.trim();
    if (!name || !normalizedTicker) return;
    const watchlist = await createWatchlist.mutateAsync(name);
    await addItem.mutateAsync({
      watchlistId: watchlist.id,
      ticker: normalizedTicker,
      source,
      data: { ...data, Ticker: normalizedTicker }
    });
    setNewName('');
  }

  return (
    <details
      className="saved-watchlist-menu"
      onClick={(event) => event.stopPropagation()}
    >
      <summary className="secondary-button" title={`Manage ${normalizedTicker} watchlists`}>
        <BookmarkPlus size={17} />
        {label}{membershipCount > 0 ? ` (${membershipCount})` : ''}
      </summary>
      <div className="saved-watchlist-menu-content">
        <strong>{normalizedTicker}</strong>
        <span className="muted-text">Add to one or more watchlists</span>
        {watchlists.isLoading && (
          <span className="saved-watchlist-loading"><LoaderCircle size={15} /> Loading…</span>
        )}
        <div className="saved-watchlist-memberships">
          {lists.map((watchlist) => {
            const member = watchlist.tickers.includes(normalizedTicker);
            return (
              <label key={watchlist.id}>
                <input
                  type="checkbox"
                  checked={member}
                  disabled={pending}
                  onChange={() => void toggleMembership(watchlist.id, member)}
                />
                <span>{watchlist.name}</span>
                <small>{watchlist.item_count}</small>
              </label>
            );
          })}
          {!watchlists.isLoading && lists.length === 0 && (
            <span className="muted-text">Create your first watchlist below.</span>
          )}
        </div>
        <form
          className="saved-watchlist-create"
          onSubmit={(event) => {
            event.preventDefault();
            void createAndAdd();
          }}
        >
          <input
            aria-label="New watchlist name"
            placeholder="New watchlist name"
            maxLength={80}
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
          />
          <button type="submit" disabled={pending || !newName.trim()} title="Create and add">
            <Plus size={16} />
          </button>
        </form>
        {error && <span className="saved-watchlist-error">{error.message}</span>}
      </div>
    </details>
  );
}
