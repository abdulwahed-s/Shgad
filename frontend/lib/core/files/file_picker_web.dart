import 'dart:async';
import 'dart:js_interop';
import '../domain/picked_file.dart';

@JS('document.createElement')
external JSObject _create(String name);
@JS('document.body.appendChild')
external JSObject _append(JSObject node);
extension type _Input(JSObject _) implements JSObject {
  external set type(String value);
  external set accept(String value);
  external void setAttribute(String name, String value);
  external void addEventListener(String name, JSFunction callback);
  external void click();
  external void remove();
  external _Files? get files;
}
extension type _Files(JSObject _) implements JSObject {
  external _File? item(int index);
}
extension type _File(JSObject _) implements JSObject {
  external String get name;
  external int get size;
  external JSPromise<JSArrayBuffer> arrayBuffer();
}
Future<PickedFile?> pickCsvFile() {
  final input = _Input(_create('input'))
    ..type = 'file'
    ..accept = '.csv,text/csv'
    ..setAttribute('style', 'position:fixed;left:-9999px');
  final result = Completer<PickedFile?>();
  Future<void> selected() async {
    try {
      final file = input.files?.item(0);
      if (file == null) {
        result.complete(null);
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        throw const FormatException('CSV size limit');
      }
      final buffer = await file.arrayBuffer().toDart;
      result.complete(PickedFile(file.name, buffer.toDart.asUint8List()));
    } catch (error, stack) {
      result.completeError(error, stack);
    } finally {
      input.remove();
    }
  }

  input.addEventListener(
    'change',
    (() {
      unawaited(selected());
    }).toJS,
  );
  input.addEventListener(
    'cancel',
    (() {
      if (!result.isCompleted) result.complete(null);
      input.remove();
    }).toJS,
  );
  _append(input);
  input.click();
  return result.future;
}
