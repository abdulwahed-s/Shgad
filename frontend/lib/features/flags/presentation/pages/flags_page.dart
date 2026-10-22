import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../core/widgets/review_flag_view.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/flags.dart';
import '../bloc/flags_bloc.dart';

class FlagsPage extends StatelessWidget {
  const FlagsPage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<FlagsBloc>()..add(const RefreshReport()),
    child: const _FlagsView(),
  );
}

class _FlagsView extends StatelessWidget {
  const _FlagsView();
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return MerchantPage(
      title: l.flagsTitle,
      actions: [
        TextButton(
          onPressed: () => context.read<FlagsBloc>().add(const RefreshReport()),
          child: Text(l.refresh),
        ),
      ],
      children: [
        ReportView<Flags, FlagsBloc>(
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              InfoStrip(text: data.items.isEmpty ? l.noRecords : l.flagsIntro),
              for (final flag in data.items) ReviewFlagView(flag: flag),
            ],
          ),
        ),
      ],
    );
  }
}
