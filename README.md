# Seedshot

**Store-ready App Store and Google Play screenshots with realistic, localized demo data, captured by Claude Code.**

The capture command is the easy part of store screenshots. The hard part is what's on screen: a populated, believable app, written natively in every language, telling the same story on every device, in light and dark mode, at exactly the sizes the stores accept.

Seedshot is a [Claude Code](https://code.claude.com) plugin that does all of it inside your project:

- **Reads your app.** It detects the stack, languages, dark-mode and tablet support and the navigation, then proposes the screens worth showing, in store order.
- **Writes seed data.** One story told natively in each language: same structure everywhere, local names, prices, units and formats.
- **Adds a release-safe *seedshot mode*.** It's double-locked, behind a build flag *and* a launch parameter. It injects the seed data at your data layer, unlocks every pro feature, signs in (a fake session, or your demo account) and opens any screen directly.
- **Captures the full matrix.** Platform × device × language × appearance × screen, on dedicated simulators and emulators, with a clean status bar.
- **Verifies everything.** A script checks store sizes, alpha channels, counts and missing images. Claude then looks at every image for untranslated text, truncation, spinners or stray dialogs.
- **Delivers** ready-to-upload folders and a one-page contact sheet.
- **Leaves your project as it found it.** Every file Seedshot touched goes back exactly as it was. Your own changes, even uncommitted ones, stay.

## Install

In Claude Code:

```bash
claude plugin marketplace add ozdemirberkay/seedshot
claude plugin install seedshot@seedshot
```

Or, from inside a session: `/plugin install seedshot --marketplace ozdemirberkay/seedshot`

## Use

Seedshot has four skills. Run the whole flow with one command, or only the step you need:

| Command | What it does | Use it when |
|---|---|---|
| `/seedshot:all` | Everything below, in order: plan → seed → capture → verify, then puts your project back as it was | You want store screenshots. This is the only command you need |
| `/seedshot:seed` | Writes localized seed data and adds seedshot mode, without capturing, and leaves it in until the next capture | You want demo data in the app, or capture with your own tools (fastlane, by hand) |
| `/seedshot:capture` | Captures the matrix on dedicated simulators and emulators | A new release: it puts last release's seedshot mode back and takes it out again. Or you'll navigate the app yourself |
| `/seedshot:verify` | Store checks, an image-by-image review, a contact sheet | You have screenshots, from Seedshot or anywhere else, and want them checked before upload |

You don't have to type a command. Open your app's project in Claude Code and ask, and Claude picks the right skill:

> Prepare App Store and Play Store screenshots for this app.
>
> Are the screenshots in ~/Desktop/shots ready for the App Store?

Every command takes optional overrides:

```
/seedshot:all ios only, en-US and de-DE, skip dark
/seedshot:capture screens: home, stats
/seedshot:verify ~/Desktop/shots
```

Seedshot asks you exactly once, to approve the plan (screens, devices, languages, pro access, sign-in, output folder), and saves it to `.seedshot/config.json`. Every skill reads that file, so the steps can run on different days and the next release needs no questions at all. After the approval it works on its own and reports back with the results.

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

Both stores reject alpha channels. The simulator's own PNGs have one; Seedshot's don't. See [store-specs.md](references/store-specs.md) for the full rules and sources.

## Your project, exactly as it was

Seedshot has to change your code to show seed data, but only for the length of a run:

1. **Before the first change**, `session.py start` snapshots the project inside git's own object store. Your files, index, branches and stash aren't touched. (Outside git, a private copy under `~/.cache/seedshot` is used.)
2. **Every file Seedshot touches is registered first**: the module, its hooks, seed data, project and build files.
3. **When the run ends**, `session.py restore` puts each registered file back exactly as it was, uncommitted work included, and deletes the folders Seedshot created. Changes that weren't Seedshot's, yours or a build's, are listed and left alone. Real bug fixes it made along the way (a missing translation) stay, and are listed.

`git status` then shows your own work, the kept fixes and one folder, `.seedshot/`:

| File | What it is | Commit it? |
|---|---|---|
| `config.json` | The approved plan | Yes, so the team and the next release reuse it |
| `seedshot.patch` | Seedshot mode and seed data, saved when they were taken out | Yes, so the next release puts them back in one step |
| `login.json` | Your demo account, if the app needs a real sign-in | Never. `.seedshot/.gitignore` keeps it out |

While seedshot mode is in the code, it's still double-locked. It only runs when **both** the app was built with the seedshot flag (a Swift compilation condition, a Gradle property, a `--dart-define`, `EXPO_PUBLIC_SEEDSHOT`) **and** it was launched with a `SEEDSHOT_SCREEN` parameter. Store builds have neither. `session.py status` shows what's Seedshot's at any time. Seedshot never commits.

## Pro features and sign-in

- **Full access.** If the app has a paid tier, the screenshots show it the way a paying user sees it: every pro feature unlocked, no locks or upgrade banners. Seedshot answers "active" at your app's own entitlement check and never makes a real or sandbox purchase. Ask for the free tier instead if you prefer. If the images show pro features, App Review Guideline 2.3.2 asks the description to say they need a purchase.
- **Sign-in.** By default Seedshot fakes a signed-in session in memory, so nothing reaches your backend. If your screens can't work without a real session (server-checked tokens, auth-gated images, remote config), it signs in to a demo account instead.

### Using a demo account

1. **Ask for it, or let Seedshot ask.** Say so in your request (`/seedshot:all sign in with my demo account`), or Seedshot proposes it in the plan when it finds your screens need a real session. The approved plan saves `"signIn": "account"` in `.seedshot/config.json`.
2. **Give it the account.** Use a dedicated demo account, like the one you give App Review. Never use a personal one. It must sign in without a one-time code (2FA, email link, SMS). Put it in `.seedshot/login.json` (any field names work):

   ```json
   { "email": "demo@example.com", "password": "…" }
   ```

   Or paste it in chat, and Claude writes the file for you without repeating the values. By the time Seedshot asks for the account, it has already added `login.json` to `.seedshot/.gitignore`. If you create the file before Seedshot asks, add that line yourself.
3. **Capture as usual.** Each launch passes the file's fields to the app as `SEEDSHOT_LOGIN_*` launch parameters (`email` becomes `SEEDSHOT_LOGIN_EMAIL`). Seedshot mode then signs in through your app's own sign-in code. The values never appear in commands, code, the config or the saved patch. The scripts refuse the file if git could commit it.
4. **Next release.** The config remembers the choice, so there's nothing to ask. `login.json` stays on your machine, so anyone else on the team who captures needs their own copy.

Seedshot only reads with that account: it never creates, edits or deletes anything in it. Screen content still comes from the seed data, so every language tells the same story. The real session only gets the app past the checks that need one. If you've filled the account with showcase data and want that shown instead, say so. That data won't be translated, so it looks the same in every language.

## What it runs and changes

- **Runs:** `xcrun simctl`, Android `emulator` and `adb`, your project's own build command (`xcodebuild`, Gradle, `flutter`, `expo` …) and its bundled Python scripts.
- **Creates:** dedicated "Seedshot …" simulators and `Seedshot_Phone` / `Seedshot_Tablet` emulators. `ios.py cleanup --delete` and `android.py cleanup --delete` remove them.
- **Changes in your project:** seedshot mode, only during a run; afterwards, only `.seedshot/` and any real bug fixes it lists. Nothing is committed.
- **Writes:** screenshots to `~/Desktop/seedshot/<App>/`, or the folder you choose. iOS build output goes to `~/Library/Developer/Xcode/DerivedData/Seedshot-<App>`.
- **Network:** Seedshot sends no data anywhere. Network access happens only through your project's build tools (CocoaPods, Gradle, npm …), SDK downloads it asks you about first, and, if you give it a demo account, your app signing in to your backend with it.

## Supported stacks

Swift (SwiftUI / UIKit) · Kotlin (Jetpack Compose / Views) · Flutter · React Native · Expo

## Requirements

- **Claude Code on your own machine:** the terminal, the desktop app or an IDE extension. Seedshot drives local simulators, so it doesn't work in claude.ai chat or in cloud sessions.
- **iOS:** macOS with Xcode and at least one iOS simulator runtime
- **Android:** Android SDK with the emulator and a system image (API 33+ recommended, for per-app locales)
- **Python 3 and git:** the helper scripts use only the standard library; Pillow is optional. git comes with Xcode's Command Line Tools.

Check your setup:

```bash
python3 scripts/ios.py doctor
python3 scripts/android.py doctor
```

## The helper scripts

They're usable on their own too. Run any of them with `--help`.

| Script | What it does |
|---|---|
| `ios.py` | Dedicated "Seedshot …" simulators, 9:41 status bar, appearance, locale-aware launch, settled alpha-free screenshots |
| `android.py` | Store-safe AVDs, SystemUI demo mode, per-app locale, dark mode, settled alpha-free screenshots |
| `verify.py` | App Store / Google Play size, alpha, count and completeness checks. `--fix` strips alpha, `--sheet` writes a one-page HTML overview, `--seed <dir>` checks that per-locale seed files share one structure |
| `session.py` | Tracks every change Seedshot makes to a project: `start`, `track`, `status`, `restore` (put it all back, save it as a patch), `apply` (put the patch back next release) |

`pngkit.py` is a small shared helper the others use to write alpha-free PNGs.

## Repository layout

```
skills/
  all/SKILL.md        the whole flow; runs the three below in order, then puts the project back
  seed/SKILL.md       seed data and seedshot mode
  capture/SKILL.md    simulators, emulators and screenshots
  verify/SKILL.md     store checks and visual review
references/           shared by every skill: planning, seed-data guide, per-stack recipes, store rules
scripts/              shared helper scripts (ios.py, android.py, verify.py, session.py, pngkit.py)
```

## License

[MIT](LICENSE)
