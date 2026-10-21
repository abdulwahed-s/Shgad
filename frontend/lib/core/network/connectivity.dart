import 'dart:async';
import 'package:dio/dio.dart';
import 'platform_network.dart';
import '../domain/connectivity.dart';

class ConnectionSource {
  ConnectionSource() {
    watchPlatformNetwork(set);
  }
  final _changes = StreamController<bool>.broadcast();
  bool online = platformOnline();
  Stream<bool> get changes => _changes.stream;
  void set(bool value) {
    online = value;
    if (!_changes.isClosed) _changes.add(value);
  }

  Future<void> dispose() => _changes.close();
}

class DeviceConnectionRepository implements ConnectionRepository {
  DeviceConnectionRepository(this.source, this.dio);
  final ConnectionSource source;
  final Dio dio;
  @override
  bool get online => source.online;
  @override
  Stream<bool> get changes => source.changes;
  @override
  Future<bool> check() async {
    if (!platformOnline()) {
      source.set(false);
      return false;
    }
    try {
      await dio.get<Object>(
        '/health',
        options: Options(receiveTimeout: const Duration(seconds: 3)),
      );
      source.set(true);
    } on DioException {
      source.set(false);
    }
    return source.online;
  }
}
