---
name: kmp
description: "Entry point for Kotlin Multiplatform work: Compose Multiplatform app on Android, iOS and desktop, module map, sibling skills, Gradle closing commands. Load when starting any Kotlin Multiplatform task, before the matching sibling skill."
applyTo: '**/*.kt,**/*.kts,gradle/libs.versions.toml'
tags: [kmp, mobile, standards, entrypoint]
---

# Kotlin Multiplatform App

This is the root skill for a Kotlin Multiplatform app. Load it first, then load the sibling that matches the files you will touch.

## Module map

| Module | Holds | Size |
|---|---|---|
| `shared` | Every screen, view model, repository, database and design token | All product code |
| `androidApp` | `Application`, one `Activity`, the manifest | Under 100 lines of Kotlin |
| `desktopApp` | `main()` with one `Window` | Under 100 lines of Kotlin |
| `iosApp` | The Xcode project, `iOSApp.swift`, `ContentView.swift` | Under 100 lines of Swift |

A feature lands in `shared/src/commonMain`. A host module changes only when the platform entry point itself changes.

## Sibling skills

- Kotlin language rules: {{ skill_link("kmp-kotlin") }}
- Gradle, version catalog and targets: {{ skill_link("kmp-gradle") }}
- Layers, features and dependency injection: {{ skill_link("kmp-architecture") }}
- View models and UI state: {{ skill_link("kmp-state") }}
- Compose screens and navigation: {{ skill_link("kmp-compose") }}
- Theme, tokens and shared components: {{ skill_link("kmp-design-system") }}
- Accessibility semantics: {{ skill_link("kmp-a11y") }}
- HTTP, database and offline sync: {{ skill_link("kmp-data") }}
- Platform ports and the three host apps: {{ skill_link("kmp-platform") }}
- Tests in the shared module: {{ skill_link("kmp-testing") }}
- Running the app on a device: {{ skill_link("kmp-qa") }}

## Core rules

- When two rules conflict, the more specific sibling wins within its domain.
- Write product code in `commonMain` first. Move a line to a platform source set only when it calls a platform API, and then follow {{ skill_link("kmp-platform") }}.
- Every target stays green on every change. A change that compiles for Android alone is unfinished.
- Add a dependency through `gradle/libs.versions.toml`, and pick the multiplatform artifact. An artifact with only an Android or JVM variant belongs in that platform source set behind a port.
- Keep the three host modules free of product logic. They start dependency injection and show the shared root composable.

## Closing commands

Run these from the repo root before reporting a change done. Each must exit 0.

```bash
./gradlew :shared:jvmTest
./gradlew :androidApp:assembleDebug :desktopApp:compileKotlin
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew detekt ktlintCheck
```

`compileKotlinIosSimulatorArm64` compiles the iOS source sets on Linux, macOS and Windows. Linking the iOS framework needs macOS, and the iOS simulator and iOS tests need an Apple silicon Mac. On another host report those steps as `blocked` and name the host.
