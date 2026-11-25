---
name: kmp-platform
description: "Kotlin Multiplatform platform boundary: port interfaces, expect and actual, Koin platform modules, Android, iOS and desktop hosts, Xcode. Load when code needs a platform API, when touching a host app or Xcode project, or a target fails."
applyTo: '**/androidMain/**,**/iosMain/**,**/jvmMain/**,androidApp/**,desktopApp/**,iosApp/**'
tags: [kmp, mobile, standards]
---

# Platform Boundary

Common code holds the app. Platform code holds only what a platform API forces there. Per-target detail is in [references/android.md](references/android.md), [references/ios.md](references/ios.md) and [references/desktop.md](references/desktop.md).

## Port first

Reach a platform API through an interface declared in common code.

```kotlin
fun interface LinkOpener {
    fun open(url: String)
}
```

- Each target implements the port in its own source set: `AndroidLinkOpener(context)`, `IosLinkOpener()`, `DesktopLinkOpener()`.
- Each target has one Koin module that binds its implementations: `androidPlatformModule(context)`, `iosPlatformModule()`, `desktopPlatformModule(dataDir)`. The host app passes it to `startApp`.
- A test binds a fake of the same interface. Nothing else changes.

## When `expect` and `actual` fit

| Need | Use |
|---|---|
| A service with behavior, state or a constructor argument such as a `Context` | interface port and Koin binding |
| A constant or a pure function with no dependency | `expect fun` or `expect val` |
| A type that a library generates | `expect object` as the library documents, such as the Room constructor |

- Never write `expect class` for a service. Its constructor differs per platform, so common code cannot create it, and a test cannot replace it.
- Every `expect` has an `actual` in `androidMain`, `iosMain` and `jvmMain` in the same change. `./gradlew :shared:compileKotlinIosSimulatorArm64` catches a missing iOS one on any host.
- Keep platform files small. Logic that could run in common code moves to common code, and the platform file keeps the API call.

## Host apps

Each host does three things: build the config, call `startApp` once, show `App()`.

- Android: `Application.onCreate` calls `startApp(AppConfig(...), androidPlatformModule(this))`. `MainActivity` calls `enableEdgeToEdge()` and then `setContent { App() }`.
- Desktop: `main()` calls `startApp` and then `application { Window(onCloseRequest = ::exitApplication, title = ...) { App() } }`.
- iOS: Swift calls `IosEntryKt.startIosApp(apiBaseUrl:)` once in the `App` initializer and wraps `IosEntryKt.MainViewController()` in a `UIViewControllerRepresentable`.

A host app holds no screen, no view model and no business rule.

## Common code stays common

- `commonMain` imports nothing from `java.*`, `android.*` or `platform.*`. Use `kotlinx-datetime`, `kotlinx-io` or `okio`, `kotlin.uuid.Uuid` and `kotlinx.coroutines` in their place.
- Never branch on a platform name in common code. A difference in behavior is a different implementation of a port.
- An architecture test enforces the import rule, as in {{ skill_link("kmp-testing") }}.

## What each host can build

| Host | Android | Desktop | iOS |
|---|---|---|---|
| Linux, Windows | build, test, run | build, test, run | compile Kotlin to klib only |
| macOS on Apple silicon | build, test, run | build, test, run | link the framework, run the simulator, run `iosSimulatorArm64Test`, archive |
| macOS on Intel | build, test, run | build, test, run | link `iosArm64` and build for a device only. No simulator run |

Check a Mac with `uname -m` before planning an iOS run. `x86_64` means the simulator is out, because the libraries ship no `iosX64` variant.

A change made on Linux closes its iOS line with the compile task and reports the simulator run as open for a Mac. It never reports iOS as verified.

## Closing check

```bash
./gradlew :shared:compileKotlinIosSimulatorArm64 :androidApp:assembleDebug :desktopApp:compileKotlin :shared:jvmTest
```

Exit 0 closes a platform change on any host. On a Mac, also build the `iosApp` scheme for a simulator, following [references/ios.md](references/ios.md).
