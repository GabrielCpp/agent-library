# iOS host

## Files

```text
iosApp/
  Configuration/Config.xcconfig    TEAM_ID, BUNDLE_ID, APP_NAME
  iosApp.xcodeproj
  iosApp/iOSApp.swift              @main App, calls startIosApp once
  iosApp/ContentView.swift         wraps MainViewController
  iosApp/Info.plist
shared/src/iosMain/kotlin/.../IosEntry.kt
```

## Kotlin entry

```kotlin
fun startIosApp(apiBaseUrl: String) {
    startApp(AppConfig(apiBaseUrl = apiBaseUrl), iosPlatformModule())
}

@Suppress("FunctionName", "ktlint:standard:function-naming")
fun MainViewController(): UIViewController = ComposeUIViewController { App() }
```

## Swift side

```swift
@main
struct iOSApp: App {
    init() { IosEntryKt.startIosApp(apiBaseUrl: "https://api.example.com") }
    var body: some Scene { WindowGroup { ContentView() } }
}

struct ComposeView: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController { IosEntryKt.MainViewController() }
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
}

struct ContentView: View {
    var body: some View { ComposeView().ignoresSafeArea() }
}
```

- A top-level Kotlin function in `IosEntry.kt` appears in Swift as a static member of `IosEntryKt`.
- Swift holds no screen and no logic. A new screen never touches the Xcode project.

## Framework step

- The Xcode target has a Run Script phase before Compile Sources: `cd "$SRCROOT/.." && ./gradlew :shared:embedAndSignAppleFrameworkForXcode`.
- The target sets `ENABLE_USER_SCRIPT_SANDBOXING = NO` so the script can run Gradle.
- The framework is static and named `Shared`, so Swift writes `import Shared`.
- Use direct framework integration. Add CocoaPods or a Swift package export only when a dependency requires it.

## Platform code

- Call Apple APIs from `iosMain` through `platform.Foundation.*` and `platform.UIKit.*`.
- An `iosMain` file that passes pointers needs `@OptIn(ExperimentalForeignApi::class)` on the smallest function.
- The database file goes in the documents directory from `NSFileManager.defaultManager.URLForDirectory(NSDocumentDirectory, ...)`.
- Each permission needs its usage string in `Info.plist`, or the app crashes at the request.
- A Kotlin exception that crosses into Swift ends the app. Catch inside Kotlin and return a result type.

## Commands, on an Apple silicon Mac

```bash
./gradlew :shared:iosSimulatorArm64Test
xcodebuild -project iosApp/iosApp.xcodeproj -scheme iosApp -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16' -derivedDataPath build/ios build
xcrun simctl boot 'iPhone 16'
xcrun simctl install booted build/ios/Build/Products/Debug-iphonesimulator/*.app
xcrun simctl launch booted <bundle id>
xcrun simctl io booted screenshot ios.png
```

An Intel Mac builds for a device only: `xcodebuild ... -sdk iphoneos -destination 'generic/platform=iOS' build`, then install on a connected iPhone.

On Linux the only iOS check is `./gradlew :shared:compileKotlinIosSimulatorArm64`.
