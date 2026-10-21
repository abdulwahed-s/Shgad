import 'dart:math';

class NewClientId {
  final _random = Random.secure();
  String call() =>
      List.generate(24, (_) => _random.nextInt(16).toRadixString(16)).join();
}
