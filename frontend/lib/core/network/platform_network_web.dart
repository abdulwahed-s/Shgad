import 'dart:js_interop';

@JS('navigator.onLine')
external bool get _online;
@JS('window.addEventListener')
external void _listen(String type, JSFunction callback);
bool platformOnline() => _online;
void watchPlatformNetwork(void Function(bool) onChange) {
  _listen(
    'online',
    (() {
      onChange(true);
    }).toJS,
  );
  _listen(
    'offline',
    (() {
      onChange(false);
    }).toJS,
  );
}
