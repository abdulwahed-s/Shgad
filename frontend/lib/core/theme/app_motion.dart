import 'package:flutter/material.dart';
import '../constants/app_dimens.dart';

abstract final class AppMotion {
  static ChipAnimationStyle chip(BuildContext context) {
    final style = AnimationStyle(
      duration: state(context),
      reverseDuration: state(context),
    );
    return ChipAnimationStyle(
      enableAnimation: style,
      selectAnimation: style,
      avatarDrawerAnimation: style,
      deleteDrawerAnimation: style,
    );
  }

  static Duration route(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context)
      ? Duration.zero
      : const Duration(milliseconds: 150);
  static Duration sheet(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context)
      ? Duration.zero
      : const Duration(milliseconds: 180);
  static Duration state(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context)
      ? Duration.zero
      : const Duration(milliseconds: 120);
}

class SoftEntrance extends StatefulWidget {
  const SoftEntrance({required this.child, super.key});
  final Widget child;
  @override
  State<SoftEntrance> createState() => _SoftEntranceState();
}

class _SoftEntranceState extends State<SoftEntrance>
    with SingleTickerProviderStateMixin {
  late final AnimationController controller = AnimationController(vsync: this);
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    controller.duration = AppMotion.sheet(context);
    controller.forward();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    child: widget.child,
    builder: (context, child) {
      final value = Curves.easeOutCubic.transform(controller.value);
      return Opacity(
        opacity: value,
        child: Transform.translate(
          offset: Offset(0, AppDimens.sm * (1 - value)),
          child: child,
        ),
      );
    },
  );
}
