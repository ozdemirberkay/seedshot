---
name: verify
description: Check App Store and Google Play screenshots before upload. Runs store checks (pixel sizes per store slot, alpha channels, images per set, screens missing from any language or appearance), then reviews every image for untranslated text, mixed languages, truncation, spinners, dialogs, debug banners and dark-mode problems, and writes a one-page HTML contact sheet. Use this when the user wants existing screenshots checked, reviewed or validated against store rules, or asks whether a screenshot set is ready to upload.
license: MIT
compatibility: Python 3 for the checks; Pillow is optional (only for fixing alpha channels). Re-capturing needs an iOS simulator (macOS with Xcode) or an Android emulator.
allowed-tools:
  - Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
  - Bash(xcrun simctl *)
  - Bash(adb *)
---

# Seedshot: verify

The plugin folder is `${CLAUDE_PLUGIN_ROOT}`. The files you read from it below aren't expanded: where their paths say `CLAUDE_PLUGIN_ROOT`, use this folder. The shell doesn't set that variable.

## Before you start

Find the screenshot folder: the path the user gave, else `output` in `.seedshot/config.json`, else ask.

The checks expect Seedshot's layout:

```
<output>/<ios|android>/<phone|tablet>/<locale>/<light|dark>/<NN>-<screen-id>.png
```

If the images are in another layout (fastlane's `<locale>/` folders, a hand-made set), mirror them into this layout as copies in a scratch folder and check those. Never move, rename or modify the user's own files. Say which copy `--fix` changed, so the user knows which files to upload.

## Automated checks

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py <output>`. It checks:
- pixel sizes against each store slot
- alpha channels (both stores reject them)
- per-folder counts (Apple ≤ 10, Play ≤ 8, Play tablets ≥ 4 recommended)
- that every locale/appearance folder has the same screens.

Add `--fix` to strip alpha channels. Fix every error before delivering. `${CLAUDE_PLUGIN_ROOT}/references/store-specs.md` has the rules and their sources.

## Visual review: look at every image

It is tedious, and it is the step that makes Seedshot worth using. For each image, check:
- **Language**: everything is in the folder's language. No mixed languages, no raw keys like `home.title`, and dates/numbers/currency are formatted for that locale.
- **Appearance**: matches the folder (`dark` really is dark), and no unreadable text or invisible icons.
- **Completeness**: no spinners, skeletons, placeholder images, empty states, half-finished animations, keyboards, dialogs, toasts or debug banners.
- **Access**: signed in, and nothing locked: no lock icons, "PRO" tags on features, upgrade banners, trial countdowns or ads. Only the paywall shot, or a free-tier set the user asked for, may show them.
- **Status bar**: clean (9:41, full battery and signal).
- **Layout**: no truncation, overflow or clipped text, which is common in German, Turkish, Finnish and Russian.
- **Consistency**: the same story as the other locales and devices.

If the project has seedshot mode (in the code, or saved in `.seedshot/seedshot.patch`), re-capture anything that fails, following `${CLAUDE_PLUGIN_ROOT}/skills/capture/SKILL.md` for just those cells, then re-run `verify.py`. If it doesn't, list each failing image and what's wrong with it.

## Contact sheet

Run the final check with `--sheet`. It also writes `<output>/index.html`, a grid of every screen across locales and appearances, so the user can review the whole set at a glance. Open it for them (`open` on macOS).

## When run on its own

**Report.** Keep it short:
- the folder checked and the contact sheet
- image counts per platform/device/locale/appearance, and the store slots they fill
- what was fixed, and what still needs the user (re-captures, real bugs in the app)
- anything the user must do in the store consoles (e.g. "Play: tablet listing needs at least 4 images, you have 5 ✓"). If the images show features that need a subscription or purchase, remind them that the App Store description must say so (App Review Guideline 2.3.2).
