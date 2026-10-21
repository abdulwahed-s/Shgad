enum FailureKind {
  offline,
  validation,
  missing,
  notFound,
  unavailable,
  internal,
}

class AppFailure {
  const AppFailure(this.kind, {this.code = '', this.messageKey = ''});
  final FailureKind kind;
  final String code;
  final String messageKey;
}
