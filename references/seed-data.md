# Writing seed data

Seed data is what the store visitor actually reads. It has to:
- make the app look alive and useful
- read as if a native speaker wrote it
- tell the same story on every device and in every language.

## Start from a story

Before writing JSON, decide in one or two sentences who the user is and what moment you're showing. For example:

> A freelance designer, mid-month, on track with savings, with a busy but healthy week of spending.

Every screen then shows a slice of that one life. Here's why that matters:
- A dashboard, a detail screen and a stats screen agree with each other (the balance on screen 1 matches the transactions on screen 3).
- Each locale tells the same story with local details, so the listing is consistent everywhere.

Pick a **persona per locale**, culturally equivalent and not translated. Use a common, natural local name, not a celebrity's and not a stereotype.

| Locale | Persona | City | Currency |
|---|---|---|---|
| en-US | Emma Carter | Portland | $ |
| tr-TR | Elif Kaya | İzmir | ₺ |
| de-DE | Lena Fischer | Hamburg | € |
| es-ES | Lucía Navarro | Valencia | € |
| ja-JP | 佐藤 美咲 | 福岡 | ¥ |

## Same structure, native content

Keep identical in every locale:
- the number of items in every list, their order, and their states (read/unread, done/pending, selected)
- chart shapes and trends (if English shows a 12% rise, Turkish shows a rise too)
- relative magnitudes (the biggest expense is the biggest everywhere)
- which item a detail screen opens, which tab is selected, which filter is on
- images: the same asset slot shows an equivalent image.

Adapt per locale:
- names, places, shops, foods and holidays: plausible locally
- prices: realistic local amounts, not exchange-rate conversions. A coffee is $4.50, ₺85, €3.20, ¥450. Conversions give odd numbers like ₺153.27.
- units (km/mi, kg/lb, °C/°F) and first day of week
- date, time, number and currency formats. Let the platform formatter do this with the locale, and store raw values (ISO dates, numbers) in the seed files rather than preformatted strings.
- tone and idiom in free text (notes, messages, titles). Write them; don't translate them.

`verify.py --seed <dir>` checks the structural half automatically. It also flags long strings that are identical across locales, which are usually untranslated leftovers.

## Make it look good

- **Populated, not crowded.** Lists show 5–8 varied items. Charts have visible variation. Badges and counts are modest but non-zero (3 unread, not 0 and not 99+).
- **Varied lengths.** Mix short and long titles, but avoid anything that truncates on the narrowest locale.
- **Aspirational but believable.** Healthy streaks, goals mostly met with one in progress, a nice-looking balance. Not a millionaire, not broke.
- **Recent.** Generate timestamps relative to launch ("2 hours ago", "Yesterday", this week's dates), so screenshots never look stale. Keep visible clock times plausible next to the 9:41 status bar: nothing "later today" with a past time.
- **Complete.** Every field a screen displays has a value. No `null`-driven placeholders, "N/A", "Untitled" or default avatars.
- **Tablet-ready.** Wide layouts show more items, more columns, side panels. Supply enough data that the 13" iPad doesn't look empty.

## Avoid

- Lorem ipsum, "Test", "Sample", "Foo", "asdf", "John Doe", "user@example.com" visible on screen
- Real people, real companies' logos and trademarks, copyrighted characters, real addresses, phone numbers or emails. Fictional-but-plausible shop names are fine ("Corner Bakery", "Köşe Fırını").
- Anything sensitive or polarizing: politics, religion, health conditions, unless that's the app's domain, handled respectfully.
- Prices, claims or features the app doesn't actually have, because App Review rejects misleading screenshots
- Content that contradicts the app's real behavior (a "Premium" badge on a free tier, features behind flags that aren't shipping)
- Downloading stock or web images without clear rights. Prefer:
  1. images already in the project
  2. generated art (gradients, shapes, initials avatars, platform icon sets like SF Symbols or Material Symbols)
  3. images the user provides.

## File layout

Keep seed data in data files inside the seedshot module, one per locale, with identical structure:

```
seedshot/data/
  en-US.json
  tr-TR.json
```

The seedshot module loads `<SEEDSHOT_LOCALE>.json`, falling back to the base locale. Bundle every locale's file in the seedshot build, so switching locale needs no rebuild.

Example shape (a finance app):

```json
{
  "persona": { "name": "Elif Kaya", "avatar": "seed_avatar_1" },
  "balance": 84250.75,
  "currency": "TRY",
  "transactions": [
    { "id": "t1", "title": "Köşe Fırını", "amount": -85, "category": "food", "minutesAgo": 95 },
    { "id": "t2", "title": "Maaş", "amount": 42000, "category": "income", "minutesAgo": 4320 }
  ],
  "weeklySpending": [820, 640, 910, 450, 1200, 380, 560]
}
```

Use relative time fields (`minutesAgo`, `daysAgo`) or offsets, and turn them into dates at launch.
