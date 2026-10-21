import '../../../../core/data/amount_model.dart';
import '../../domain/entities/chat_reply.dart';

class ChatModel {
  static ChatContext context(dynamic range, dynamic party) => ChatContext(
    range['start'] as String,
    range['end'] as String,
    party?['id'] as String?,
    party?['display_name'] as String?,
  );
  static ChatReply parse(Map<String, dynamic> j) => ChatReply(
    status: j['status'] as String,
    text: j['reply_ar'] as String,
    figures: (j['figures'] as List).map(parseAmount).toList(),
    metrics: (j['metrics'] as List? ?? [])
        .map(
          (m) => SourcedMetric(
            m['value'] as int?,
            m['unit'] as String,
            m['kind'] as String,
            m['label_key'] as String,
            List<String>.from(m['source_ids'] as List),
            m['formula'] as String,
          ),
        )
        .toList(),
    contexts: (j['contexts'] as List? ?? [])
        .map((c) => context(c['range'], c['counterparty']))
        .toList(),
    options: (j['clarification']?['options'] as List? ?? [])
        .map((o) => ChatOption(o['label_ar'] as String, o['value'] as String))
        .toList(),
    resolved: j['resolved_range'] == null
        ? null
        : context(j['resolved_range'], j['resolved_counterparty']),
    template: j['renderer']?['fell_back_to_template'] == true,
  );
}
