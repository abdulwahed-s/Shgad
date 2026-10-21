import '../../../../core/domain/picked_file.dart';
import '../../../../core/files/file_picker.dart';

class CsvPicker {
  Future<PickedFile?> pick() => pickCsvFile();
}
