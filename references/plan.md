# Discover & plan

Every Seedshot skill starts here. Read the project, agree on a plan with the user once, and save it to `.seedshot/config.json`, so every skill and every later release reuses it.

Plan only what the running skill needs. `seed` needs the stack, locales, screens and story. `capture` needs the full matrix and the build. `verify` needs only the output folder. Leave the other fields for the skill that fills them. If the user passed arguments (e.g. `ios only`, `tr en`, `skip dark`, `screens: home, stats`), treat them as overrides to the defaults and the saved config.

## The capture matrix

Every screenshot is one cell of: **platform × device class × locale × appearance × screen**.

| Dimension | Default | Source |
|---|---|---|
| Platforms | Every platform the project builds for | Detected (`ios/`, `android/`, `*.xcodeproj`, Gradle app module) |
| Devices | iOS: iPhone 6.3" (required slot) + iPad 13" (required if the app runs on iPad). Android: 1080×1920 phone + 1440×2560 tablet | See `store-specs.md` |
| Locales | Every language the app ships translations for | Detected from localization files |
| Appearances | `light` and `dark`, or only `light` if the app has no dark theme | Detected |
| Screens | 4–8 screens that sell the app, in store order | Proposed by you, approved by the user |
| Output | `~/Desktop/seedshot/<AppName>/` | Config |

The default devices are chosen for store acceptance, not personal preference. Apple requires the 6.3" iPhone and 13" iPad sizes, and scales those down for smaller devices. Google Play rejects phone images longer than 2:1 (most modern Pixel emulators are 20:9), and wants 9:16 for tablets and featuring. Don't swap devices casually. If the user asks for a different one, say what that means for the store slot.

## The .seedshot folder

Everything Seedshot keeps in a project lives in one folder at its root, so the user can always tell Seedshot's files from their own:

| File | What it is | Commit it? |
|---|---|---|
| `.seedshot/config.json` | The approved plan | Yes, so the team and the next release reuse it |
| `.seedshot/seedshot.patch` | Seedshot mode and the seed data, saved when they're removed from the code after a run | Yes, so the next release puts them back in one step |
| `.seedshot/login.json` | The demo account, only if the app needs a real sign-in | Never. `.seedshot/.gitignore` keeps it out of git |

If the config exists:
- load it
- update anything that changed in the project (new screens, new locales)
- show a short summary instead of the full planning conversation.

An older Seedshot kept `seedshot.config.json` at the project root. Move it to `.seedshot/config.json`.

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
  "access": { "pro": true, "signIn": "fake" },
  "seed": { "module": "lib/seedshot/", "data": "assets/seedshot/", "story": "A freelance designer mid-month, savings on track." }
}
```

## Discover

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
  - Also find where onboarding, paywalls, permission prompts and rating prompts are triggered.
- **Paid tier**: a pro/premium plan, subscription or in-app purchase (RevenueCat, StoreKit, Play Billing, Adapty, Superwall, Qonversion, or the app's own `isPro`), what it unlocks, and the one place the UI checks it.
- **Sign-in**: whether the screens need a signed-in user, the auth provider, and whether the screens can be fed without the backend (a fake session works) or need a real session the app can't fake (server-checked tokens, auth-gated images or config).
- **Existing seedshot mode**: check for a previous run: `.seedshot/` (config, saved patch), or seedshot code an older Seedshot left in the project. Reuse it rather than starting over. Old code that's already in the project counts as the user's, so this run's restore would leave it. To find it, search the source folders, skipping build output, dependencies and `.seedshot/` (`grep -rIli seedshot`): a module folder, seed data files, one-line hooks, build-flag lines (`SEEDSHOT` compilation conditions, a `buildConfigField`, a `--dart-define`), project-file entries. List each file and change in the plan. On approval, before `session.py start`: copy the module and seed data to a scratch folder, remove the old code, check that the app still builds, then build seedshot mode again from that copy.
- **Toolchain** (only when capturing): run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ios.py doctor` and/or `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/android.py doctor`. If something is missing (no simulator runtime, no Android system image), tell the user exactly what to install. Downloads are large, so ask before starting one.

## Plan (the one checkpoint)

Present a compact plan and wait for the user's approval. Include the parts the running skill needs:

- stack, platforms, the device for each class (with pixel size and the store slot it fills)
- locales, and appearances
- the **ordered screen list**, with one line each on what it will show. Example: "02 · Stats: weekly chart trending up, 3 insight cards". The first three images matter most, because stores show them in search results. Lead with the app's core value, not with settings, login or onboarding.
- output path, and total image count (e.g. 6 screens × 2 locales × 2 appearances × 4 devices = 96)
- **access**: the app as a paying user with every pro feature unlocked (the default when it has a paid tier, unless the user wants the free tier shown), and how it's signed in:
  - `fake` (default): a fake signed-in session, nothing touches the backend
  - `account`: the user's demo account, when the screens can't work without a real session. Before you ask for it, make sure `.seedshot/.gitignore` lists `login.json` (create the file if it's missing), so the account can never be committed, not even before approval. `session.py start` keeps an existing `.gitignore`. Then ask the user to put the account in `.seedshot/login.json` themselves, e.g. `{"email": "…", "password": "…"}` (any field names work). If they paste it in chat instead, write that file for them and never repeat the values. It should be a dedicated demo account, like the one given to App Review, never a personal one, and one that signs in without a one-time code.
- what you'll add to the project (seedshot mode), and that it comes out again when the run ends: every file Seedshot touched goes back exactly as it was, and the user's own changes are left alone.

On approval, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py start`, then write `.seedshot/config.json`. `start` snapshots the project so everything Seedshot changes can be undone, and creates `.seedshot/` with its `.gitignore`. This is the only planned interruption. After it, work autonomously and only stop for genuine blockers.
