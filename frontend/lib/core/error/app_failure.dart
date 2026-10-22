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

class IqdFormatException extends FormatException {
  const IqdFormatException() : super('IQD exceeds exact web integer range');
}

AppFailure dataFailure(Object error) => error is IqdFormatException
    ? const AppFailure(
        FailureKind.validation,
        code: 'UNSAFE_WEB_IQD',
        messageKey: 'error_web_iqd_range',
      )
    : const AppFailure(FailureKind.internal);
