import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/daily_close/domain/entities/daily_close.dart';
import 'package:shgad/features/daily_close/domain/repositories/close_repository.dart';
import 'package:shgad/features/quick_entry/domain/entities/entry.dart';
import 'package:shgad/features/quick_entry/domain/repositories/entry_repository.dart';
import 'package:shgad/features/today/domain/entities/today.dart';
import 'package:shgad/features/today/presentation/bloc/today_bloc.dart';
import 'support/test_app.dart';

void main() {
  test(
    'Successful save, void and difference review refresh an active Today; failed writes do not',
    () async {
      final api = installRecordedApp();
      final bloc = getIt<TodayBloc>();
      Future<void> refreshAfter(Future<Object> Function() write) async {
        final refreshed = bloc.stream.firstWhere(
          (s) => s is ReportLoaded<Today>,
        );
        expect(await write(), isA<Success>());
        await refreshed;
      }

      bloc.add(const RefreshReport());
      await bloc.stream.firstWhere((s) => s is ReportLoaded<Today>);
      int reads() => api.requests
          .where((r) => r.path == '/api/obligations/upcoming')
          .length;
      expect(reads(), 1);
      final entries = getIt<EntryRepository>();
      await refreshAfter(
        () => entries.save(
          const EntryDraft('save', {
            'type': 'CASH_SALE',
            'business_date': '2026-09-28',
            'amount_iqd': '١٢٠٠٠',
          }),
        ),
      );
      expect(reads(), 2);
      await refreshAfter(() => entries.undo('ENT-TEST', 'void', 'mistyped'));
      expect(reads(), 3);
      await refreshAfter(
        () => getIt<CloseRepository>().resolve(
          const ResolutionDraft(
            'review',
            '2026-09-28',
            'leave_unexplained',
            null,
            null,
          ),
        ),
      );
      expect(reads(), 4);
      api.offline = true;
      expect(
        await entries.save(
          const EntryDraft('offline', {
            'type': 'CASH_SALE',
            'business_date': '2026-09-28',
            'amount_iqd': '12000',
          }),
        ),
        isA<Failed>(),
      );
      await Future<void>.delayed(Duration.zero);
      expect(reads(), 4);
      await bloc.close();
      await getIt.reset();
    },
  );
}
