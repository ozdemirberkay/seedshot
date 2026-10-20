---
name: seed
description: Prepare a mobile app for store screenshots without capturing them. Writes realistic demo data that tells one story, natively localized per language, and adds an isolated, release-safe "seedshot mode" to the project that injects that data at the data layer, unlocks every pro feature, signs in (a fake session or the user's demo account) and opens any screen directly from a launch parameter. Every change is tracked, so a capture run takes it all back out and leaves the project exactly as it was. Use this when the user wants demo or seed data for screenshots, a screenshot or demo mode in the app, plans to capture with their own tools (fastlane snapshot, by hand), or needs seed data updated for a new screen or language. Also use it to take seedshot mode, or seedshot code an older version left behind, out of the project. Works with Swift/SwiftUI/UIKit, Kotlin/Jetpack Compose, Flutter, React Native and Expo projects. For the whole flow including capture, use seedshot:all.
license: MIT
compatibility: Requires a local mobile project. The optional smoke test needs an iOS simulator (macOS with Xcode) or an Android emulator. Python 3 for helper scripts.
allowed-tools:
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
  - Bash(xcrun simctl *)
  - Bash(adb *)
---

# Seedshot: seed data and seedshot mode

The plugin folder is `${CLAUDE_PLUGIN_ROOT}`. The files you read from it below aren't expanded: where their paths say `CLAUDE_PLUGIN_ROOT`, use this folder. The shell doesn't set that variable.

The goal: the app can render any listed screen, in any of its languages, full of believable data, on demand, and a store build can never show any of it.

## Before you start

If `.seedshot/config.json` exists, load it and use its `locales`, `screens`, `seed` and `access` fields. Otherwise, follow `${CLAUDE_PLUGIN_ROOT}/references/plan.md` to discover the project and agree on a plan, limited to what this skill needs: stack, locales, the ordered screen list with what each shows, the one-line story, access (pro, sign-in), and where the module and data will live. When `seedshot:all` sent you here, the plan is already approved, so go straight on.

## 0. Track every change

The user must always be able to tell Seedshot's changes from their own, and get the project back exactly as it was. So every change goes through `${CLAUDE_PLUGIN_ROOT}/scripts/session.py`:

- **Before the first change**, run `session.py start` (planning already did if it ran). It snapshots the project inside git's own object store (or a private copy outside git) without touching the user's files, index or branches.
- **Before you change or create anything, register it**: `session.py track <file-or-folder>…`. Register a new folder once (`track lib/seedshot`), not each file in it. This covers everything you touch: the module, hooks, seed data, project and build files (`project.pbxproj`, `build.gradle`, `pubspec.yaml`, `package.json`) and real bug fixes. A change you didn't register counts as the user's and is never undone.
- **Reuse the last run.** If `.seedshot/seedshot.patch` exists, run `session.py apply` instead of writing seedshot mode from scratch. It starts the session if needed, puts last release's module, hooks and seed data back, and registers them. Redo by hand only the files it lists as not applying, then update for new screens and locales.
- **Stay out of git-ignored files** (`.env`, `local.properties`): the snapshot can't see them. Pass build flags on the command line instead. Build output goes outside the project or into folders it already ignores, so nothing new shows up in `git status`.
- `session.py status` lists Seedshot's changes and, separately, everything else that changed since start.

**At the end of the run**, the skill that captures takes it all back out: `session.py restore --keep <each real bug fix file>`. It saves Seedshot's changes to `.seedshot/seedshot.patch`, puts every registered file back exactly as it was at start (the user's uncommitted work in those files included), deletes the folders Seedshot created, and ends the session. Other changes are listed and left alone. Act on what it prints:
- **Not restored, because a commit changed them too:** remove Seedshot's part from those files by hand. The patch shows what it was.
- **Kept file still contains seedshot code:** remove that part by hand.
- **Dependency files restored:** run the project's install step (`pod install`, `npm install`, `flutter pub get` …), so the next build matches the restored files.

If the user asks to take seedshot mode out and `status` says there's no session, the code is from an older Seedshot: remove it as "Existing seedshot mode" in `${CLAUDE_PLUGIN_ROOT}/references/plan.md` describes.

## 1. Seed: build the dataset

Read `${CLAUDE_PLUGIN_ROOT}/references/seed-data.md` before writing any data. The essentials:

