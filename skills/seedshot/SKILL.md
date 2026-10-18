---
name: seedshot
description: Capture App Store and Google Play screenshots of a mobile app, filled with realistic demo data that is consistent across devices and natively localized per language. Covers every important screen, light and dark mode, every language the app supports, iPhone/iPad simulators and Android phone/tablet emulators, all at store-accepted sizes. Builds an isolated, release-safe "seedshot mode" in the project that injects seed data and opens each screen directly, then captures, verifies and organizes the images. Use this whenever the user wants store screenshots, App Store / Play Store listing images, screenshots in several languages or in dark mode, needs to refresh screenshots for a new release, or asks to "take screenshots of the app" for publishing. Works with Swift/SwiftUI/UIKit, Kotlin/Jetpack Compose, Flutter, React Native and Expo projects.
license: MIT
compatibility: Requires a local mobile project. iOS capture needs macOS with Xcode (xcrun simctl). Android capture needs the Android SDK (adb, emulator, avdmanager). Python 3 for helper scripts; Pillow is optional (only for fixing alpha channels).
allowed-tools:
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
  - Bash(xcrun simctl *)
  - Bash(adb *)
---

# Seedshot

Store screenshots are an app's shop window. The capture command is the easy part. What makes them good is **what's on screen**: a populated, believable app, written natively in each language, telling the same story on every device. Your job is to produce that set with no mistakes. One untranslated label, one loading spinner or one "John Doe" in a store listing is exactly the failure this skill exists to prevent.

The work has six phases. Only one of them (Plan) needs the user; the rest you run on your own.

1. **Discover**: understand the project.
2. **Plan**: agree on the capture matrix with the user, then save it.
3. **Seed**: build the localized demo dataset.
4. **Seedshot mode**: make the app render any screen with that data, on demand.
5. **Capture**: run a pilot first, then the full matrix.
6. **Verify & deliver**: run the checks, look at every image, then report.

If the user passed arguments (e.g. `ios only`, `tr en`, `skip dark`, `screens: home, stats`), treat them as overrides to the defaults and the saved config.

## The capture matrix

Every screenshot is one cell of: **platform × device class × locale × appearance × screen**.

| Dimension | Default | Source |
|---|---|---|
| Platforms | Every platform the project builds for | Detected (`ios/`, `android/`, `*.xcodeproj`, Gradle app module) |
| Devices | iOS: iPhone 6.3" (required slot) + iPad 13" (required if the app runs on iPad). Android: 1080×1920 phone + 1440×2560 tablet | See `references/store-specs.md` |
| Locales | Every language the app ships translations for | Detected from localization files |
| Appearances | `light` and `dark`, or only `light` if the app has no dark theme | Detected |
| Screens | 4–8 screens that sell the app, in store order | Proposed by you, approved by the user |
| Output | `~/Desktop/seedshot/<AppName>/` | Config |

The default devices are chosen for store acceptance, not personal preference. Apple requires the 6.3" iPhone and 13" iPad sizes, and scales those down for smaller devices. Google Play rejects phone images longer than 2:1 (most modern Pixel emulators are 20:9), and wants 9:16 for tablets and featuring. Don't swap devices casually. If the user asks for a different one, say what that means for the store slot.

### Config file

The matrix is saved to `seedshot.config.json` at the project root, so the next release can re-run with no questions asked. If the file exists:
- load it
- update anything that changed in the project (new screens, new locales)
- show a short summary instead of the full planning conversation.

```json
{
  "app": { "name": "Pennywise", "stack": "flutter",
    "ios": { "bundleId": "com.example.pennywise", "build": "flutter build ios --simulator --debug --dart-define=SEEDSHOT=true", "appPath": "build/ios/iphonesimulator/Runner.app" },
    "android": { "package": "com.example.pennywise", "build": "flutter build apk --debug --dart-define=SEEDSHOT=true", "apkPath": "build/app/outputs/flutter-apk/app-debug.apk" } },
  "devices": { "ios": ["phone", "tablet"], "android": ["phone", "tablet"] },
  "locales": ["en-US", "tr-TR"],
  "appearances": ["light", "dark"],
  "screens": [
    { "id": "home", "order": 1, "shows": "Dashboard: balance, weekly spending chart, 4 recent transactions" },
    { "id": "insights", "order": 2, "shows": "Monthly insights: category donut, 3 tip cards" }
  ],
  "output": "~/Desktop/seedshot/Pennywise",
  "seed": { "module": "lib/seedshot/", "data": "assets/seedshot/", "story": "A freelance designer mid-month, savings on track." }
}
```

