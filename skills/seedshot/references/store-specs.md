# Store screenshot specifications

Verified October 2026 against the official pages below. Stores change these rules. If App Store Connect or Play Console rejects something that `verify.py` accepted, trust the console, and update this file and `verify.py`.

- Apple: https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/
- Google: https://support.google.com/googleplay/android-developer/answer/9866151

## App Store (Apple)

**Required to submit:**
- **iPhone:** at least one screenshot for *iPhone with Dynamic Island (medium display)*, the 6.3" class.
- **iPad** (only if the app supports iPadOS): at least one screenshot for *iPad 13-inch display*.

Apple scales the highest required resolution down to smaller sizes. So 6.3" + 13" covers every device, unless the UI differs per size and the user wants pixel-exact sets for other sizes.

Known ambiguity: the *Face ID (large display)* section still says "Required if app runs on iPhone and screenshots for iPhone with Dynamic Island (large display) aren't provided". If App Store Connect insists on a 6.5"/6.9" set, add the optional `phone-large` device class (iPhone 17 Pro Max, 1320×2868). That fills the Dynamic Island (large) slot and satisfies the rule.

| Slot | Portrait pixels | Simulator (`ios.py device …`) | Status |
|---|---|---|---|
| iPhone 6.3" Dynamic Island (medium) | 1206×2622, 1179×2556 | `phone`: iPhone 17 Pro / 16 Pro | **Required** |
| iPhone 6.9" Dynamic Island (large) | 1320×2868, 1290×2796, 1260×2736 | `phone-large`: iPhone 17 Pro Max | Optional |
| iPhone 6.5" Face ID (large) | 1284×2778, 1242×2688 | — | Optional (see ambiguity) |
| iPhone 6.1" Face ID (medium) | 1170×2532, 1125×2436, 1080×2340 | — | Optional, scaled |
| iPhone 5.5" / 4.7" Home Button | 1242×2208 / 750×1334 | — | Optional, scaled |
| iPhone Duo outer / inner | 1398×2034 / 2007×2853 | — | Optional. Apple says it becomes required in April 2027 for apps built with the iOS 27.1 SDK |
| iPad 13" | 2064×2752, 2048×2732 | `tablet`: iPad Pro 13-inch (M5/M4) | **Required** if the app runs on iPad |
| iPad 11" | 1668×2420, 1668×2388, 1640×2360, 1488×2266 | `tablet-11`: iPad Pro 11-inch | Optional, scaled from 13" |

Landscape is the same pixels swapped.

Other rules:
- Formats: `.png`, `.jpg`, `.jpeg`.
- **No alpha channel or transparency.** `simctl`'s own PNGs are RGBA, which is why `ios.py shot` captures BMP and writes RGB.
- 1–10 screenshots per device size, per localization.
- Content must follow the App Review Guidelines: show the actual app, no misleading content, no other platforms' devices or UI.

## Google Play

Requirements for all screenshots:
- JPEG or **24-bit PNG (no alpha)**.
- Each side 320–3,840 px.
- **The long side can't be more than twice the short side.** Most modern Pixel profiles are 20:9 (e.g. 1080×2400), which is longer than 2:1, so raw emulator captures from them are rejected. That's why `android.py avd phone` creates a 1080×1920 device.
- Up to 8 screenshots per device type. At least 2 across device types to publish.

Large screens (tablets 7" and 10", Chromebooks):
- At least 4 screenshots.
- Each side 1,080–7,680 px.
- "Use a 16:9 aspect ratio for landscape and a 9:16 aspect ratio for portrait."
- `android.py avd tablet` creates 1440×2560 (9:16, 720 dp wide, so tablet layouts kick in).

Featuring ("eligible for recommendations in formats that use screenshots"):
- Apps need at least 4 screenshots at ≥1080 px.
- 9:16 portrait at minimum 1080×1920, or 16:9 landscape at minimum 1920×1080.
- The default phone size meets this.

Content guidance:
- Show the actual in-app experience, with the core value in the first three images.
- No people's hands or fingers, unless usage is off-device.
- Taglines are allowed but must cover ≤20% of the image. Raw seedshot captures have none.
- Don't suggest Play performance or rankings ("#1", "Best app"), and don't include Play badges.

| Device class | Seedshot default | Why |
|---|---|---|
| Phone | 1080×1920 @ 420 dpi (411×731 dp) | 9:16, the featuring requirement; within the 2:1 limit |
| Tablet | 1440×2560 @ 320 dpi (720×1280 dp) | 9:16, the large-screen guidance; ≥1080 px |

If an app looks cramped at 731 dp tall, 1080×2160 (exactly 2:1) is also accepted. It loses featuring eligibility, though, so tell the user before switching.
