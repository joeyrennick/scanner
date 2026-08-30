export type MultiSelectFilterOption<T extends string> = {
  value: T;
  label: string;
};

export function MultiSelectFilter<T extends string>({
  label,
  allLabel,
  selected,
  options,
  onChange
}: {
  label: string;
  allLabel: string;
  selected: T[];
  options: readonly MultiSelectFilterOption<T>[];
  onChange: (selected: T[]) => void;
}) {
  const selectedLabels = options
    .filter((option) => selected.includes(option.value))
    .map((option) => option.label);
  const summary = selectedLabels.length === 0
    ? allLabel
    : selectedLabels.length <= 2
      ? selectedLabels.join(', ')
      : `${selectedLabels.length} selected`;

  function toggle(value: T) {
    onChange(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
    );
  }

  return (
    <div className="multi-select-filter-field">
      <span>{label}</span>
      <details className="multi-select-filter">
        <summary title={selectedLabels.length > 0 ? selectedLabels.join(', ') : allLabel}>
          <span>{summary}</span>
          <span aria-hidden="true">▾</span>
        </summary>
        <div className="multi-select-filter-menu">
          <label className="multi-select-all-option">
            <input
              type="checkbox"
              checked={selected.length === 0}
              onChange={() => onChange([])}
            />
            {allLabel}
          </label>
          {options.map((option) => (
            <label key={option.value}>
              <input
                type="checkbox"
                checked={selected.includes(option.value)}
                onChange={() => toggle(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}
