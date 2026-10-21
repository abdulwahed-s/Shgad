import '../../../../core/utils/result.dart';
import '../entities/entry.dart';
import '../repositories/entry_repository.dart';

class LoadEntrySetup {
  LoadEntrySetup(this.repository);
  final EntryRepository repository;
  Future<Result<EntrySetup>> call() => repository.setup();
}

class SaveEntry {
  SaveEntry(this.repository);
  final EntryRepository repository;
  Future<Result<SavedEntry>> call(EntryDraft draft) => repository.save(draft);
}

class UndoEntry {
  UndoEntry(this.repository);
  final EntryRepository repository;
  Future<Result<VoidedEntry>> call(
    String sourceId,
    String clientId,
    String reason,
  ) => repository.undo(sourceId, clientId, reason);
}
