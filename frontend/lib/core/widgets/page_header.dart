import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import 'balanced_text.dart';
import 'ledger_widgets.dart';
import 'shgad_brand.dart';

class PageHeader extends StatelessWidget implements PreferredSizeWidget {
  const PageHeader({
    required this.title,
    this.onBack,
    this.action,
    this.height = AppDimens.toolbarHeight,
    super.key,
  });
  final String title;
  final VoidCallback? onBack;
  final Widget? action;
  final double height;
  @override
  Size get preferredSize => Size.fromHeight(height);
  @override
  Widget build(BuildContext context) => AppBar(
    title: DefaultTextStyle.merge(
      maxLines: 3,
      softWrap: true,
      overflow: TextOverflow.visible,
      child: BalancedText(
        title,
        style: Theme.of(context).appBarTheme.titleTextStyle,
      ),
    ),
    toolbarHeight: height,
    automaticallyImplyLeading: false,
    leading: onBack != null
        ? BackButton(onPressed: onBack)
        : MediaQuery.sizeOf(context).width < AppDimens.compactBreakpoint
        ? const Padding(
            padding: EdgeInsets.all(AppDimens.md),
            child: ShgadBrand(),
          )
        : null,
    actions: [?action],
  );
}

class PageMeta extends StatelessWidget {
  const PageMeta({
    this.updated,
    this.date,
    this.onRefresh,
    this.showRefresh = false,
    super.key,
  });
  final String? updated, date;
  final VoidCallback? onRefresh;
  final bool showRefresh;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppDimens.lg),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (context, bounds) {
              final style = Theme.of(context).textTheme.bodySmall;
              final captions = [?updated, ?date];
              double needed = AppDimens.sm * 2 + AppDimens.xs;
              for (final caption in captions) {
                final painter = TextPainter(
                  text: TextSpan(text: caption, style: style),
                  textDirection: Directionality.of(context),
                  textScaler: MediaQuery.textScalerOf(context),
                )..layout();
                needed += painter.width;
                painter.dispose();
              }
              if (captions.length == 2 && needed <= bounds.maxWidth) {
                return Row(
                  children: [
                    Text(captions.first, style: style),
                    const SizedBox(width: AppDimens.sm),
                    Container(
                      width: AppDimens.xs,
                      height: AppDimens.xs,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: style?.color,
                      ),
                    ),
                    const SizedBox(width: AppDimens.sm),
                    Text(captions.last, style: style),
                  ],
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (var i = 0; i < captions.length; i++) ...[
                    if (i > 0) const SizedBox(height: AppDimens.xs),
                    Text(captions[i], style: style),
                  ],
                ],
              );
            },
          ),
        ),
        if (onRefresh != null || showRefresh)
          TextAction(
            text: AppLocalizations.of(context).refresh,
            onPressed: onRefresh,
          ),
      ],
    ),
  );
}
