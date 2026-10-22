import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../error/app_failure.dart';
import 'ledger_widgets.dart';

String failureText(AppLocalizations l, AppFailure failure) =>
    switch (failure.messageKey) {
      'error_web_iqd_range' => l.errorWebIqd,
      'error_difference_sign_mismatch' => l.errorSign,
      'error_difference_exceeded' => l.errorExceeded,
      'error_missing_count' => l.errorCount,
      'error_missing_opening_balance' => l.errorBalance,
      'error_missing_costs' => l.errorCosts,
      'error_missing_forecast_history' => l.errorHistory,
      'error_missing_due_date' => l.errorDueDate,
      'error_ambiguous_counterparty' => l.errorParty,
      'error_ambiguous_date' => l.errorDate,
      'error_mapping_unresolved' => l.errorMapping,
      'error_import_rejected' => l.errorImport,
      _ => switch (failure.kind) {
        FailureKind.offline => l.needsConnection,
        FailureKind.validation => l.errorValidation,
        FailureKind.missing => l.errorMissing,
        FailureKind.notFound => l.errorNotFound,
        FailureKind.unavailable => l.errorUnavailable,
        FailureKind.internal => l.errorInternal,
      },
    };

class FailureView extends StatelessWidget {
  const FailureView({required this.failure, required this.onRetry, super.key});
  final AppFailure failure;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => EmptyState(
    text: failureText(AppLocalizations.of(context), failure),
    action: AppLocalizations.of(context).retry,
    onPressed: onRetry,
  );
}
