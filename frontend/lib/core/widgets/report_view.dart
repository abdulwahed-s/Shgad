import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../l10n/generated/app_localizations.dart';
import '../domain/snapshot.dart';
import '../constants/app_dimens.dart';
import '../presentation/report_bloc.dart';
import '../utils/date_formatter.dart';
import 'failure_view.dart';
import 'ledger_widgets.dart';
import 'page_header.dart';

class ReportView<T, B extends ReportBloc<T>> extends StatelessWidget {
  const ReportView({required this.builder, this.dateLabel, super.key});
  final Widget Function(BuildContext, T) builder;
  final String Function(T)? dateLabel;
  @override
  Widget build(BuildContext context) => BlocBuilder<B, ReportState<T>>(
    builder: (context, state) {
      final Snapshot<T>? snapshot = switch (state) {
        ReportLoaded<T>(:final snapshot) ||
        ReportOffline<T>(:final snapshot) => snapshot,
        ReportLoading<T>(:final previous) => previous,
        _ => null,
      };
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (state is ReportFailure<T>)
            FailureView(
              failure: state.failure,
              onRetry: () => context.read<B>().add(const RefreshReport()),
            ),
          if (snapshot != null) ...[
            if (snapshot.offline) OfflineBanner(updatedAt: snapshot.updatedAt),
            PageMeta(
              updated: snapshot.offline
                  ? null
                  : AppLocalizations.of(context).updatedAt(
                      AppLocalizations.of(context).timeInBaghdad(
                        formatDate(
                          snapshot.updatedAt,
                          AppLocalizations.of(context).localeName,
                          timestamp: true,
                        ),
                      ),
                    ),
              date: dateLabel?.call(snapshot.data),
              onRefresh: () => context.read<B>().add(const RefreshReport()),
            ),
            if (state is ReportLoading<T>) const InlineProgress(),
            builder(context, snapshot.data),
          ] else if (state is ReportInitial<T> ||
              state is ReportLoading<T>) ...[
            const InlineProgress(),
            const SizedBox(height: AppDimens.chartHeight),
          ],
        ],
      );
    },
  );
}

Future<void> refreshReport<T>(ReportBloc<T> bloc) async {
  final completed = bloc.stream.firstWhere(
    (state) => state is! ReportLoading<T> && state is! ReportInitial<T>,
  );
  bloc.add(const RefreshReport());
  await completed;
}
