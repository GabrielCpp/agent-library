# Android host

## Files

```text
androidApp/
  build.gradle.kts                 com.android.application, depends on projects.shared
  src/main/AndroidManifest.xml     application name, launcher activity, permissions
  src/main/kotlin/.../NotesApplication.kt
  src/main/kotlin/.../MainActivity.kt
```

## Rules

- `compileSdk` follows what Compose Multiplatform requires. `targetSdk` follows the Play Store deadline. `minSdk` is 26 unless the product says otherwise.
- `MainActivity` extends `ComponentActivity`, calls `enableEdgeToEdge()` before `setContent`, and declares `android:configChanges` for nothing. The view model survives rotation.
- Pass the application `Context` into `androidPlatformModule`. Never store an `Activity` in a singleton.
- Build the Room builder with `Room.databaseBuilder<AppDatabase>(context, context.getDatabasePath("app.db").absolutePath)`.
- Declare each permission in the manifest and request a runtime permission at the moment the feature needs it, behind a port.
- Release builds turn on `isMinifyEnabled` and `isShrinkResources`. Keep rules come from the libraries. Add a rule only for a class that fails at runtime in a release build, and run the release build on a device before shipping.
- Signing values come from environment variables or a file outside git.

## Commands

```bash
./gradlew :androidApp:assembleDebug
adb -s <device id> install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
```

Always pass `-s <device id>`. A plain `adb install` fails when two devices are attached.
