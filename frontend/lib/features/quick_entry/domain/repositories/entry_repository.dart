import '../../../../core/utils/result.dart';
import '../entities/entry.dart';

abstract interface class EntryRepository {
  Future<Result<EntrySetup>> setup();
  Future<Result<SavedEntry>> save(EntryDraft draft);
  Future<Result<VoidedEntry>> undo(
    String sourceId,
    String clientId,
    String reason,
  );
}