## 1. Discover

Read the project before asking anything. Establish:

- **Stack**: Swift/SwiftUI/UIKit, Kotlin/Compose/Views, Flutter, React Native (bare) or Expo. Monorepos may have several apps; ask which one if it's unclear.
- **Identifiers**: iOS bundle id, scheme and workspace/project. Android application id, app module and launcher activity.
- **Locales**:
  - iOS: `*.lproj`, `Localizable.xcstrings`
  - Android: `res/values-*/strings.xml`
  - Flutter: `l10n/*.arb`
  - RN/Expo: i18n JSON
  - Also note the default/development language.
- **Dark mode**:
  - Supported if you find dark color assets, `values-night`, `darkTheme`/`ThemeMode`, or `useColorScheme`.
  - Not supported if it's forced off (`UIUserInterfaceStyle = Light`, `forceDarkAllowed` false with no night resources, a hard-coded light theme).
- **Tablet support**:
  - iOS: `TARGETED_DEVICE_FAMILY` contains `2`.
  - Android: does the app have tablet layouts, and is it restricted to phones?
- **Screens**: read the navigation (tab bars, `NavigationStack`, `NavHost`, GoRouter/auto_route, React Navigation/expo-router) and list candidate screens.
- **Data flow**: where each candidate screen gets its data:
  - REST/GraphQL client
  - local database (SwiftData/Core Data/Room/Realm/Hive/SQLite)
  - Firebase/Supabase
  - in-memory state store
  - Also find where auth, onboarding, paywalls, permission prompts and rating prompts are triggered.
- **Existing seedshot mode**: check for a previous run (a `seedshot` folder/module, `seedshot.config.json`). Reuse and update it rather than starting over.
- **Toolchain**: run `python3 ${CLAUDE_SKILL_DIR}/scripts/ios.py doctor` and/or `python3 ${CLAUDE_SKILL_DIR}/scripts/android.py doctor`. If something is missing (no simulator runtime, no Android system image), tell the user exactly what to install. Downloads are large, so ask before starting one.

## 2. Plan (the one checkpoint)

Present a compact plan and wait for the user's approval:

- stack, platforms, the device for each class (with pixel size and the store slot it fills)
- locales, and appearances
- the **ordered screen list**, with one line each on what it will show. Example: "02 · Stats: weekly chart trending up, 3 insight cards". The first three images matter most, because stores show them in search results. Lead with the app's core value, not with settings, login or onboarding.
- output path, and total image count (e.g. 6 screens × 2 locales × 2 appearances × 4 devices = 96)
- what you'll add to the project (the seedshot module) and that it is inert in release builds.

On approval, write `seedshot.config.json`. This is the only planned interruption. After it, work autonomously and only stop for genuine blockers.

## 3. Seed: build the dataset

Read `references/seed-data.md` before writing any data. The essentials:

- **One story, told natively in each language.** Every locale gets the same structure: same number of items, same order, same states, same chart shape, same magnitudes. The content is culturally native: local names, places, currency, units, date and number formats, idioms. Write it the way a native speaker would. Don't translate it word for word.
- **Show the app at its best.** Populated, varied, plausible and aspirational. No lorem ipsum, "Test", "John Doe", `foo@bar.com`, zero balances or empty lists, unless an empty state is deliberately one of the shots.
- **Fill the tablet.** Make sure there are enough items that the 13" iPad and the 10" tablet layouts don't look sparse.
- **Fresh dates.** Generate dates relative to launch time, so nothing looks stale. Keep visible times consistent with the 9:41 status bar.
- **Safe content.** No real people, real brands or trademarks, and no real personal data. For images, prefer assets already in the project, then generated neutral art (gradients, initials avatars, system icons). Never download images you don't have rights to. If the app's look depends on photos (recipes, travel, real estate), ask the user for a set.
- **Seed data lives in data files.** Use one JSON file per locale with identical structure, so parity is checkable: `python3 ${CLAUDE_SKILL_DIR}/scripts/verify.py --seed <seed-data-dir>`. It compares every locale's structure with the base locale's, and flags long text left identical (probably untranslated).

