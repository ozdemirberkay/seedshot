# Seedshot mode recipes

Seedshot mode is a small module in the app that renders any listed screen with seed data, on demand. The recipes below are starting points. Adapt them to the project's architecture (its DI, state management and navigation), and keep the footprint small.

## Contents
- [The contract](#the-contract)
- [Swift: SwiftUI / UIKit](#swift-swiftui--uikit)
- [Kotlin: Jetpack Compose / Views](#kotlin-jetpack-compose--views)
- [Flutter](#flutter)
- [React Native (bare)](#react-native-bare)
- [Expo](#expo)
- [Pitfalls on every stack](#pitfalls-on-every-stack)
- [Capture troubleshooting](#capture-troubleshooting)

## The contract

| | |
|---|---|
| **Lock 1: build flag** | The code compiles in, or is reachable, only in a seedshot build. Store builds never set the flag. |
| **Lock 2: launch parameter** | Even in a seedshot build, nothing changes unless `SEEDSHOT_SCREEN` is present at launch. |
| **Parameters** | `SEEDSHOT_SCREEN` (a screen id from the config) and `SEEDSHOT_LOCALE` (BCP 47, e.g. `tr-TR`). On iOS, `ios.py launch` passes them as environment variables **and** as launch arguments (`-SEEDSHOT_SCREEN home`, readable through `UserDefaults`). On Android, `android.py launch` passes them as string intent extras. |
| **Fixed clock** | Expose `Seedshot.now` = today at 09:41 local time. Use it wherever the UI derives text from the clock ("Good morning", "2 hours ago"), so it matches the status bar. |
| **Footprint** | One folder for the module and seed files, plus one-line hooks at: app entry (read parameters), the data boundary (swap source), and navigation (open the requested screen). List every hook in the final report. |

---

## Swift: SwiftUI / UIKit

**Build** (flag as a compilation condition, Debug configuration):

```bash
xcodebuild -scheme <Scheme> [-workspace <App>.xcworkspace | -project <App>.xcodeproj] \
  -configuration Debug -sdk iphonesimulator -destination "id=$UDID" \
  -derivedDataPath build/seedshot \
  SWIFT_ACTIVE_COMPILATION_CONDITIONS="DEBUG SEEDSHOT" build
# app: build/seedshot/Build/Products/Debug-iphonesimulator/<Product>.app
```

Add `build/seedshot/` to `.gitignore` if it isn't covered already.

**Module** (`<App>/Seedshot/Seedshot.swift`):

```swift
#if SEEDSHOT
import Foundation

enum Seedshot {
    static let screen: String? = param("SEEDSHOT_SCREEN")
    static let locale: String = param("SEEDSHOT_LOCALE") ?? "en-US"
    static var isActive: Bool { screen != nil }
    static let now: Date = Calendar.current.date(bySettingHour: 9, minute: 41, second: 0, of: Date())!

    private static func param(_ key: String) -> String? {
        ProcessInfo.processInfo.environment[key] ?? UserDefaults.standard.string(forKey: key)
    }

    /// Decodes Seedshot/Data/seedshot-<locale>.json, falling back to en-US.
    static func load<T: Decodable>(_ type: T.Type) -> T {
        let url = Bundle.main.url(forResource: "seedshot-\(locale)", withExtension: "json")
            ?? Bundle.main.url(forResource: "seedshot-en-US", withExtension: "json")!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try! decoder.decode(T.self, from: Data(contentsOf: url))
    }
}
#endif
```

Seed JSON files ship as bundle resources. They're inert without the flag. To keep them out of Release builds too, add `EXCLUDED_SOURCE_FILE_NAMES = seedshot-*.json` to the Release configuration of the app target.

**Hooks:**
- **Data:** inject at the composition root.
  - Protocol-backed repository: `let repo: TransactionsRepository = Seedshot.isActive ? SeedTransactionsRepository() : LiveTransactionsRepository()`, inside `#if SEEDSHOT … #endif` with the live path in `#else`.
  - SwiftData: `ModelConfiguration(isStoredInMemoryOnly: true)`, then insert seed models before the first view appears.
  - Core Data: use an in-memory store (`NSInMemoryStoreType`).
  - Plain REST: a `URLProtocol` subclass that answers from seed JSON keyed by path. `URLProtocol.registerClass` only covers `URLSession.shared`. For custom sessions (Alamofire included), prepend it to `configuration.protocolClasses`.
- **Navigation:** at the root, map `Seedshot.screen` to state. Set the selected tab, push the detail for a specific seed item (`path = [seed.items[2]]`), present the sheet. Reuse the real views, so the screenshot shows the real UI.
- **Path to screen:** pretend signed-in (seed user/token in memory, never the keychain), and mark onboarding and "what's new" as seen. Don't request permissions, don't show rating prompts, don't start analytics. To have permissions already granted, run `xcrun simctl privacy $UDID grant all <bundle-id>` before launch.
- **Animations:** `UIView.setAnimationsEnabled(false)` early in launch settles UIKit and most SwiftUI transitions. Stop looping animations (Lottie, shimmer) in seedshot mode.

---

## Kotlin: Jetpack Compose / Views

**Build flag** in `app/build.gradle(.kts)`. Constant-false in store builds, so R8 strips the seedshot branches:

```kotlin
android {
    buildFeatures { buildConfig = true }
    defaultConfig {
        buildConfigField("boolean", "SEEDSHOT", (project.findProperty("seedshot") ?: "false").toString())
    }
}
```

```bash
./gradlew :app:assembleDebug -Pseedshot=true
# apk: app/build/outputs/apk/debug/app-debug.apk  (add the flavor to the task/path if the app uses flavors)
```

**Module** (`com.example.app.seedshot`):

```kotlin
object Seedshot {
    var screen: String? = null; private set
    var locale: String = "en-US"; private set
    val isActive: Boolean get() = BuildConfig.SEEDSHOT && screen != null
    val now: java.time.LocalDateTime get() = java.time.LocalDate.now().atTime(9, 41)

    fun init(intent: android.content.Intent) {
        if (!BuildConfig.SEEDSHOT) return
        screen = intent.getStringExtra("SEEDSHOT_SCREEN")
        locale = intent.getStringExtra("SEEDSHOT_LOCALE") ?: locale
    }

    fun json(context: android.content.Context): String =
        runCatching { context.assets.open("seedshot/$locale.json") }
            .getOrElse { context.assets.open("seedshot/en-US.json") }
            .bufferedReader().use { it.readText() }
}
```

- Call `Seedshot.init(intent)` in `MainActivity.onCreate` before `setContent`/`setContentView`.
- Put seed files in `app/src/debug/assets/seedshot/` so release APKs don't contain them.

**Hooks:**
- **Data:**
  - Hilt/Koin: bind repository interfaces to seed implementations when `Seedshot.isActive`.
  - Retrofit: add an OkHttp `Interceptor` that builds a `Response` from seed JSON for known paths.
  - Room: use `Room.inMemoryDatabaseBuilder` and insert the seed.
- **Navigation:** choose `NavHost(startDestination = …)` from `Seedshot.screen`, or navigate once in a `LaunchedEffect`.
- **Locale:** `android.py` sets the per-app locale (API 33+), and resources follow it. If the app has its own language setting, apply `Seedshot.locale` with `AppCompatDelegate.setApplicationLocales`.
- **Dynamic color:** on Android 12+, Material You colors come from the emulator wallpaper. Disable dynamic color in seedshot mode if the brand palette should show.
- **Permissions:** `android.py install` grants runtime permissions (`-g`). The notification permission dialog won't appear.

---

## Flutter

**Build** (const flag, tree-shaken when false):

```bash
flutter build ios --simulator --debug --dart-define=SEEDSHOT=true
# app: build/ios/iphonesimulator/Runner.app
flutter build apk --debug --dart-define=SEEDSHOT=true
# apk: build/app/outputs/flutter-apk/app-debug.apk
```

Add `--flavor <name>` (and `-t lib/main_<flavor>.dart`) if the project uses flavors. A debug build on a simulator or emulator launches standalone, with no `flutter run` attached.

**Module** (`lib/seedshot/seedshot.dart`):

```dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';

const kSeedshot = bool.fromEnvironment('SEEDSHOT');

class Seedshot {
  static String? screen;
  static String locale = 'en-US';
  static bool get isActive => kSeedshot && screen != null;
  static DateTime get now { final d = DateTime.now(); return DateTime(d.year, d.month, d.day, 9, 41); }

  static Future<void> init() async {
    if (!kSeedshot) return;
    final Map<String, String?> p = Platform.isAndroid
        ? Map<String, String?>.from(await const MethodChannel('seedshot').invokeMethod('params') ?? {})
        : Platform.environment; // iOS: simctl passes SEEDSHOT_* as environment variables
    screen = p['SEEDSHOT_SCREEN'];
    locale = p['SEEDSHOT_LOCALE'] ?? locale;
  }

  static Future<Map<String, dynamic>> data() async {
    final raw = await rootBundle.loadString('assets/seedshot/$locale.json')
        .catchError((_) => rootBundle.loadString('assets/seedshot/en-US.json'));
    return jsonDecode(raw) as Map<String, dynamic>;
  }
}
```

Android needs a tiny channel to read the intent extras (`MainActivity.kt`). It returns nulls in normal launches:

```kotlin
class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "seedshot").setMethodCallHandler { call, result ->
            if (call.method == "params") result.success(mapOf(
                "SEEDSHOT_SCREEN" to intent.getStringExtra("SEEDSHOT_SCREEN"),
                "SEEDSHOT_LOCALE" to intent.getStringExtra("SEEDSHOT_LOCALE"),
            )) else result.notImplemented()
        }
    }
}
```

**Hooks:**
- **`main()`:** `WidgetsFlutterBinding.ensureInitialized(); await Seedshot.init();` before `runApp`.
- **Debug banner:** `MaterialApp(debugShowCheckedModeBanner: kSeedshot ? false : <existing value>, …)`.
- **Data:**
  - Riverpod: `ProviderScope(overrides: Seedshot.isActive ? seedOverrides() : const [])`.
  - get_it: register seed repositories.
  - Bloc: inject seed repositories.
  - Dio: an `InterceptorsWrapper` whose `onRequest` resolves with seed JSON.
- **Navigation:** GoRouter `initialLocation: Seedshot.isActive ? seedRoute(Seedshot.screen!) : '/'`, or a one-time `Navigator.push` after the first frame.
- **Seed assets:** declare `assets/seedshot/` in `pubspec.yaml`. They're inert in store builds, because `kSeedshot` is false and nothing reads them.
- **Locale:** Flutter follows the device/app locale set by the scripts. If the app stores its own locale choice, pass `locale: Seedshot.isActive ? Locale(...) : …` to `MaterialApp`.

---

## React Native (bare)

**Build flag:** use what the project already has (`react-native-config`, `.env` + babel plugin). Otherwise, add `babel-plugin-transform-inline-environment-variables` as a dev dependency with `{ include: ['SEEDSHOT'] }`, and read `process.env.SEEDSHOT === '1'`.

**Build in Release** (no Metro, no LogBox, no dev menu):

```bash
SEEDSHOT=1 npx react-native run-ios --mode Release --simulator "Seedshot iPhone 17 Pro"
cd android && SEEDSHOT=1 ./gradlew assembleRelease
# apk: android/app/build/outputs/apk/release/app-release.apk (the template signs release with the debug key)
```

If the build command installs the app itself, skip `install` and go straight to `launch`.

**Parameters:** `react-native-launch-arguments` reads iOS launch arguments and Android intent extras, which are exactly what the scripts send:

```ts
import { LaunchArguments } from 'react-native-launch-arguments';
const SEEDSHOT = process.env.SEEDSHOT === '1';
const args = SEEDSHOT ? LaunchArguments.value<{ SEEDSHOT_SCREEN?: string; SEEDSHOT_LOCALE?: string }>() : {};
export const seedshot = { active: SEEDSHOT && !!args.SEEDSHOT_SCREEN, screen: args.SEEDSHOT_SCREEN, locale: args.SEEDSHOT_LOCALE ?? 'en-US' };
```

**Hooks:**
- **Data:**
  - React Query: `queryClient.setQueryData` for each key before rendering.
  - Redux/Zustand: preloaded state.
  - HTTP: an axios adapter or a `fetch` wrapper that answers from seed JSON.
- **Navigation:** React Navigation `initialState` derived from `seedshot.screen`, or `navigation.reset` on mount.
- **Seed JSON:** `require('./seedshot/data/tr-TR.json')` inside the seedshot module, behind the `SEEDSHOT` check so Metro's dead-code elimination drops it from store bundles.

---

## Expo

Seedshot needs a native build (Expo Go can't receive launch arguments). `npx expo run:*` prebuilds automatically.

```bash
EXPO_PUBLIC_SEEDSHOT=1 npx expo run:ios --configuration Release --device "Seedshot iPhone 17 Pro"
EXPO_PUBLIC_SEEDSHOT=1 npx expo run:android --variant release --device Seedshot_Phone
```

- `EXPO_PUBLIC_*` variables are inlined at bundle time, so `process.env.EXPO_PUBLIC_SEEDSHOT === '1'` is the build flag.
- Use `react-native-launch-arguments` for parameters, as in bare React Native. It autolinks.
- **expo-router:** in the root layout, when seedshot is active, `router.replace(seedRoute(screen))` once fonts and splash are ready.
- **expo-localization:** reads the device/app locale set by the scripts.

---

## Pitfalls on every stack

- **Remote images:** seed data should reference bundled assets. Network images load late, flicker and may fail offline.
- **Splash screens, async fonts, first-frame fetches:** `shot` waits until the screen stops changing, but make sure seedshot mode finishes loading quickly and deterministically.
- **Clock-driven text** ("Good evening", "in 3 hours"): use `Seedshot.now`.
- **Feature flags / remote config:** pin them in seedshot mode to the values the shipped app will have.
- **Empty and error states:** only if they're deliberately on the shot list. Otherwise any of them in a capture means the seed is incomplete.
- **Text fields:** don't auto-focus them, so no keyboard appears.
- **Accessibility text size:** the scripts leave the default size. Don't capture at accessibility sizes unless asked.

---

## Capture troubleshooting

**Locale isn't applied.**
- iOS: `ios.py launch` passes `-AppleLanguages (tr-TR) -AppleLocale tr_TR` for that launch only. This works for native, Flutter and React Native apps. An app that keeps its own language preference ignores it, so apply `SEEDSHOT_LOCALE` in seedshot mode.
- Android: `android.py launch` sets a per-app locale (`cmd locale set-app-locales`, API 33+, no root, works on Google Play images). If that can't be verified, it falls back to the system locale. That needs root, so a `google_apis` image rather than `google_apis_playstore`. If both fail, it stops with an error.
- Right-to-left languages (ar, he, fa, ur) mirror the layout. Check charts, progress bars and directional icons closely.

**Status bar isn't clean.**
- iOS overrides survive relaunches but not a reboot, so run `statusbar` after every `boot`.
- Android demo mode likewise: run `demo` after every `boot`.

**Screen never settles.** `shot` saves after two identical frames in a row, and warns when that doesn't happen within `--settle-timeout`. The causes are looping animations (Lottie, shimmer, pulsing badges), a blinking cursor, video or an auto-advancing carousel, or a live clock or countdown. Stop or freeze them in seedshot mode rather than raising the timeout.

**Landscape-only app.** Both tools capture in portrait.
- iOS has no simctl rotate command. Lock the orientation in seedshot mode. If the image comes out rotated, use `sips -r 90 file.png` and then `verify.py --fix`, since sips may add alpha back.
- Android: run `adb shell settings put system accelerometer_rotation 0 && adb shell settings put system user_rotation 1` before launch.

**Simulator runtime.** `ios.py` picks the newest runtime the active Xcode SDK supports, and skips newer betas. Override it with `--runtime "iOS 26.0"`. If the deployment target is above every installed runtime, ask the user to install one (Xcode → Settings → Components).

| Symptom | Fix |
|---|---|
| `simctl launch` fails with "not installed" | The bundle id is wrong, or the app was built for a device. Rebuild with `-sdk iphonesimulator`. |
| App shows real or empty data | Lock 1 is missing: the build lacks the seedshot flag. |
| App ignores `SEEDSHOT_SCREEN` | Lock 2 isn't wired. On iOS, read both the environment and `UserDefaults`. On Android, read the extras in the activity that receives the launch intent. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | A differently signed copy is installed. Run `adb -s $SERIAL uninstall <pkg>` and retry. |
| Emulator never finishes booting | Check `~/.android/avd/<AVD>.seedshot.log` and try `--headless`. Low disk space and old emulator versions are the usual causes. |
| Dark screenshots look light on Android | The app forces or caches its theme. Make it follow the system theme in seedshot mode. |
| Wrong or system fonts | Async font loading wasn't finished before the shot. Wait for fonts in seedshot mode. |
