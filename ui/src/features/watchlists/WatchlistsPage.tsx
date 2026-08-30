import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { BookmarkPlus, BriefcaseBusiness, LineChart, Plus, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  useAddSavedWatchlistItem,
  useCreateSavedWatchlist,
  useDeleteSavedWatchlist,
  useRemoveSavedWatchlistItem,
  useRenameSavedWatchlist,
  useSavedWatchlist,
  useSavedWatchlists
} from '../../api/savedWatchlists';
import type { SavedWatchlistItem, WatchlistRow } from '../../api/types';
import {
  candidateFromWatchlistRow,
  defaultScannerResultFilters,
  normalizeScannerResultFilters,
  rowMatchesScannerResultFilters,
  type DisplayCandidate,
  type ScannerResultFilters
} from '../../lib/watchlist';
import { clampScannerColumnWidth } from '../../lib/scannerColumns';
import { rememberRecentTicker } from '../../lib/recentTicker';
import { MultiSelectFilter } from '../../components/MultiSelectFilter';

type WatchlistColumnKey =
  | 'select'
  | 'ticker'
  | 'currentPrice'
  | 'fairValue'
  | 'dcfUpside'
  | 'validation'
  | 'quality'
  | 'dcfEstimate'
  | 'risk'
  | 'strategy'
  | 'added';

type WatchlistSortKey = Exclude<WatchlistColumnKey, 'select'>;
type WatchlistSort = { key: WatchlistSortKey; direction: 'asc' | 'desc' };
type WatchlistDisplayRow = {
  item: SavedWatchlistItem;
  raw: WatchlistRow;
  candidate: DisplayCandidate;
};
type WatchlistPageState = {
  version: 1;
  activeWatchlistId: number | null;
  activeTicker: string | null;
  selectedTickers: string[];
  search: string;
  filters: ScannerResultFilters;
  sort: WatchlistSort;
  widths: Record<WatchlistColumnKey, number>;
  visibility: Record<WatchlistColumnKey, boolean>;
  scrollTop: number;
  scrollLeft: number;
};

