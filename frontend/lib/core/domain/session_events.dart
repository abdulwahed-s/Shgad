import 'dart:async';

class SessionEvents {
  int generation = 0;
  final _resets = StreamController<void>.broadcast();
  Stream<void> get resets => _resets.stream;
  void reset() {
    generation++;
    _resets.add(null);
  }

  Future<void> dispose() => _resets.close();
}

class WatchSessionReset {
  WatchSessionReset(this.events);
  final SessionEvents events;
  Stream<void> call() => events.resets;
}
