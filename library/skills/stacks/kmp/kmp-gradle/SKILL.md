---
name: kmp-gradle
description: "Kotlin Multiplatform Gradle build: module split, Android Gradle Plugin 9, version catalog, source sets, KSP, detekt, ktlint. Load when creating a project, adding a dependency, plugin or target, upgrading Kotlin or Gradle, or a build fails."
applyTo: '**/*.gradle.kts,gradle/libs.versions.toml,gradle.properties,gradle/wrapper/gradle-wrapper.properties'
tags: [kmp, mobile, standards]
---

# Gradle Build

The full build files that these rules describe are in [references/build-files.md](references/build-files.md). Copy from there when starting a project.

## Modules

- `shared` applies `org.jetbrains.kotlin.multiplatform` and `com.android.kotlin.multiplatform.library`. It declares the Android, iOS and JVM targets.
- `androidApp` applies `com.android.application` alone. It depends on `projects.shared`.
- `desktopApp` applies `org.jetbrains.kotlin.jvm` and the Compose plugins. It depends on `projects.shared`.
- `iosApp` is an Xcode project and is absent from `settings.gradle.kts`.

Android Gradle Plugin 9 rejects `com.android.application` in the same module as the multiplatform plugin. A single `composeApp` module that holds everything is the pre-9 layout, so split it before upgrading.

## Targets in `shared`

```kotlin
kotlin {
    listOf(iosArm64(), iosSimulatorArm64()).forEach { target ->
        target.binaries.framework {
            baseName = "Shared"
            isStatic = true
        }
    }
    jvm()
    android {
        namespace = "com.example.app.shared"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        androidResources { enable = true }
    }
}
```

- Declare the Android target with `android { }` inside `kotlin { }`. `androidTarget { }` and `androidLibrary { }` are the removed and deprecated spellings.
- Declare `iosArm64()` and `iosSimulatorArm64()`. The `ios()` shortcut is gone. Never declare `iosX64()`: Compose Multiplatform, lifecycle and navigation ship no Intel simulator variant, so the build fails with `No matching variant` for `ios_x64`.
- Set `androidResources { enable = true }`. Compose resources fail to load on Android without it.
- Use the default source set hierarchy: `commonMain`, `androidMain`, `iosMain`, `jvmMain`, `commonTest`, `jvmTest`. Declare no source set by hand.

## Dependencies

- Every version sits in `gradle/libs.versions.toml`. A build file names `libs.<alias>` and no version string.
- Take Compose artifacts from the catalog by coordinate, such as `org.jetbrains.compose.material3:material3`. The `compose.material3` accessors are deprecated. `compose.desktop.currentOs` is the one accessor still in use.
- Take lifecycle and navigation from the `org.jetbrains.androidx.*` groups. The `androidx.*` groups of the same libraries ship no iOS variant.
- Pick one Ktor engine per platform source set: OkHttp for `androidMain` and `jvmMain`, Darwin for `iosMain`.
- Register a KSP processor once per target. A single `ksp(...)` line covers no multiplatform target.

```kotlin
dependencies {
    add("kspAndroid", libs.androidx.room.compiler)
    add("kspJvm", libs.androidx.room.compiler)
    add("kspIosArm64", libs.androidx.room.compiler)
    add("kspIosSimulatorArm64", libs.androidx.room.compiler)
}
```

## `gradle.properties`

```properties
org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
kotlin.daemon.jvmargs=-Xmx2g
org.gradle.configuration-cache=true
org.gradle.caching=true
kotlin.native.ignoreDisabledTargets=true
android.useAndroidX=true
android.nonTransitiveRClass=true
```

- Keep the configuration cache on. A plugin that breaks it gets replaced or isolated, and the cache stays.
- `kotlin.native.ignoreDisabledTargets=true` silences the warning that iOS test tasks are off on a Linux or Windows host.

## Versions that move together

| Change | Also change |
|---|---|
| Kotlin | KSP, the Compose compiler plugin, which takes the Kotlin version, and the Compose Multiplatform release that supports it |
| Compose Multiplatform | `compileSdk`, when the build reports that an Android artifact requires a newer API level |
| Gradle wrapper version | `distributionSha256Sum` in `gradle-wrapper.properties`, from the `.sha256` file next to the distribution |
| Android Gradle Plugin | Gradle, to a version inside the range that the Kotlin release notes list |
| Room | the Room Gradle plugin, the compiler and `sqlite-bundled` |

Read the Kotlin compatibility page before an upgrade and move one row at a time. `targetSdk` moves on its own schedule and can trail `compileSdk`.

## Static checks

- Apply detekt at the root with `buildUponDefaultConfig = true` and one `config/detekt.yml`. Point its `source` at every `src` folder, because the default covers no multiplatform source set.
- Apply the ktlint Gradle plugin to every subproject. Set `ktlint_function_naming_ignore_when_annotated_with = Composable` in `.editorconfig`.
- Run `./gradlew ktlintFormat` before fixing a style finding by hand.

## Closing check

```bash
./gradlew :shared:jvmTest :androidApp:assembleDebug :desktopApp:compileKotlin :shared:compileKotlinIosSimulatorArm64 detekt ktlintCheck
```

Exit 0 closes a build change. Run it twice after a plugin change. The second run must print `Configuration cache entry reused`.
