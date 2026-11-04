import '../../../../core/domain/amount.dart';
import '../../../../core/domain/known_zero_query.dart';

class ChatCollectionAction {
  const ChatCollectionAction(this.kind, this.customerId, this.tone);
  final String kind, tone;
  final String? customerId;
  String get location => Uri(
    path: '/collections',
    queryParameters: kind == 'draft' && customerId != null
        ? {'customer': customerId!, 'tone': tone}
        : null,
  ).toString();
}

class SourcedMetric {
  const SourcedMetric(
    this.value,
    this.unit,
    this.kind,
    this.label,
    this.sources,
    this.formula, {
    this.queryEvidence,
  });
  final int? value;
  final String unit, kind, label, formula;
  final List<String> sources;
  final KnownZeroQuery? queryEvidence;
}

class ChatContext {
  const ChatContext(this.start, this.end, this.partyId, this.partyName);
  final String start, end;
  final String? partyId, partyName;
}

class ChatOption {
  const ChatOption(this.label, this.value);
  final String label, value;
}

class ChatReply {
  const ChatReply({
    required this.status,
    required this.text,
    required this.figures,
    required this.metrics,
    required this.contexts,
    required this.options,
    required this.resolved,
    required this.template,
    this.collectionAction,
  });
  final String status, text;
  final List<Amount> figures;
  final List<SourcedMetric> metrics;
  final List<ChatContext> contexts;
  final List<ChatOption> options;
  final ChatContext? resolved;
  final bool template;
  final ChatCollectionAction? collectionAction;
}

class ChatTurn {
  const ChatTurn(this.question, this.reply);
  final String question;
  final ChatReply reply;
}
