import 'dart:convert';
import 'package:dio/dio.dart';
import '../../../../core/domain/picked_file.dart';
import '../../../../core/network/api_client.dart';

class CsvRemote {
  CsvRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> preview(
    PickedFile file,
    List<Map<String, String?>>? columns,
  ) => api.post(
    '/api/imports/csv/mapping',
    FormData.fromMap({
      'file': MultipartFile.fromBytes(file.bytes, filename: file.name),
      if (columns != null) 'columns_json': jsonEncode({'columns': columns}),
    }),
  );
  Future<Map<String, dynamic>> confirm(String id) =>
      api.post('/api/imports/csv/mapping/${Uri.encodeComponent(id)}/confirm');
}
