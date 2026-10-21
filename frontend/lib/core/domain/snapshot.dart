class Snapshot<T> {
  const Snapshot(this.data, this.updatedAt, {this.offline = false});
  final T data;
  final String updatedAt;
  final bool offline;
}
