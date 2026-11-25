# Desktop host

## Files

```text
desktopApp/
  build.gradle.kts                 kotlin jvm, Compose plugins, hot reload, depends on projects.shared
  src/main/kotlin/.../Main.kt
```

## Entry

```kotlin
fun main() {
    startApp(AppConfig(apiBaseUrl = "https://api.example.com"), desktopPlatformModule(dataDir()))
    application {
        Window(onCloseRequest = ::exitApplication, title = "Notes") { App() }
    }
}
```

## Rules

- Name the entry file `Main.kt`. ktlint rejects a lowercase file name.
- Add `kotlinx-coroutines-swing` to `desktopApp`. `Dispatchers.Main` has no implementation on the JVM without it, and the first view model crashes.
- Add `compose.desktop.currentOs` to `desktopApp` and to `jvmTest` in `shared`.
- Resolve the data directory per operating system: `%APPDATA%` on Windows, `~/Library/Application Support` on macOS, `$XDG_DATA_HOME` or `~/.local/share` on Linux. Accept a system property override so a QA run starts from an empty directory.
- Set a minimum window size, and let the layout adapt as in the `kmp-compose` skill.
- Package with `compose.desktop { application { mainClass = "...MainKt"; nativeDistributions { targetFormats(Dmg, Msi, Deb) } } }`. Each format builds only on its own operating system.

## Commands

```bash
./gradlew :desktopApp:run
./gradlew :desktopApp:hotRun
./gradlew :desktopApp:packageDistributionForCurrentOS
```

`hotRun` comes from the `org.jetbrains.compose.hot-reload` plugin and reloads changed composables into the running window.
