---
name: kmp-qa
description: "Verifying a Kotlin Multiplatform app on Android emulator, desktop and iOS simulator with Maestro flows and screenshots. Load when verifying a change in the running app, capturing a screenshot as proof, or writing or fixing a Maestro flow."
applyTo: '**/.maestro/**/*.yaml'
tags: [kmp, mobile, qa]
---

# Local Run and Smoke QA

Tests prove logic. This skill proves that the screen a change touched works in the running app. Bound every command with `timeout` so a stuck emulator or build cannot hold the session.

## Pick the targets

- A change in `commonMain` is checked on Android and on desktop. iOS is added when the host is an Apple silicon Mac.
- A change in one platform source set or host app is checked on that target.
- A target with no device, emulator, display or Mac is reported as `blocked` with the reason. A passing compile is never reported as a QA pass.

## Android

```bash
adb devices
timeout 600 ./gradlew :androidApp:assembleDebug
timeout 120 adb -s <device id> install -r androidApp/build/outputs/apk/debug/androidApp-debug.apk
timeout 300 maestro --device <device id> test .maestro/<flow>.yaml
```

- Name the device in every `adb` and `maestro` command. With two devices attached, a command with no id fails or picks the wrong one.
- Prefer an emulator. Use a physical phone only when the user names it.
- When no device is listed, start an existing emulator with `emulator -avd <name> -no-snapshot-save` in the background and wait for `adb -s <id> shell getprop sys.boot_completed` to print `1`.

## Maestro flow

```yaml
appId: com.example.notes
---
- launchApp:
    clearState: true
- assertVisible: "Notes"
- tapOn: "Groceries"
- assertVisible: "Milk, eggs, bread"
- takeScreenshot: .maestro/out/note-detail
- back
- assertVisible: "Notes"
```

- Keep one small flow per touched journey in `.maestro/`. Start from `launchApp` and reach the screen by the taps a user makes. Use no deep link.
- Tap and assert by visible text or content description. A flow that needs an id points at missing semantics, as in {{ skill_link("kmp-a11y") }}.
- Start with `clearState: true` so the result does not depend on the last run.
- Take a screenshot at the state the change produces. Keep `.maestro/out/` out of git.
- The same flow runs on an iOS simulator with the bundle id as `appId`.

## Desktop

```bash
JAVA_TOOL_OPTIONS="-D<app>.dataDir=$(mktemp -d)" timeout 300 ./gradlew :desktopApp:run &
```

- Start with an empty data directory through the app's system property, so the run begins from first launch.
- Wait for the window, then capture it. On Linux with X11: find the id with `xwininfo -root -tree | grep '"<window title>"'` and capture with `import -window <id> desktop.png`. On macOS: `screencapture -l <window id> desktop.png`.
- Maestro does not drive a desktop window. Cover desktop interaction with the screen tests in {{ skill_link("kmp-testing") }}, and use the run for launch, layout at window size and the screenshot.
- Stop the app when done. A leftover process holds the database file.
- With no display, report desktop as `blocked`.

## iOS

Only on an Apple silicon Mac. An Intel Mac has no simulator for this stack, so report `blocked: needs Apple silicon or a connected iPhone`. Build, install, launch and capture with the `xcodebuild` and `xcrun simctl` commands in the iOS reference of {{ skill_link("kmp-platform") }}, then run the same Maestro flow. On any other host, run `./gradlew :shared:compileKotlinIosSimulatorArm64` and report the iOS run as `blocked: needs macOS`.

## Success signal

A target passes when all of these hold:

- the app launches to its first screen with no crash,
- the flow or manual path reaches the touched screen and every assertion passes,
- the screenshot shows the changed behavior,
- `adb -s <device id> logcat -d -b crash` is empty for the app on Android, and the Gradle run printed no exception on desktop.

## Report

State one line per target: `pass` with the screenshot path, `fail` with the failing step and the log line, or `blocked` with the reason. Then stop the emulator and the desktop app that this run started.
