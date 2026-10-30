import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';

class ShgadBrand extends StatelessWidget {
  const ShgadBrand({this.wordmark = false, this.height, super.key});

  final bool wordmark;
  final double? height;

  @override
  Widget build(BuildContext context) => Image.asset(
    wordmark
        ? 'assets/branding/shgad_wordmark.png'
        : 'assets/branding/shgad_symbol.png',
    height:
        height ??
        (wordmark ? AppDimens.brandWordmarkHeight : AppDimens.brandSymbolSize),
    fit: BoxFit.contain,
    semanticLabel: AppLocalizations.of(context).appTitle,
  );
}
