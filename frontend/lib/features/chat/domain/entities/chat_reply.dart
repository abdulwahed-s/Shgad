import '../../../../core/domain/amount.dart';

class SourcedMetric {
  const SourcedMetric(
    this.value,
    this.unit,
    this.kind,
    this.label,
    this.sources,
    this.formula,
  );
  final int? value;
  final String unit, kind, label, formula;
  final List<String> sources;
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
  });
  final String status, text;
  final List<Amount> figures;
  final List<SourcedMetric> metrics;
  final List<ChatContext> contexts;
  final List<ChatOption> options;
  final ChatContext? resolved;
  final bool template;
}

class ChatTurn {
  const ChatTurn(this.question, this.reply);
  final String question;
  final ChatReply reply;
}