## 4. Seedshot mode

Seedshot mode is a small, self-contained addition to the app. It makes any listed screen render with seed data, deterministically, on demand. `references/seedshot-mode.md` has concrete recipes per stack; read the section for this project's stack. The contract:

- **Two locks.** The code is active only when (1) the build was made with the seedshot build flag (a Swift compilation condition, a Gradle property, a `--dart-define`, `EXPO_PUBLIC_SEEDSHOT`) **and** (2) the app was launched with a seedshot launch parameter. A store build has neither, so it can never show demo data. That's why the module can safely stay in the project.
- **Launch parameters** (iOS launch arguments/environment, Android intent extras):
  - `SEEDSHOT_SCREEN`: the screen id to open.
  - `SEEDSHOT_LOCALE`: e.g. `tr-TR`. Used to pick the seed file, and to set the in-app language if the app has its own language setting.
  - Appearance comes from the OS, which the capture scripts set.
- **Inject data at the data boundary, not in the views.** Swap a repository/service, override a provider, stub the HTTP layer (URLProtocol, OkHttp interceptor, Dio interceptor, fetch/axios adapter), or pre-fill an in-memory database. UI code stays untouched, so the screenshots show the real UI.
- **Clear the path to the screen.**
  - Use a fake signed-in session, and skip onboarding, paywalls, rating prompts, permission prompts, ads, analytics, crash-report dialogs and "what's new" sheets.
  - Open the requested screen in the requested state directly (tab selected, detail item chosen, sheet presented).
  - Hide debug banners and dev overlays. Stop or settle animations, especially looping ones.
- **Self-contained and reported.** Put everything in one folder (e.g. `Seedshot/`, `lib/seedshot/`, `src/seedshot/`, a `seedshot` source set), plus a few one-line hooks at the app entry and the data boundary. Never call real backends or write to real accounts.
- **Don't hide real bugs.** Missing translations, truncated labels and broken dark-mode colors are bugs real users see too. Don't paper over them inside seedshot mode. If the fix is small and clearly correct (e.g. adding a missing string to the localization file), make it in the app and list it in the report. Otherwise report it to the user.

## 5. Capture

Use the bundled scripts. They wrap the fiddly parts, so you don't re-derive them each time. Run each with `--help` for usage.

- `scripts/ios.py`: `doctor`, `device` (finds or creates a dedicated "Seedshot …" simulator for a device class), `boot`, `statusbar` (9:41, full battery and signal), `appearance`, `install`, `launch` (locale + seedshot parameters), `shot` (waits until the screen stops changing, then saves an alpha-free PNG), `cleanup`.
- `scripts/android.py`: `doctor`, `avd` (creates a dedicated AVD at a store-safe resolution), `boot`, `demo` (clean status bar via SystemUI demo mode), `appearance`, `install` (grants runtime permissions), `launch` (sets the per-app locale, then starts with seedshot extras), `shot`, `cleanup`.

```bash
S=${CLAUDE_SKILL_DIR}/scripts
UDID=$(python3 $S/ios.py device phone)        # or: tablet
python3 $S/ios.py boot $UDID && python3 $S/ios.py statusbar $UDID && python3 $S/ios.py install $UDID <App.app>
python3 $S/ios.py appearance $UDID dark
python3 $S/ios.py launch $UDID <bundle-id> --locale tr-TR --screen stats
python3 $S/ios.py shot $UDID <output>/ios/phone/tr-TR/dark/02-stats.png

AVD=$(python3 $S/android.py avd phone)        # or: tablet
SERIAL=$(python3 $S/android.py boot $AVD)     # first boot of a new AVD takes 1–3 minutes
python3 $S/android.py demo $SERIAL && python3 $S/android.py install $SERIAL <app.apk>
# then appearance / launch / shot exactly as on iOS, with $SERIAL and the package name
```

