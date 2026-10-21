import 'dart:convert';
import 'dart:typed_data';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/picked_file.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/csv_import/data/datasources/csv_picker.dart';
import 'package:shgad/features/csv_import/data/datasources/csv_remote.dart';
import 'package:shgad/features/csv_import/data/models/csv_model.dart';
import 'package:shgad/features/csv_import/data/repositories/csv_repository_impl.dart';
import 'package:shgad/features/csv_import/domain/entities/csv_import.dart';
import 'package:shgad/features/csv_import/domain/repositories/csv_repository.dart';
import 'package:shgad/features/csv_import/domain/usecases/csv_usecases.dart';
import 'package:shgad/features/csv_import/presentation/bloc/csv_bloc.dart';
import 'entry_test.dart' show FakeConnection;
import 'support/fixtures.dart';

class MockCsvPicker extends Mock implements CsvPicker {}

class MockCsvRemote extends Mock implements CsvRemote {}

class MockCsvRepository extends Mock implements CsvRepository {}

void main() {
  final file = PickedFile(
    'fictional.csv',
    Uint8List.fromList(
      utf8.encode(
        'Ref,At,Kind,IQD\nCSV-1,2026-09-28T10:00:00+03:00,CASH_SALE,12000\n',
      ),
    ),
  );
  final selection = CsvSelection(file, ['Ref', 'At', 'Kind', 'IQD']);
  setUpAll(() {
    registerFallbackValue(file);
    registerFallbackValue(selection);
  });
  test(
    'CSV header parser handles BOM, quoted comma, UTF8, and rejects duplicate/invalid headers',
    () {
      expect(
        CsvModel.headers(
          Uint8List.fromList(
            utf8.encode('\uFEFF"مرجع,المحل",At,Kind,IQD\r\nX,Y,Z,1\r\n'),
          ),
        ),
        ['مرجع,المحل', 'At', 'Kind', 'IQD'],
      );
      expect(
        () => CsvModel.headers(Uint8List.fromList(utf8.encode('Ref,Ref\nA,B'))),
        throwsFormatException,
      );
      expect(
        () => CsvModel.headers(Uint8List.fromList([255, 254])),
        throwsFormatException,
      );
    },
  );
  test(
    'CSV repository preserves file and manual mappings, returns parsed preview and receipt',
    () async {
      final picker = MockCsvPicker();
      final remote = MockCsvRemote();
      final repo = CsvRepositoryImpl(remote, picker);
      when(picker.pick).thenAnswer((_) async => file);
      expect(
        (await repo.pick() as Success<CsvSelection?>).value!.headers,
        selection.headers,
      );
      when(
        () => remote.preview(any(), any()),
      ).thenAnswer((_) async => csvPreviewJson());
      final preview =
          (await repo.preview(selection, [const CsvColumn('IQD', 'amount_iqd')])
                  as Success<CsvPreview>)
              .value;
      expect(preview.rows.single.amount!.value, 12000);
      final mapping =
          verify(() => remote.preview(any(), captureAny())).captured.single
              as List;
      expect(mapping.single, {
        'source_header': 'IQD',
        'target_field': 'amount_iqd',
      });
      when(
        () => remote.confirm('map-test'),
      ).thenAnswer((_) async => csvReceiptJson());
      expect(
        (await repo.confirm('map-test') as Success<CsvReceipt>).value.accepted,
        1,
      );
      when(
        () => remote.confirm(any()),
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      expect(await repo.confirm('map-test'), isA<Failed>());
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    late FakeConnection connection;
    blocTest<CsvBloc, CsvState>(
      'CSV picking loading to $mode',
      build: () {
        final repo = MockCsvRepository();
        connection = FakeConnection();
        when(repo.pick).thenAnswer(
          (_) async => mode == 'loaded'
              ? Success(selection)
              : Failed(
                  AppFailure(
                    mode == 'offline'
                        ? FailureKind.offline
                        : FailureKind.validation,
                  ),
                ),
        );
        return CsvBloc(
          PickCsv(repo),
          PreviewCsv(repo),
          ConfirmCsv(repo),
          WatchConnectivity(connection),
          CheckConnectivity(connection),
        );
      },
      act: (b) => b.add(const ChooseCsv()),
      expect: () => [
        isA<CsvLoading>(),
        switch (mode) {
          'loaded' => isA<CsvLoaded>(),
          'offline' => isA<CsvOffline>(),
          _ => isA<CsvFailure>(),
        },
      ],
      tearDown: () => connection.controller.close(),
    );
  }
  test(
    'Mapping edits disable confirmation until repreview; offline retains file and mapping with no queue',
    () async {
      final repo = MockCsvRepository();
      final connection = FakeConnection();
      when(repo.pick).thenAnswer((_) async => Success(selection));
      when(
        () => repo.preview(any(), any()),
      ).thenAnswer((_) async => Success(CsvModel.preview(csvPreviewJson())));
      when(
        () => repo.confirm(any()),
      ).thenAnswer((_) async => Success(CsvModel.receipt(csvReceiptJson())));
      final bloc = CsvBloc(
        PickCsv(repo),
        PreviewCsv(repo),
        ConfirmCsv(repo),
        WatchConnectivity(connection),
        CheckConnectivity(connection),
      );
      bloc.add(const ChooseCsv());
      await bloc.stream.firstWhere((s) => s is CsvLoaded);
      bloc.add(const AcknowledgeSynthetic(true));
      await Future<void>.delayed(Duration.zero);
      bloc.add(const PreviewCsvFile());
      await bloc.stream.firstWhere((s) => s.view.canConfirm);
      bloc.add(const ChangeCsvColumn('IQD', null));
      await bloc.stream.firstWhere((s) => s.view.dirty);
      expect(bloc.state.view.canConfirm, isFalse);
      bloc.add(const ConfirmCsvImport());
      await Future<void>.delayed(Duration.zero);
      verifyNever(() => repo.confirm(any()));
      connection.set(false);
      await bloc.stream.firstWhere((s) => s is CsvOffline);
      expect(bloc.state.view.selection!.file.bytes, file.bytes);
      expect(bloc.state.view.columns.last.target, isNull);
      bloc.add(const ConfirmCsvImport());
      await Future<void>.delayed(Duration.zero);
      connection.set(true);
      await bloc.stream.firstWhere((s) => s is CsvLoaded);
      verifyNever(() => repo.confirm(any()));
      bloc.add(const PreviewCsvFile());
      await bloc.stream.firstWhere((s) => s.view.canConfirm);
      bloc.add(const PrepareCsvImport());
      await bloc.stream.firstWhere((s) => s.view.confirming);
      bloc.add(const ConfirmCsvImport());
      await bloc.stream.firstWhere((s) => s.view.receipt != null);
      expect(bloc.state.view.receipt!.id, 'BATCH-IMPORT');
      await bloc.close();
      await connection.controller.close();
    },
  );
}
