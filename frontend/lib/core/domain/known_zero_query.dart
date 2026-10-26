/// Immutable server query proof for an observed empty aggregate, never SQL.
class KnownZeroQuery {
  const KnownZeroQuery({
    required this.tool,
    required this.start,
    required this.end,
    required this.matchingRows,
    required this.originalQuery,
  });
  final String tool, start, end, originalQuery;
  final int matchingRows;
}
