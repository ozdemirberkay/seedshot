# Seedshot

**Store-ready App Store and Google Play screenshots with realistic, localized demo data, captured by Claude Code.**

The capture command is the easy part of store screenshots. The hard part is what's on screen: a populated, believable app, written natively in every language, telling the same story on every device, in light and dark mode, at exactly the sizes the stores accept.

Seedshot is a [Claude Code](https://code.claude.com) skill that does all of it inside your project:

- **Reads your app.** It detects the stack, languages, dark-mode and tablet support and the navigation, then proposes the screens worth showing, in store order.
- **Writes seed data.** One story told natively in each language: same structure everywhere, local names, prices, units and formats.
- **Adds a release-safe *seedshot mode*.** It's double-locked, behind a build flag *and* a launch parameter. It injects the seed data at your data layer and opens any screen directly.
- **Captures the full matrix.** Platform × device × language × appearance × screen, on dedicated simulators and emulators, with a clean status bar.
- **Verifies everything.** A script checks store sizes, alpha channels, counts and missing images. Claude then looks at every image for untranslated text, truncation, spinners or stray dialogs.
- **Delivers** ready-to-upload folders and a one-page contact sheet.

## Install

In Claude Code:

```bash
claude plugin marketplace add ozdemirberkay/seedshot
claude plugin install seedshot@seedshot
```

Or, from inside a session: `/plugin install seedshot --marketplace ozdemirberkay/seedshot`

<details>
<summary>Use it as a standalone skill, without the plugin</summary>

Copy `skills/seedshot` to `~/.claude/skills/seedshot`. It is then available in every project as `/seedshot`.
</details>

## Use

Open your app's project in Claude Code and ask:

> Prepare App Store and Play Store screenshots for this app.

Or run it directly, optionally with overrides:

```
/seedshot:seedshot
/seedshot:seedshot ios only, en-US and de-DE, skip dark
```

Seedshot asks you exactly once, to approve the plan (screens, devices, languages, output folder). Then it works on its own and reports back with the results.

## What you get

```
~/Desktop/seedshot/<App>/
├── index.html                      ← contact sheet: every screen × language × appearance
├── ios/
│   ├── phone/<locale>/<light|dark>/01-home.png …    (1206×2622, iPhone 6.3")
│   └── tablet/<locale>/<light|dark>/01-home.png …   (2064×2752, iPad 13")
└── android/
    ├── phone/<locale>/<light|dark>/01-home.png …    (1080×1920)
    └── tablet/<locale>/<light|dark>/01-home.png …   (1440×2560)
```

Each leaf folder is one upload set, in store order.

## Store-correct defaults

| | Device | Size | Why |
|---|---|---|---|
| iOS phone | iPhone 17 Pro / 16 Pro | 1206×2622 | The one iPhone size App Store Connect requires |
| iOS tablet | iPad Pro 13-inch | 2064×2752 | Required when the app runs on iPad; Apple scales it down for 11" |
| Android phone | Dedicated AVD | 1080×1920 | Play rejects images longer than 2:1 (most Pixel emulators are 20:9); 9:16 is what featuring requires |
| Android tablet | Dedicated AVD | 1440×2560 | 9:16 per Play's large-screen guidance; 720 dp wide, so tablet layouts are used |

Both stores reject alpha channels. The simulator's own PNGs have one; Seedshot's don't. See [store-specs.md](skills/seedshot/references/store-specs.md) for the full rules and sources.

## Seedshot mode is safe to keep

The module Seedshot adds to your project only runs when **both**:

1. the app was built with the seedshot flag (a Swift compilation condition, a Gradle property, a `--dart-define`, `EXPO_PUBLIC_SEEDSHOT`), and
2. it was launched with a `SEEDSHOT_SCREEN` parameter.

Store builds have neither. The module lives in one folder with a few one-line hooks, and every touched file is listed in the final report. Keep it, and next release's screenshots are a single command. Seedshot never commits, never calls your real backend and never touches real accounts.

## What it runs and changes

- **Runs:** `xcrun simctl`, Android `emulator` and `adb`, your project's own build command (`xcodebuild`, Gradle, `flutter`, `expo` …) and its bundled Python scripts.
- **Creates:** dedicated "Seedshot …" simulators and `Seedshot_Phone` / `Seedshot_Tablet` emulators. `ios.py cleanup --delete` and `android.py cleanup --delete` remove them.
- **Changes in your project:** the seedshot module, its hooks and `seedshot.config.json`. Nothing is committed.
- **Writes:** screenshots to `~/Desktop/seedshot/<App>/`, or the folder you choose.
- **Network:** Seedshot sends no data anywhere. Network access happens only through your project's build tools (CocoaPods, Gradle, npm …), and through SDK downloads it asks you about first.

## Supported stacks

Swift (SwiftUI / UIKit) · Kotlin (Jetpack Compose / Views) · Flutter · React Native · Expo

## Requirements

- **Claude Code on your own machine:** the terminal, the desktop app or an IDE extension. Seedshot drives local simulators, so it doesn't work in claude.ai chat or in cloud sessions.
- **iOS:** macOS with Xcode and at least one iOS simulator runtime
- **Android:** Android SDK with the emulator and a system image (API 33+ recommended, for per-app locales)
- **Python 3:** the helper scripts use only the standard library; Pillow is optional

Check your setup:

```bash
python3 skills/seedshot/scripts/ios.py doctor
python3 skills/seedshot/scripts/android.py doctor
```

## The helper scripts

They're usable on their own too. Run any of them with `--help`.

| Script | What it does |
|---|---|
| `ios.py` | Dedicated "Seedshot …" simulators, 9:41 status bar, appearance, locale-aware launch, settled alpha-free screenshots |
| `android.py` | Store-safe AVDs, SystemUI demo mode, per-app locale, dark mode, settled alpha-free screenshots |
| `verify.py` | App Store / Google Play size, alpha, count and completeness checks. `--fix` strips alpha, `--sheet` writes a one-page HTML overview, `--seed <dir>` checks that per-locale seed files share one structure |

`pngkit.py` is a small shared helper the others use to write alpha-free PNGs.

## License

[MIT](LICENSE)