- **One story, told natively in each language.** Every locale gets the same structure: same number of items, same order, same states, same chart shape, same magnitudes. The content is culturally native: local names, places, currency, units, date and number formats, idioms. Write it the way a native speaker would. Don't translate it word for word.
- **Show the app at its best.** Populated, varied, plausible and aspirational. No lorem ipsum, "Test", "John Doe", `foo@bar.com`, zero balances or empty lists, unless an empty state is deliberately one of the shots.
- **Fill the tablet.** Make sure there are enough items that the 13" iPad and the 10" tablet layouts don't look sparse.
- **Fresh dates.** Generate dates relative to launch time, so nothing looks stale. Keep visible times consistent with the 9:41 status bar.
- **Safe content.** No real people, real brands or trademarks, and no real personal data. For images, prefer assets already in the project, then generated neutral art (gradients, initials avatars, system icons). Never download images you don't have rights to. If the app's look depends on photos (recipes, travel, real estate), ask the user for a set.
- **Seed data lives in data files.** Use one JSON file per locale with identical structure, so parity is checkable: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py --seed <seed-data-dir>`. It compares every locale's structure with the base locale's, and flags long text left identical (probably untranslated).

## 2. Seedshot mode

Seedshot mode is a small, self-contained addition to the app. It makes any listed screen render with seed data, deterministically, on demand. `${CLAUDE_PLUGIN_ROOT}/references/seedshot-mode.md` has concrete recipes per stack; read the section for this project's stack, and "Full access and sign-in". The contract:

- **Two locks.** The code is active only when (1) the build was made with the seedshot build flag (a Swift compilation condition, a Gradle property, a `--dart-define`, `EXPO_PUBLIC_SEEDSHOT`) **and** (2) the app was launched with a seedshot launch parameter. A store build has neither, so it can never show demo data, even if one is made while seedshot mode is in the code.
- **Launch parameters** (iOS launch arguments/environment, Android intent extras):
  - `SEEDSHOT_SCREEN`: the screen id to open.
  - `SEEDSHOT_LOCALE`: e.g. `tr-TR`. Used to pick the seed file, and to set the in-app language if the app has its own language setting.
  - Appearance comes from the OS, which the capture scripts set.
- **Inject data at the data boundary, not in the views.** Swap a repository/service, override a provider, stub the HTTP layer (URLProtocol, OkHttp interceptor, Dio interceptor, fetch/axios adapter), or pre-fill an in-memory database. UI code stays untouched, so the screenshots show the real UI.
- **Full access.** Show the app the way a paying user on its top tier sees it: every pro/premium feature unlocked, with no lock icons, "PRO" upsell tags, trial banners, usage limits or ads. Answer "active" at the app's own entitlement check (its `isPro`, subscription service or entitlement store), and don't start the purchase SDK in seedshot mode. Never make a real or sandbox purchase. Show the free tier only if the user asked for it, and the paywall only if it's on the shot list.
- **Signed in.** With `access.signIn` = `fake` (the default), use a fake session: a seed user and token in memory, never in the keychain or real storage, and no call to the real backend. With `account`, sign in to the user's demo account through the app's real sign-in code, using the `SEEDSHOT_LOGIN_*` launch parameters that `launch --login` passes from `.seedshot/login.json`. Only read with that account: never create, edit or delete anything in it. Never write the credentials into code, seed data, the config, a command line or chat.
- **Clear the path to the screen.**
  - Skip onboarding, rating prompts, permission prompts, ads, analytics, crash-report dialogs and "what's new" sheets.
  - Open the requested screen in the requested state directly (tab selected, detail item chosen, sheet presented).
  - Hide debug banners and dev overlays. Stop or settle animations, especially looping ones.
- **Self-contained.** Put everything in one folder (e.g. `Seedshot/`, `lib/seedshot/`, `src/seedshot/`, a `seedshot` source set), plus a few one-line hooks at the app entry and the data boundary. Never call real backends, except to sign in to and read from the demo account.
- **Don't hide real bugs.** Missing translations, truncated labels and broken dark-mode colors are bugs real users see too. Don't paper over them inside seedshot mode. If the fix is small and clearly correct (e.g. adding a missing string to the localization file), make it in the app, register the file like any other, and list it in the report: it stays when Seedshot's changes come out (`restore --keep <file>`). Keep such fixes out of files that also hold seedshot hooks. Otherwise report the bug to the user.

## When run on its own

**Smoke test.** Build once with the seedshot flag, open one screen in one locale and look at it: `ios.py launch <udid> <bundle-id> --locale <locale> --screen <id>` (or `android.py launch`), then `shot` to a scratch path. The script usage is in `${CLAUDE_PLUGIN_ROOT}/skills/capture/SKILL.md`. Fix what's wrong before you report. Skip this if no simulator or emulator is available, and say so.

Seedshot mode stays in the project after this skill alone, since the user wants to use it. Don't restore. The next `/seedshot:capture` or `/seedshot:all` takes it out at its end, or the user can ask for it sooner.

**Report.** Keep it short:
- the seed data files and the story they tell
- Seedshot's changes, from `session.py status`: the module, its hooks, and any real bugs you fixed
- how to open a screen by hand: the build flag, and the `SEEDSHOT_SCREEN` / `SEEDSHOT_LOCALE` (and `SEEDSHOT_LOGIN_*`) launch parameters
- next step: `/seedshot:capture` takes the screenshots with this mode, then takes it out again, puts every file back as it was, and saves it in `.seedshot/` for next time.

Never commit. Leave changes in the working tree for the user to review.
