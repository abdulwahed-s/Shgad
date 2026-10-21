import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class CacheRecord {
  const CacheRecord(this.json, this.updatedAt);
  final Map<String, dynamic> json;
  final String updatedAt;
}

abstract interface class ResponseCache {
  Future<CacheRecord?> read(String key);
  Future<void> write(String key, CacheRecord record);
  Future<void> clear();
}

class PreferencesResponseCache implements ResponseCache {
  PreferencesResponseCache(this.preferences, this.namespace);
  final SharedPreferencesAsync preferences;
  final String namespace;
  String _key(String key) => 'shgad.v1.$namespace.$key';
  @override
  Future<CacheRecord?> read(String key) async {
    try {
      final text = await preferences.getString(_key(key));
      if (text == null) return null;
      final json = jsonDecode(text) as Map<String, dynamic>;
      return CacheRecord(
        Map<String, dynamic>.from(json['data'] as Map),
        json['updated_at'] as String,
      );
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> write(String key, CacheRecord record) async {
    // This is a disposable read cache, never a ledger or a write queue.
    try {
      await preferences.setString(
        _key(key),
        jsonEncode({'data': record.json, 'updated_at': record.updatedAt}),
      );
    } catch (_) {
      /* Live data remains usable when local storage is unavailable. */
    }
  }

  @override
  Future<void> clear() async {
    final keys = await preferences.getKeys();
    final owned = keys
        .where((key) => key.startsWith('shgad.v1.$namespace.'))
        .toSet();
    if (owned.isNotEmpty) await preferences.clear(allowList: owned);
  }
}