Build once per platform with the seedshot flag. Every locale's seed data is bundled, so locales and appearances switch at launch with no rebuild. Then:

1. **Pilot first.** Capture one screen on one device in one locale. Open the image and inspect it closely. Most problems surface here: wrong data, a leftover dialog, the debug banner, the wrong language, a spinner. Fixing them now costs one rebuild instead of a hundred bad images.
2. **Full matrix.** Loop platform → device → locale → appearance → screen, with a fresh launch for every shot (`launch` terminates the previous instance). Name files:

   ```
   <output>/<ios|android>/<phone|tablet>/<locale>/<light|dark>/<NN>-<screen-id>.png
   ```

   `NN` is the store order from the plan (`01`, `02`, …). Each folder is then a ready-to-upload set in the right order.
3. **Don't overwrite earlier runs.** If the output folder already has images, move it aside to `<output>.bak-<YYYYMMDD-HHMM>` instead of deleting it.

If a capture step misbehaves (locale not applied, screen never settles, landscape-only app, install errors), see "Capture troubleshooting" at the end of `references/seedshot-mode.md`.

## 6. Verify & deliver

**Automated checks.** Run `python3 ${CLAUDE_SKILL_DIR}/scripts/verify.py <output>`. It checks:
- pixel sizes against each store slot
- alpha channels (both stores reject them)
- per-folder counts (Apple ≤ 10, Play ≤ 8, Play tablets ≥ 4 recommended)
- that every locale/appearance folder has the same screens.

Add `--fix` to strip alpha channels. Fix every error before delivering.

**Visual review: look at every image.** It is tedious, and it is the step that makes this skill worth using. For each image, check:
- **Language**: everything is in the folder's language. No mixed languages, no raw keys like `home.title`, and dates/numbers/currency are formatted for that locale.
- **Appearance**: matches the folder (`dark` really is dark), and no unreadable text or invisible icons.
- **Completeness**: no spinners, skeletons, placeholder images, empty states, half-finished animations, keyboards, dialogs, toasts or debug banners.
- **Status bar**: clean (9:41, full battery and signal).
- **Layout**: no truncation, overflow or clipped text, which is common in German, Turkish, Finnish and Russian.
- **Consistency**: the same story as the other locales and devices.

Re-capture anything that fails, then re-run `verify.py`.

**Contact sheet.** Run the final check with `--sheet`. It also writes `<output>/index.html`, a grid of every screen across locales and appearances, so the user can review the whole set at a glance. Open it for them (`open` on macOS).

**Clean up.** Run `ios.py cleanup` / `android.py cleanup`. They clear status-bar overrides and shut down the dedicated simulators and emulators.

**Final report.** Keep it short:
- the output path and the contact sheet
- image counts per platform/device/locale/appearance
- files added or changed in the project: the seedshot module, its hook points, and any real bugs you fixed
- how to re-run next release: invoke seedshot again; the config and module are reused
- anything the user must do in the store consoles (e.g. "Play: tablet listing needs at least 4 images, you have 5 ✓").

Never commit. Leave changes in the working tree for the user to review. If the project is a git repo, end with a `git status` summary.

## Reference files

- `references/store-specs.md`: App Store and Google Play size, format and count rules, with sources. Read it when choosing or changing devices, or when `verify.py` flags something.
- `references/seed-data.md`: how to write excellent, consistent, localized seed data. Read it before Phase 3.
- `references/seedshot-mode.md`: per-stack recipes (SwiftUI/UIKit, Compose/Views, Flutter, React Native, Expo) for the build flag, launch parameters, data injection and screen routing. Read the relevant section before Phase 4. Its last section, "Capture troubleshooting", covers locale, status bar, orientation and settle issues.
