import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../utils/iqd_formatter.dart';
import 'balanced_text.dart';
import 'ledger_widgets.dart';

class StepIndicator extends StatelessWidget {
  const StepIndicator({required this.labels, required this.current, super.key});
  final List<String> labels;
  final int current;
  @override
  Widget build(BuildContext context) {
    Widget step(int i) => Semantics(
      selected: i == current,
      label: labels[i],
      value: IqdFormatter.digits(
        (i + 1).toString(),
        AppLocalizations.of(context).localeName,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppDimens.sm),
        child: Row(
          children: [
            NumberBadge(number: i + 1),
            const SizedBox(width: AppDimens.sm),
            Expanded(
              child: BalancedText(
                labels[i],
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: i == current
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
    return MediaQuery.sizeOf(context).width < AppDimens.compactBreakpoint
        ? Column(children: [for (var i = 0; i < labels.length; i++) step(i)])
        : Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < labels.length; i++) Expanded(child: step(i)),
            ],
          );
  }
}
