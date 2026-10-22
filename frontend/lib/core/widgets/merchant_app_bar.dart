import 'package:flutter/material.dart';
import '../constants/app_dimens.dart';
import 'merchant_menu.dart';

PreferredSizeWidget merchantAppBar(
  BuildContext context,
  String title, {
  bool menu = true,
}) => AppBar(
  toolbarHeight: MediaQuery.textScalerOf(
    context,
  ).scale(AppDimens.toolbarHeight),
  title: Text(title, maxLines: 2),
  actions: menu ? const [MerchantMenu()] : null,
);
