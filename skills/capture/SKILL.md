---
name: capture
description: Capture App Store and Google Play screenshots on dedicated iOS simulators and Android emulators, at store-accepted sizes, with a clean 9:41 status bar, alpha-free PNGs, in every language and in light and dark mode, saved as ready-to-upload folders in store order. Uses the project's seedshot mode when it has one (putting last release's back from .seedshot/ and taking it out again afterwards), so re-capturing for a new release is fully automatic; otherwise it captures whatever the app shows while the user navigates. Use this when the app is already prepared and the user wants screenshots taken or re-taken, or wants store-size captures of the current app. For a project with no demo data yet, use seedshot:all.
license: MIT
compatibility: Requires a local mobile project. iOS capture needs macOS with Xcode (xcrun simctl). Android capture needs the Android SDK (adb, emulator, avdmanager). Python 3 for helper scripts; Pillow is optional (only for fixing alpha channels).
allowed-tools:
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
  - Bash(xcrun simctl *)
  - Bash(adb *)
---

# Seedshot: capture

The plugin folder is `${CLAUDE_PLUGIN_ROOT}`. The files you read from it below aren't expanded: where their paths say `CLAUDE_PLUGIN_ROOT`, use this folder. The shell doesn't set that variable.

## Before you start

If `.seedshot/config.json` exists, load it, apply any arguments the user passed (e.g. `ios only`, `tr-TR en-US`, `skip dark`, `screens: home, stats`) and show a one-line summary of what you'll capture. Otherwise, follow `${CLAUDE_PLUGIN_ROOT}/references/plan.md` to discover the project and agree on the capture matrix: platforms, devices, locales, appearances, screens, output folder and build command. When `seedshot:all` sent you here, the plan is already approved, so go straight on.

Run `ios.py doctor` / `android.py doctor` first. If something is missing, tell the user exactly what to install, and ask before any large download.

## How each screen is reached

- **With seedshot mode**: `launch --screen <id>` opens each screen with seed data, and the whole matrix runs on its own. Add `--login` when `access.signIn` is `account`.
  - If the module is in the code (`/seedshot:seed` left it there), use it as it is.
  - If it isn't, but `.seedshot/seedshot.patch` exists (a previous run saved it), run `session.py apply`. It starts a session and puts the module, hooks and seed data back. Redo by hand any file it lists as not applying, following `${CLAUDE_PLUGIN_ROOT}/skills/seed/SKILL.md`, and register what you touch with `session.py track`.
- **With the app's own demo mode**: if the app already has launch arguments for demo data or screens, pass them with `launch --param KEY=VALUE`.
- **Without either**: launch without `--screen`, boot with the window visible (`ios.py boot --show`, or `android.py boot` without `--headless`), and let the user put each screen on display. Capture on their word, one screen at a time. Say upfront that what's on screen is then up to them, and that this is a lot of manual work for a full matrix, so suggest fewer locales or devices, or `/seedshot:seed` first.

## The scripts

Use the bundled scripts. They wrap the fiddly parts, so you don't re-derive them each time. Run each with `--help` for usage.

- `ios.py`: `doctor`, `device` (finds or creates a dedicated "Seedshot …" simulator for a device class), `boot`, `statusbar` (9:41, full battery and signal), `appearance`, `install`, `launch` (locale + seedshot parameters), `shot` (waits until the screen stops changing, then saves an alpha-free PNG), `cleanup`.
- `android.py`: `doctor`, `avd` (creates a dedicated AVD at a store-safe resolution), `boot`, `demo` (clean status bar via SystemUI demo mode), `appearance`, `install` (grants runtime permissions), `launch` (sets the per-app locale, then starts with seedshot extras), `shot`, `cleanup`.
- `session.py`: `start`, `track`, `status`, `restore`, `apply`. Tracks every change Seedshot makes to the project, so it can all be undone.

```bash
S=${CLAUDE_PLUGIN_ROOT}/scripts
UDID=$(python3 $S/ios.py device phone)        # or: tablet
python3 $S/ios.py boot $UDID && python3 $S/ios.py statusbar $UDID && python3 $S/ios.py install $UDID <App.app>
python3 $S/ios.py appearance $UDID dark
python3 $S/ios.py launch $UDID <bundle-id> --locale tr-TR --screen stats   # + --login for a demo account
python3 $S/ios.py shot $UDID <output>/ios/phone/tr-TR/dark/02-stats.png

AVD=$(python3 $S/android.py avd phone)        # or: tablet
SERIAL=$(python3 $S/android.py boot $AVD)     # first boot of a new AVD takes 1–3 minutes
python3 $S/android.py demo $SERIAL && python3 $S/android.py install $SERIAL <app.apk>
# then appearance / launch / shot exactly as on iOS, with $SERIAL and the package name
```

## Capture

Build once per platform, with the seedshot flag if the app has seedshot mode. Every locale's seed data is bundled, so locales and appearances switch at launch with no rebuild. Then:

1. **Pilot first.** Capture one screen on one device in one locale. Open the image and inspect it closely. Most problems surface here: wrong data, a leftover dialog, the debug banner, the wrong language, a spinner. Fixing them now costs one rebuild instead of a hundred bad images.
2. **Full matrix.** Loop platform → device → locale → appearance → screen, with a fresh launch for every shot (`launch` terminates the previous instance). Name files:

   ```
   <output>/<ios|android>/<phone|tablet>/<locale>/<light|dark>/<NN>-<screen-id>.png
   ```

   `NN` is the store order from the plan (`01`, `02`, …). Each folder is then a ready-to-upload set in the right order.
3. **Don't overwrite earlier runs.** If the output folder already has images, move it aside to `<output>.bak-<YYYYMMDD-HHMM>` instead of deleting it.

If a capture step misbehaves (locale not applied, screen never settles, landscape-only app, install errors), see "Capture troubleshooting" at the end of `${CLAUDE_PLUGIN_ROOT}/references/seedshot-mode.md`.

## Clean up

- Run `ios.py cleanup` / `android.py cleanup`. They clear status-bar overrides and shut down the dedicated simulators and emulators.
- If a Seedshot session is active (`session.py status`), take seedshot mode out again with `session.py restore`, as "At the end of the run" in `${CLAUDE_PLUGIN_ROOT}/skills/seed/SKILL.md` describes. `.seedshot/seedshot.patch` keeps it for next time.

When `seedshot:all` sent you here, clean up after the verify step instead, since it may re-capture.

## When run on its own

Run the automated store checks: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <output> --fix --sheet`. Fix every error, then open the contact sheet (`<output>/index.html`) for the user.

**Report.** Keep it short: the output path and the contact sheet, image counts per platform/device/locale/appearance, any problems you saw, and what `restore` put back. Suggest `/seedshot:verify` for the image-by-image review before upload.
