---
name: all
description: Capture App Store and Google Play screenshots of a mobile app from start to finish, filled with realistic demo data that is consistent across devices and natively localized per language. Covers every important screen, light and dark mode, every language the app supports, iPhone/iPad simulators and Android phone/tablet emulators, all at store-accepted sizes. Plans the set with the user once, writes seed data, builds an isolated, release-safe "seedshot mode" in the project that injects it, unlocks every pro feature, signs in and opens each screen directly, then captures, verifies and organizes the images, and finally puts every file it touched back exactly as it was. Use this whenever the user wants store screenshots, App Store / Play Store listing images, screenshots in several languages or in dark mode, needs to refresh screenshots for a new release, or asks to "take screenshots of the app" for publishing. Works with Swift/SwiftUI/UIKit, Kotlin/Jetpack Compose, Flutter, React Native and Expo projects. For one step alone, use seedshot:seed, seedshot:capture or seedshot:verify.
license: MIT
compatibility: Requires a local mobile project. iOS capture needs macOS with Xcode (xcrun simctl). Android capture needs the Android SDK (adb, emulator, avdmanager). Python 3 for helper scripts; Pillow is optional (only for fixing alpha channels).
allowed-tools:
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ios.py *)
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/android.py *)
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session.py *)
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py *)
  - Bash(xcrun simctl *)
  - Bash(adb *)
---

# Seedshot: the whole flow

The plugin folder is `${CLAUDE_PLUGIN_ROOT}`. The files you read from it below aren't expanded: where their paths say `CLAUDE_PLUGIN_ROOT`, use this folder. The shell doesn't set that variable.

Store screenshots are an app's shop window. The capture command is the easy part. What makes them good is **what's on screen**: a populated, believable app, written natively in each language, telling the same story on every device. Your job is to produce that set with no mistakes. One untranslated label, one loading spinner or one "John Doe" in a store listing is exactly the failure Seedshot exists to prevent.

This skill runs the other three Seedshot skills in order, then puts the project back. Each step lives in its own file, so read each one when you reach it and follow it fully:

| Step | Read | What it does |
|---|---|---|
| 1. Discover & plan | `${CLAUDE_PLUGIN_ROOT}/references/plan.md` | Reads the project, sets the capture matrix from the arguments (everything by default), gets the plan approved once, starts change tracking, saves `.seedshot/config.json` |
| 2. Seed | `${CLAUDE_PLUGIN_ROOT}/skills/seed/SKILL.md` | Writes the localized demo data and the release-safe seedshot mode, registering every file it touches |
| 3. Capture | `${CLAUDE_PLUGIN_ROOT}/skills/capture/SKILL.md` | Pilot shot, then the full matrix on dedicated simulators and emulators |
| 4. Verify | `${CLAUDE_PLUGIN_ROOT}/skills/verify/SKILL.md` | Store checks, a look at every image, re-captures, contact sheet |
| 5. Clean up | `${CLAUDE_PLUGIN_ROOT}/skills/capture/SKILL.md`, "Clean up" | `session.py restore` takes seedshot mode out and puts every file back as it was, keeping real bug fixes. `ios.py cleanup` / `android.py cleanup` shut down the simulators and emulators |

If the user passed arguments (e.g. `ios only`, `tr en`, `skip dark`, `screens: home, stats`), treat them as overrides to the defaults and the saved config.

## One checkpoint, for everything

In step 1, plan the **whole** matrix at once: devices, locales, appearances, screens, the seed story, access (pro, sign-in) and the output folder. That approval is the only planned interruption. Steps 2–4 then start from the saved config, so skip their own "before you start" planning and work autonomously. Only stop for genuine blockers.

Each step file ends with a short report for when it runs on its own. Here, don't report between steps. Collect what each step did and give one final report.

Step 5 always runs, so the user never has to call anything else. Skip only `restore`, and only if the user asked to keep seedshot mode in the project; the next capture takes it out.

## Final report

Keep it short:
- the output path and the contact sheet
- image counts per platform/device/locale/appearance
- the project: Seedshot's changes were taken out and every file is back as it was; the real bugs you fixed stay (list them); other files that changed during the run were left alone (list them, they're the user's or a build's)
- `.seedshot/`: the plan and the saved seedshot mode, kept for the next release. Git ignores the folder.
- how to re-run next release: `/seedshot:all` again, or `/seedshot:capture` if only the app's look changed; both put the saved seedshot mode back and take it out again
- anything the user must do in the store consoles (e.g. "Play: tablet listing needs at least 4 images, you have 5 ✓"). If the images show pro features, the App Store description must say they need a subscription (App Review Guideline 2.3.2).

Never commit. If the project is a git repo, end with a `git status` summary: it should show only the user's own changes and the kept fixes. If `.seedshot/` shows up, its `.gitignore` is missing or was edited: say so.