const storageKey = 'swing-scanner.saved-watchlists.page.v1';
const columnOrder: WatchlistColumnKey[] = [
  'select',
  'ticker',
  'currentPrice',
  'fairValue',
  'dcfUpside',
  'validation',
  'quality',
  'dcfEstimate',
  'risk',
  'strategy',
  'added'
];
const columnLabels: Record<WatchlistColumnKey, string> = {
  select: 'Row Selection',
  ticker: 'Ticker',
  currentPrice: 'Current Price',
  fairValue: 'Fair Value',
  dcfUpside: 'DCF Upside',
  validation: 'Validation',
  quality: 'Business Quality',
  dcfEstimate: 'DCF Estimate',
  risk: 'Risk',
  strategy: 'Scanner Strategy',
  added: 'Added'
};
const defaultWidths: Record<WatchlistColumnKey, number> = {
  select: 48,
  ticker: 180,
  currentPrice: 125,
  fairValue: 110,
  dcfUpside: 110,
  validation: 155,
  quality: 155,
  dcfEstimate: 165,
  risk: 125,
  strategy: 150,
  added: 135
};
const defaultVisibility = columnOrder.reduce<Record<WatchlistColumnKey, boolean>>(
  (visibility, key) => {
    visibility[key] = true;
    return visibility;
  },
  {} as Record<WatchlistColumnKey, boolean>
);
const validationFilterOptions = [
  { value: 'validated', label: 'Validated' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const qualityFilterOptions = [
  { value: 'strong', label: 'Strong' },
  { value: 'acceptable', label: 'Acceptable' },
  { value: 'weak', label: 'Weak' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const dcfFilterOptions = [
  { value: 'undervalued', label: 'Undervalued' },
  { value: 'fairly_valued', label: 'Fairly Valued' },
  { value: 'overvalued', label: 'Overvalued' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const riskFilterOptions = [
  { value: 'low', label: 'Low' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'high', label: 'High' },
  { value: 'not_calculated', label: 'Not Calculated' }
] as const;
const defaultState: WatchlistPageState = {
  version: 1,
  activeWatchlistId: null,
  activeTicker: null,
  selectedTickers: [],
  search: '',
  filters: defaultScannerResultFilters,
  sort: { key: 'ticker', direction: 'asc' },
  widths: defaultWidths,
  visibility: defaultVisibility,
  scrollTop: 0,
  scrollLeft: 0
};

export function WatchlistsPage() {
  const navigate = useNavigate();
  const listsQuery = useSavedWatchlists();
  const createList = useCreateSavedWatchlist();
  const renameList = useRenameSavedWatchlist();
  const deleteList = useDeleteSavedWatchlist();
  const addItem = useAddSavedWatchlistItem();
  const removeItem = useRemoveSavedWatchlistItem();
  const [state, setState] = useState(loadWatchlistPageState);
  const [newListName, setNewListName] = useState('');
  const [tickerDraft, setTickerDraft] = useState('');
  const tableRef = useRef<HTMLTableElement | null>(null);
  const tableWrapRef = useRef<HTMLDivElement | null>(null);
  const lists = listsQuery.data?.watchlists ?? [];
  const activeWatchlistId = lists.some((list) => list.id === state.activeWatchlistId)
    ? state.activeWatchlistId
    : lists[0]?.id ?? null;
  const detailQuery = useSavedWatchlist(activeWatchlistId);
  const activeList = detailQuery.data;

  useEffect(() => {
    if (activeWatchlistId !== state.activeWatchlistId) {
      updateState({
        activeWatchlistId,
        activeTicker: null,
        selectedTickers: []
      });
    }
  }, [activeWatchlistId, state.activeWatchlistId]);

  useEffect(() => {
    const wrap = tableWrapRef.current;
    if (!wrap) return;
    wrap.scrollTop = state.scrollTop;
    wrap.scrollLeft = state.scrollLeft;
  }, [activeWatchlistId]);

  const displayRows = useMemo(
    () =>
      (activeList?.items ?? []).map<WatchlistDisplayRow>((item, index) => {
        const raw = { ...item.data, Ticker: item.ticker };
        return { item, raw, candidate: candidateFromWatchlistRow(raw, index) };
      }),
    [activeList?.items]
  );
  const filteredRows = useMemo(() => {
    const query = state.search.trim().toLowerCase();
    return displayRows.filter(
      (row) =>
        rowMatchesScannerResultFilters(row.raw, state.filters) &&
        (!query ||
          row.candidate.ticker.toLowerCase().includes(query) ||
          row.candidate.companyName.toLowerCase().includes(query))
    );
  }, [displayRows, state.filters, state.search]);
  const sortedRows = useMemo(
    () => sortWatchlistRows(filteredRows, state.sort),
    [filteredRows, state.sort]
  );
  const visibleColumns = columnOrder.filter((key) => state.visibility[key]);
  const selectedSet = new Set(state.selectedTickers);
  const activeRow = displayRows.find((row) => row.candidate.ticker === state.activeTicker) ?? null;
  const mutationError =
    createList.error ?? renameList.error ?? deleteList.error ?? addItem.error ?? removeItem.error;
  const busy =
    createList.isPending ||
    renameList.isPending ||
    deleteList.isPending ||
    addItem.isPending ||
    removeItem.isPending;

  function updateState(changes: Partial<WatchlistPageState>) {
    setState((current) => {
      const next = { ...current, ...changes };
      localStorage.setItem(storageKey, JSON.stringify(next));
      return next;
    });
  }

  async function createWatchlist() {
    const name = newListName.trim();
    if (!name) return;
    const created = await createList.mutateAsync(name);
    setNewListName('');
    updateState({ activeWatchlistId: created.id, activeTicker: null, selectedTickers: [] });
  }

  async function renameWatchlist() {
    if (!activeList) return;
    const name = window.prompt('Watchlist name', activeList.name)?.trim();
    if (!name || name === activeList.name) return;
    await renameList.mutateAsync({ watchlistId: activeList.id, name });
  }

  async function deleteWatchlist() {
    if (!activeList || !window.confirm(`Delete “${activeList.name}” and all of its saved tickers?`)) {
      return;
    }
    await deleteList.mutateAsync(activeList.id);
    updateState({ activeWatchlistId: null, activeTicker: null, selectedTickers: [] });
  }

  async function addTicker() {
    const ticker = normalizeTicker(tickerDraft);
    if (!activeWatchlistId || !ticker) return;
    await addItem.mutateAsync({
      watchlistId: activeWatchlistId,
      ticker,
      source: 'watchlists',
      data: { Ticker: ticker }
    });
    setTickerDraft('');
    selectTicker(ticker);
  }

  async function removeSelected() {
    if (!activeWatchlistId || selectedSet.size === 0) return;
    const tickers = [...selectedSet];
    if (!window.confirm(`Remove ${tickers.length} ticker${tickers.length === 1 ? '' : 's'} from this watchlist?`)) {
      return;
    }
    await Promise.all(
      tickers.map((ticker) => removeItem.mutateAsync({ watchlistId: activeWatchlistId, ticker }))
    );
    updateState({
      selectedTickers: [],
      activeTicker: tickers.includes(state.activeTicker ?? '') ? null : state.activeTicker
    });
  }

  function selectTicker(ticker: string) {
    updateState({ activeTicker: ticker });
    rememberRecentTicker(ticker, 'watchlists', activeWatchlistId);
  }

  function openChart(ticker: string) {
    selectTicker(ticker);
    navigate('/candidates', {
      state: { ticker, maximized: true, savedWatchlistId: activeWatchlistId }
    });
  }

  function openFundamentals(ticker: string) {
    selectTicker(ticker);
    const params = new URLSearchParams({ ticker, strategy: 'all' });
    if (activeWatchlistId !== null) params.set('watchlist_id', String(activeWatchlistId));
    navigate(`/fundamentals?${params.toString()}`);
  }

  function toggleSelected(ticker: string) {
    const next = new Set(selectedSet);
    if (next.has(ticker)) next.delete(ticker);
    else next.add(ticker);
    updateState({ selectedTickers: [...next] });
  }

  function toggleAll() {
    const visibleTickers = sortedRows.map((row) => row.candidate.ticker);
    const allSelected = visibleTickers.length > 0 && visibleTickers.every((ticker) => selectedSet.has(ticker));
    const next = new Set(selectedSet);
    visibleTickers.forEach((ticker) => allSelected ? next.delete(ticker) : next.add(ticker));
    updateState({ selectedTickers: [...next] });
  }

  function changeSort(key: WatchlistSortKey) {
    updateState({
      sort: state.sort.key === key
        ? { key, direction: state.sort.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' }
    });
  }

  function startColumnResize(key: WatchlistColumnKey, event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = state.widths[key];
    const pointerId = event.pointerId;
    const handle = event.currentTarget;
    handle.setPointerCapture(pointerId);
    function move(moveEvent: PointerEvent) {
      if (moveEvent.pointerId !== pointerId) return;
      updateState({
        widths: {
          ...state.widths,
          [key]: clampScannerColumnWidth(startWidth + moveEvent.clientX - startX)
        }
      });
    }
    function finish(upEvent: PointerEvent) {
      if (upEvent.pointerId !== pointerId) return;
      if (handle.hasPointerCapture(pointerId)) handle.releasePointerCapture(pointerId);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
    }
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', finish);
    window.addEventListener('pointercancel', finish);
  }

  function autoFitColumn(key: WatchlistColumnKey) {
    const table = tableRef.current;
    const columnIndex = visibleColumns.indexOf(key);
    if (!table || columnIndex < 0) return;
    const cells = table.querySelectorAll<HTMLElement>(
      `tr > :nth-child(${columnIndex + 1})`
    );
    const measured = Math.max(
      defaultWidths[key],
      ...Array.from(cells).map((cell) => Math.ceil(cell.scrollWidth + 24))
    );
    updateState({ widths: { ...state.widths, [key]: clampScannerColumnWidth(measured) } });
  }

  return (
    <div className="watchlists-page">
      <section className="panel watchlists-toolbar" aria-label="Saved watchlist controls">
        <div className="watchlist-list-controls">
          <label>
            Watchlist
            <select
              value={activeWatchlistId ?? ''}
              onChange={(event) =>
                updateState({
                  activeWatchlistId: Number(event.target.value) || null,
                  activeTicker: null,
                  selectedTickers: []
                })
              }
            >
              {lists.length === 0 && <option value="">No watchlists</option>}
              {lists.map((list) => (
                <option key={list.id} value={list.id}>{list.name} ({list.item_count})</option>
              ))}
            </select>
          </label>
          <form onSubmit={(event) => { event.preventDefault(); void createWatchlist(); }}>
            <input
              aria-label="New watchlist name"
              placeholder="New watchlist name"
              maxLength={80}
              value={newListName}
              onChange={(event) => setNewListName(event.target.value)}
            />
            <button className="secondary-button" type="submit" disabled={!newListName.trim() || busy}>
              <Plus size={16} /> New
            </button>
          </form>
          <button className="secondary-button" type="button" disabled={!activeList || busy} onClick={() => void renameWatchlist()}>
            Rename
          </button>
          <button className="danger-button" type="button" disabled={!activeList || busy} onClick={() => void deleteWatchlist()}>
            <Trash2 size={16} /> Delete List
          </button>
        </div>
        <div className="watchlist-ticker-controls">
          <form onSubmit={(event) => { event.preventDefault(); void addTicker(); }}>
            <input
              aria-label="Ticker to add"
              placeholder="Add ticker"
              value={tickerDraft}
              onChange={(event) => setTickerDraft(event.target.value.toUpperCase())}
            />
            <button className="primary-button" type="submit" disabled={!activeList || !normalizeTicker(tickerDraft) || busy}>
              <BookmarkPlus size={16} /> Add
            </button>
          </form>
          <button className="secondary-button" type="button" disabled={!activeRow} onClick={() => activeRow && openChart(activeRow.candidate.ticker)}>
            <LineChart size={16} /> Chart{activeRow ? `: ${activeRow.candidate.ticker}` : ''}
          </button>
          <button className="secondary-button" type="button" disabled={!activeRow} onClick={() => activeRow && openFundamentals(activeRow.candidate.ticker)}>
            <BriefcaseBusiness size={16} /> Fundamentals{activeRow ? `: ${activeRow.candidate.ticker}` : ''}
          </button>
          <button className="danger-button" type="button" disabled={selectedSet.size === 0 || busy} onClick={() => void removeSelected()}>
            <Trash2 size={16} /> Remove{selectedSet.size > 0 ? ` (${selectedSet.size})` : ''}
          </button>
        </div>
        {mutationError && <div className="saved-watchlist-error">{mutationError.message}</div>}
      </section>

      <section className="panel watchlist-results-panel" aria-labelledby="watchlist-results-title">
        <div className="panel-header">
          <div>
            <h2 id="watchlist-results-title">{activeList?.name ?? 'Saved Watchlist'}</h2>
            <p>{sortedRows.length} displayed of {displayRows.length} saved tickers</p>
          </div>
          <details className="column-chooser">
            <summary className="secondary-button">Columns</summary>
            <div className="column-chooser-menu">
              <strong>Show or hide columns</strong>
              <div className="column-chooser-options">
                {columnOrder.filter((key) => key !== 'select' && key !== 'ticker').map((key) => (
                  <label key={key}>
                    <input
                      type="checkbox"
                      checked={state.visibility[key]}
                      onChange={() => updateState({
                        visibility: { ...state.visibility, [key]: !state.visibility[key] }
                      })}
                    />
                    {columnLabels[key]}
                  </label>
                ))}
              </div>
              <button className="secondary-button" type="button" onClick={() => updateState({ visibility: defaultVisibility })}>
                Show All
              </button>
            </div>
          </details>
        </div>

        <div className="scanner-result-filter-bar" aria-label="Watchlist filters">
          <div className="scanner-result-filter-grid watchlist-filter-grid">
            <label>
              Search
              <input placeholder="Ticker or company" value={state.search} onChange={(event) => updateState({ search: event.target.value })} />
            </label>
            <MultiSelectFilter label="Validation" allLabel="All validation statuses" selected={state.filters.validation} options={validationFilterOptions} onChange={(validation) => updateState({ filters: { ...state.filters, validation } })} />
            <MultiSelectFilter label="Business Quality" allLabel="All quality levels" selected={state.filters.quality} options={qualityFilterOptions} onChange={(quality) => updateState({ filters: { ...state.filters, quality } })} />
            <MultiSelectFilter label="DCF Estimate" allLabel="All DCF estimates" selected={state.filters.dcf} options={dcfFilterOptions} onChange={(dcf) => updateState({ filters: { ...state.filters, dcf } })} />
            <MultiSelectFilter label="Risk" allLabel="All risk levels" selected={state.filters.risk} options={riskFilterOptions} onChange={(risk) => updateState({ filters: { ...state.filters, risk } })} />
            <label>Minimum Price<input type="number" min="0" step="0.01" value={state.filters.minPrice ?? ''} onChange={(event) => updateState({ filters: { ...state.filters, minPrice: priceOrNull(event.target.value) } })} /></label>
            <label>Maximum Price<input type="number" min="0" step="0.01" value={state.filters.maxPrice ?? ''} onChange={(event) => updateState({ filters: { ...state.filters, maxPrice: priceOrNull(event.target.value) } })} /></label>
          </div>
          <button className="secondary-button" type="button" onClick={() => updateState({ search: '', filters: defaultScannerResultFilters })}>Clear Filters</button>
        </div>

        <div
          ref={tableWrapRef}
          className="table-wrap watchlist-table-wrap"
          onScroll={(event) => updateState({
            scrollTop: event.currentTarget.scrollTop,
            scrollLeft: event.currentTarget.scrollLeft
          })}
        >
          <table
            ref={tableRef}
            className="data-table scanner-results-table"
            style={{ width: visibleColumns.reduce((total, key) => total + state.widths[key], 0), minWidth: '100%' }}
          >
            <colgroup>{visibleColumns.map((key) => <col key={key} style={{ width: state.widths[key] }} />)}</colgroup>
            <thead><tr>{visibleColumns.map((key) => (
              <th key={key}>
                {key === 'select' ? (
                  <input type="checkbox" aria-label="Select all visible tickers" checked={sortedRows.length > 0 && sortedRows.every((row) => selectedSet.has(row.candidate.ticker))} onChange={toggleAll} />
                ) : (
                  <button className="sortable-header" type="button" onClick={() => changeSort(key)}>
                    {columnLabels[key]} {state.sort.key === key ? (state.sort.direction === 'asc' ? '↑' : '↓') : ''}
                  </button>
                )}
                <div
                  className="column-resize-handle"
                  role="separator"
                  aria-label={`Resize ${columnLabels[key]}`}
                  aria-orientation="vertical"
                  title={`Drag to resize ${columnLabels[key]}; double-click to fit content`}
                  tabIndex={0}
                  onPointerDown={(event) => startColumnResize(key, event)}
                  onDoubleClick={() => autoFitColumn(key)}
                  onKeyDown={(event) => {
                    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                    event.preventDefault();
                    updateState({
                      widths: {
                        ...state.widths,
                        [key]: clampScannerColumnWidth(
                          state.widths[key] + (event.key === 'ArrowRight' ? 12 : -12)
                        )
                      }
                    });
                  }}
                />
              </th>
            ))}</tr></thead>
            <tbody>
              {sortedRows.map((row) => {
                const ticker = row.candidate.ticker;
                return (
                  <tr
                    key={ticker}
                    className={ticker === state.activeTicker ? 'selected-row selectable-row' : 'selectable-row'}
                    onClick={() => selectTicker(ticker)}
                  >
                    {visibleColumns.map((key) => (
                      <WatchlistCell
                        key={key}
                        columnKey={key}
                        row={row}
                        selected={selectedSet.has(ticker)}
                        onToggle={() => toggleSelected(ticker)}
                        onTickerClick={() => openChart(ticker)}
                      />
                    ))}
                  </tr>
                );
              })}
              {!detailQuery.isLoading && sortedRows.length === 0 && (
                <tr><td className="empty-cell" colSpan={visibleColumns.length}>
                  {activeList ? 'No saved tickers match the current filters.' : 'Create a watchlist to begin.'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function WatchlistCell({
  columnKey,
  row,
  selected,
  onToggle,
  onTickerClick
}: {
  columnKey: WatchlistColumnKey;
  row: WatchlistDisplayRow;
  selected: boolean;
  onToggle: () => void;
  onTickerClick: () => void;
}) {
  const candidate = row.candidate;
  if (columnKey === 'select') return <td><input type="checkbox" checked={selected} onClick={(event) => event.stopPropagation()} onChange={onToggle} aria-label={`Select ${candidate.ticker}`} /></td>;
  if (columnKey === 'ticker') return <td className="ticker-cell"><button className="ticker-link ticker-link-button" type="button" onClick={(event) => { event.stopPropagation(); onTickerClick(); }}>{candidate.ticker}</button>{candidate.companyName && <span className="company-name">{candidate.companyName}</span>}</td>;
  if (columnKey === 'validation') return <SummaryCell label={candidate.validationLabel} value={score(candidate.validationScore)} />;
  if (columnKey === 'quality') return <SummaryCell label={candidate.qualityLabel} value={score(candidate.qualityScore)} />;
  if (columnKey === 'dcfEstimate') return <SummaryCell label={candidate.dcfLabel} value={candidate.marginOfSafety} />;
  if (columnKey === 'risk') return <SummaryCell label={candidate.riskLabel} value={score(candidate.riskScore)} />;
  const value: Record<Exclude<WatchlistColumnKey, 'select' | 'ticker' | 'validation' | 'quality' | 'dcfEstimate' | 'risk'>, string> = {
    currentPrice: candidate.currentPrice,
    fairValue: candidate.fairValue,
    dcfUpside: candidate.marginOfSafety,
    strategy: candidate.strategy,
    added: formatDate(row.item.added_at)
  };
  return <td>{value[columnKey]}</td>;
}

function SummaryCell({ label, value }: { label: string; value: string | null }) {
  return <td><span className="fundamental-summary-cell"><strong>{label}</strong>{value && <span>{value}</span>}</span></td>;
}

function sortWatchlistRows(rows: WatchlistDisplayRow[], sort: WatchlistSort) {
  const direction = sort.direction === 'asc' ? 1 : -1;
  return [...rows].sort((left, right) => {
    const leftValue = watchlistSortValue(left, sort.key);
    const rightValue = watchlistSortValue(right, sort.key);
    if (typeof leftValue === 'number' && typeof rightValue === 'number') return ((leftValue - rightValue) * direction) || left.candidate.ticker.localeCompare(right.candidate.ticker);
    return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' }) * direction || left.candidate.ticker.localeCompare(right.candidate.ticker);
  });
}

function watchlistSortValue(row: WatchlistDisplayRow, key: WatchlistSortKey): string | number {
  if (key === 'added') return Date.parse(row.item.added_at) || 0;
  const values: Record<Exclude<WatchlistSortKey, 'added'>, string> = {
    ticker: row.candidate.ticker,
    currentPrice: row.candidate.currentPrice,
    fairValue: row.candidate.fairValue,
    dcfUpside: row.candidate.marginOfSafety,
    validation: row.candidate.validationScore,
    quality: row.candidate.qualityScore,
    dcfEstimate: row.candidate.marginOfSafety,
    risk: row.candidate.riskScore,
    strategy: row.candidate.strategy
  };
  const value = values[key];
  const numeric = Number(value.replace(/[$,%]/g, '').replaceAll(',', ''));
  return Number.isFinite(numeric) ? numeric : value;
}

export function loadWatchlistPageState(): WatchlistPageState {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) ?? 'null');
    if (parsed?.version !== 1) return defaultState;
    const storedWidths = isRecord(parsed.widths) ? parsed.widths : {};
    const storedVisibility = isRecord(parsed.visibility) ? parsed.visibility : {};
    return {
      ...defaultState,
      activeWatchlistId: integerOrNull(parsed.activeWatchlistId),
      activeTicker: typeof parsed.activeTicker === 'string' ? parsed.activeTicker : null,
      selectedTickers: Array.isArray(parsed.selectedTickers)
        ? parsed.selectedTickers.filter((ticker: unknown): ticker is string => typeof ticker === 'string')
        : [],
      search: typeof parsed.search === 'string' ? parsed.search : '',
      filters: normalizeScannerResultFilters(parsed.filters),
      sort: normalizeWatchlistSort(parsed.sort),
      widths: columnOrder.reduce<Record<WatchlistColumnKey, number>>((widths, key) => {
        const value = storedWidths[key];
        widths[key] = typeof value === 'number' && Number.isFinite(value)
          ? clampScannerColumnWidth(value)
          : defaultWidths[key];
        return widths;
      }, { ...defaultWidths }),
      visibility: columnOrder.reduce<Record<WatchlistColumnKey, boolean>>((visibility, key) => {
        const value = storedVisibility[key];
        visibility[key] = key === 'select' || key === 'ticker'
          ? true
          : typeof value === 'boolean' ? value : defaultVisibility[key];
        return visibility;
      }, { ...defaultVisibility }),
      scrollTop: finiteNonnegative(parsed.scrollTop),
      scrollLeft: finiteNonnegative(parsed.scrollLeft)
    };
  } catch {
    localStorage.removeItem(storageKey);
    return defaultState;
  }
}

function normalizeWatchlistSort(value: unknown): WatchlistSort {
  if (!isRecord(value) || !columnOrder.includes(value.key as WatchlistColumnKey)) {
    return defaultState.sort;
  }
  const key = value.key as WatchlistColumnKey;
  if (key === 'select') return defaultState.sort;
  return { key, direction: value.direction === 'desc' ? 'desc' : 'asc' };
}

function normalizeTicker(value: string) {
  const ticker = value.trim().toUpperCase();
  return ticker && /^[A-Z0-9.-]{1,20}$/.test(ticker) ? ticker : '';
}
function priceOrNull(value: string) { const number = Number(value); return value !== '' && Number.isFinite(number) && number >= 0 ? number : null; }
function score(value: string) { return value === 'n/a' ? null : `${value}/100`; }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(); }
function isRecord(value: unknown): value is Record<string, unknown> { return Boolean(value) && typeof value === 'object' && !Array.isArray(value); }
function integerOrNull(value: unknown) { return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null; }
function finiteNonnegative(value: unknown) { return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0; }
