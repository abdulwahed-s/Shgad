import 'dart:async';

class SessionEvents {
  int generation = 0;
  final _resets = StreamController<void>.broadcast();
  final _changes = StreamController<void>.broadcast();
  Stream<void> get resets => _resets.stream;
  Stream<void> get changes => _changes.stream;
  void changed() {
    generation++;
    _changes.add(null);
  }

  void reset() {
    generation++;
    _resets.add(null);
  }

  Future<void> dispose() async {
    await _resets.close();
    await _changes.close();
  }
}

class WatchSessionReset {
  WatchSessionReset(this.events);
  final SessionEvents events;
  Stream<void> call() => events.resets;
}

class WatchLedgerChanges {
  WatchLedgerChanges(this.events);
  final SessionEvents events;
  Stream<void> call() => events.changes;
}
