class EntryDraft {
  const EntryDraft(this.clientId, this.fields);
  final String clientId;
  final Map<String, String> fields;
  String get type => fields['type'] ?? 'CASH_SALE';
  String get date => fields['business_date'] ?? '';
  String get amountText => fields['amount_iqd'] ?? '';
}

class SavedEntry {
  const SavedEntry(this.sourceId, this.transactionId, this.duplicate);
  final String sourceId, transactionId;
  final bool duplicate;
}

class EntrySetup {
  const EntrySetup(this.date, this.parties);
  final String date;
  final Map<String, String> parties;
}

class VoidedEntry {
  const VoidedEntry(this.sourceId, this.voidId, this.reason);
  final String sourceId, voidId, reason;
}
