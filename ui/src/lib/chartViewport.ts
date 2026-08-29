export function pinnedTrailingPosition({
  scrollOffset,
  viewportLength,
  reservedLength,
  chartLength
}: {
  scrollOffset: number;
  viewportLength: number;
  reservedLength: number;
  chartLength: number;
}) {
  return Math.min(
    Math.max(scrollOffset + viewportLength - reservedLength, 0),
    Math.max(chartLength - reservedLength, 0)
  );
}
