abstract interface class ConnectionRepository {
  bool get online;
  Stream<bool> get changes;
  Future<bool> check();
}

class WatchConnectivity {
  WatchConnectivity(this.repository);
  final ConnectionRepository repository;
  bool get online => repository.online;
  Stream<bool> call() => repository.changes;
}

class CheckConnectivity {
  CheckConnectivity(this.repository);
  final ConnectionRepository repository;
  Future<bool> call() => repository.check();
}
