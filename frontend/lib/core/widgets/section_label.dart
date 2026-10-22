import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../constants/app_dimens.dart';
import 'balanced_text.dart';

class SectionLabel extends StatelessWidget {
  const SectionLabel({required this.text, super.key});

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppDimens.sm),
    child: Semantics(
      header: true,
      child: BalancedText(
        text,
        style: Theme.of(context).extension<LedgerStyles>()!.section,
      ),
    ),
  );
}
