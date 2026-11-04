import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/repositories/collections_repository.dart';

class ReminderSharingImpl implements ReminderSharingRepository {
  static Uri whatsappUri(String text) =>
      Uri.https('wa.me', '/', {'text': text});
  @override
  Future<Result<bool>> share(String text, String channel) async {
    try {
      if (channel == 'copy') {
        await Clipboard.setData(ClipboardData(text: text));
        return const Success(true);
      }
      if (channel == 'whatsapp') {
        return Success(
          await launchUrl(
            whatsappUri(text),
            mode: LaunchMode.externalApplication,
            webOnlyWindowName: '_blank',
          ),
        );
      }
      return const Failed(AppFailure(FailureKind.validation));
    } catch (_) {
      return const Failed(AppFailure(FailureKind.unavailable));
    }
  }
}
