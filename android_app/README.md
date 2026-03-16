Flutter Android App (android_app)

This folder contains a lightweight Flutter skeleton preconfigured to connect to your Firebase Realtime Database.

Quick start

1. Install Flutter and Android toolchain: https://flutter.dev/docs/get-started/install
2. From this folder run:

```bash
# create native android/ios folders and pubspec scaffolding
flutter create .

# get packages
flutter pub get

# run on a connected device or emulator
flutter run -d emulator-5554
```

Firebase setup

1. Add an Android app in your Firebase console and download `google-services.json` into `android/app/`.
2. Fill the Firebase options in `lib/firebase_config.dart` with your project's values (apiKey, appId, projectId, messagingSenderId, databaseURL).
   - Alternatively use `flutterfire configure` to generate `lib/firebase_options.dart` and update `lib/main.dart` initialization.

Files provided

- `lib/main.dart` — example app that connects to Realtime Database and shows `attendance_logs` entries.
- `lib/firebase_config.dart` — placeholder `FirebaseOptions` to fill with your project values.
- `pubspec.yaml` — includes `firebase_core` and `firebase_database` dependencies.

Notes

- This skeleton assumes you'll run `flutter create .` to populate platform directories. The provided `lib/` and `pubspec.yaml` are ready to use afterwards.
- After adding `google-services.json`, ensure Gradle is configured per Firebase Android docs, then run the app.
