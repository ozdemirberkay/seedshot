#!/usr/bin/env python3
"""Seedshot checks: screenshots against store rules, and seed data across locales.

  verify.py <output> [--fix] [--sheet]   check a screenshot folder
  verify.py --seed <seed-dir> [--base en-US]   check per-locale seed files

Screenshot layout: <output>/<ios|android>/<device-class>/<locale>/<light|dark>/<NN>-<screen>.png
Checks pixel sizes per store slot, alpha channels, per-folder counts and that
every locale/appearance folder holds the same screens.
  --fix    strip alpha channels / 16-bit depth in place
  --sheet  also write <output>/index.html, every screenshot in one grid

Seed check: every <locale>.json must match the base locale's structure (keys,
list lengths, value types); long text identical to the base is flagged as
probably untranslated.

Exit code 1 on errors.
"""
import argparse
import html
import json
import os
import re
import sys
from urllib.parse import quote

import pngkit

# Apple: accepted portrait sizes per display slot (landscape = swapped).
# Source: App Store Connect Help, "Screenshot specifications".
APPLE_SLOTS = {
    "iphone": [
        ("iPhone 6.3\" (Dynamic Island, medium)", [(1179, 2556), (1206, 2622)], "required"),
        ("iPhone 6.9\" (Dynamic Island, large)", [(1260, 2736), (1290, 2796), (1320, 2868)], "optional"),
        ("iPhone 6.5\" (Face ID, large)", [(1284, 2778), (1242, 2688)], "optional"),
        ("iPhone 6.1\" (Face ID, medium)", [(1170, 2532), (1125, 2436), (1080, 2340)], "optional"),
        ("iPhone 5.5\" (Home Button, large)", [(1242, 2208)], "optional"),
        ("iPhone 4.7\" (Home Button, medium)", [(750, 1334)], "optional"),
        ("iPhone Duo (outer)", [(1398, 2034)], "optional"),
        ("iPhone Duo (inner)", [(2007, 2853)], "optional"),
    ],
    "ipad": [
        ("iPad 13\"", [(2064, 2752), (2048, 2732)], "required"),
        ("iPad 11\"", [(1488, 2266), (1668, 2420), (1668, 2388), (1640, 2360)], "optional"),
        ("iPad 10.5\"", [(1668, 2224)], "optional"),
        ("iPad 9.7\"", [(1536, 2008), (1536, 2048)], "optional"),
    ],
}
APPLE_MAX_PER_SET = 10
PLAY_MAX_PER_SET = 8
PLAY_MIN_LARGE_SCREEN = 4
NAME_RE = re.compile(r"^\d{2}-[a-z0-9][a-z0-9._-]*\.(png|jpe?g)$")
IMAGE_EXT = (".png", ".jpg", ".jpeg")


class Report:
    def __init__(self):
        self.errors, self.warnings, self.notes = [], [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.notes.append(msg)


def apple_slot(kind, w, h):
    for name, sizes, status in APPLE_SLOTS[kind]:
        if (w, h) in sizes or (h, w) in sizes:
            return name, status
    return None, None


def check_image(platform, device_class, rel, info, rep):
    w, h = info["width"], info["height"]
    if info["alpha"]:
        rep.error(f"{rel}: has an alpha channel; both stores reject it (run with --fix)")
    if info["format"] == "png" and info.get("bit_depth", 8) != 8:
        rep.error(f"{rel}: {info['bit_depth']}-bit PNG; stores expect 8 bits per channel (run with --fix)")
    if platform == "ios":
        kind = "ipad" if device_class.startswith("tablet") or "ipad" in device_class.lower() else "iphone"
        slot, status = apple_slot(kind, w, h)
        if not slot:
            rep.error(f"{rel}: {w}x{h} is not an accepted App Store {('iPad' if kind == 'ipad' else 'iPhone')} size")
        return slot, status
    if platform == "android":
        short, long_ = min(w, h), max(w, h)
        large = device_class.startswith("tablet") or "chromebook" in device_class
        if large:
            if short < 1080 or long_ > 7680:
                rep.error(f"{rel}: {w}x{h}; Play large-screen images must be 1,080-7,680 px per side")
            if long_ * 9 != short * 16:
                rep.warn(f"{rel}: {w}x{h} is not 9:16 / 16:9, which Play asks for on large screens")
        else:
            if short < 320 or long_ > 3840:
                rep.error(f"{rel}: {w}x{h}; Play images must be 320-3,840 px per side")
            if long_ > 2 * short:
                rep.error(f"{rel}: {w}x{h} is longer than 2:1; Play rejects it (use a 9:16 or 18:9 device)")
            elif short < 1080 or long_ * 9 != short * 16:
                rep.warn(f"{rel}: {w}x{h}; Play featuring wants 9:16 portrait at least 1080x1920")
        return f"Play {'large screen' if large else 'phone'}", None
    rep.warn(f"{rel}: unknown platform folder '{platform}'")
    return None, None


def walk(root):
    """Yield (platform, device_class, locale, appearance, filename)."""
    for platform in sorted(os.listdir(root)):
        p_dir = os.path.join(root, platform)
        if not os.path.isdir(p_dir) or platform.startswith((".", "_")):
            continue
        for device in sorted(os.listdir(p_dir)):
            d_dir = os.path.join(p_dir, device)
            if not os.path.isdir(d_dir):
                continue
            for locale in sorted(os.listdir(d_dir)):
                l_dir = os.path.join(d_dir, locale)
                if not os.path.isdir(l_dir):
                    continue
                for appearance in sorted(os.listdir(l_dir)):
                    a_dir = os.path.join(l_dir, appearance)
                    if not os.path.isdir(a_dir):
                        continue
                    for name in sorted(os.listdir(a_dir)):
                        if name.lower().endswith(IMAGE_EXT):
                            yield platform, device, locale, appearance, name


def check_screenshots(args):
    root = os.path.abspath(os.path.expanduser(args.output))
    if not os.path.isdir(root):
        sys.exit(f"error: {root} is not a directory")

    rep = Report()
    sets = {}       # (platform, device, locale, appearance) -> [names]
    slots = {}      # (platform, device) -> {slot: status}
    fixed = 0
    for platform, device, locale, appearance, name in walk(root):
        rel = os.path.join(platform, device, locale, appearance, name)
        path = os.path.join(root, rel)
        sets.setdefault((platform, device, locale, appearance), []).append(name)
        info = pngkit.image_info(path)
        if not info:
            rep.error(f"{rel}: not a readable PNG or JPEG")
            continue
        needs_fix = info["alpha"] or (info["format"] == "png" and info.get("bit_depth", 8) != 8)
        if needs_fix and args.fix:
            method = pngkit.strip_alpha(path)
            info = pngkit.image_info(path)
            fixed += 1
            rep.note(f"{rel}: alpha removed ({method})")
        slot, status = check_image(platform, device, rel, info, rep)
        if slot:
            slots.setdefault((platform, device), {})[slot] = status
        if not NAME_RE.match(name):
            rep.warn(f"{rel}: name should look like '01-home.png' so uploads keep store order")

    if not sets:
        sys.exit(f"error: no images found under {root} (expected <platform>/<device>/<locale>/<appearance>/*.png)")

    # Counts per upload set.
    for (platform, device, locale, appearance), names in sets.items():
        where = f"{platform}/{device}/{locale}/{appearance}"
        limit = APPLE_MAX_PER_SET if platform == "ios" else PLAY_MAX_PER_SET
        if len(names) > limit:
            rep.error(f"{where}: {len(names)} images; the store allows at most {limit} per set")
        if platform == "android" and device.startswith("tablet") and len(names) < PLAY_MIN_LARGE_SCREEN:
            rep.warn(f"{where}: {len(names)} images; Play wants at least {PLAY_MIN_LARGE_SCREEN} for tablets")

    # Matrix completeness: every locale/appearance of a device must hold the same screens.
    by_device = {}
    for (platform, device, locale, appearance), names in sets.items():
        by_device.setdefault((platform, device), {})[(locale, appearance)] = set(names)
    for (platform, device), cells in by_device.items():
        union = set().union(*cells.values())
        for (locale, appearance), names in sorted(cells.items()):
            missing = sorted(union - names)
            if missing:
                rep.error(f"{platform}/{device}/{locale}/{appearance}: missing {', '.join(missing)}")
        locales = sorted({l for l, _ in cells})
        appearances = sorted({a for _, a in cells})
        for locale in locales:
            for appearance in appearances:
                if (locale, appearance) not in cells:
                    rep.error(f"{platform}/{device}/{locale}/{appearance}: folder missing")
    screen_sets = {k: {re.sub(r"\.(png|jpe?g)$", "", n) for c in v.values() for n in c} for k, v in by_device.items()}
    everywhere = set.intersection(*screen_sets.values())
    for (platform, device), screens in sorted(screen_sets.items()):
        extra = sorted(screens - everywhere)
        if extra:
            rep.warn(f"{platform}/{device}: screens not captured on every device: {', '.join(extra)}")

    # Store-slot summary.
    for (platform, device), found in sorted(slots.items()):
        rep.note(f"{platform}/{device}: fills {', '.join(f'{s} ({st})' if st else s for s, st in found.items())}")
    if any(p == "ios" for p, _ in slots):
        ios_slots = {s for (p, _), f in slots.items() if p == "ios" for s in f}
        if not any(s.startswith("iPhone 6.3") for s in ios_slots):
            rep.warn("no iPhone 6.3\" set; App Store Connect requires it for iPhone apps")
        if any("ipad" in d or d.startswith("tablet") for p, d in slots if p == "ios") and \
                not any(s.startswith("iPad 13") for s in ios_slots):
            rep.warn("no iPad 13\" set; App Store Connect requires it when the app runs on iPad")

    total = sum(len(v) for v in sets.values())
    if args.json:
        print(json.dumps({"root": root, "images": total, "fixed": fixed, "errors": rep.errors,
                          "warnings": rep.warnings, "notes": rep.notes}, indent=2))
    else:
        print(f"seedshot verify: {root}")
        print(f"{total} images in {len(sets)} sets" + (f", {fixed} fixed" if fixed else ""))
        for (platform, device), cells in sorted(by_device.items()):
            counts = sorted({len(v) for v in cells.values()})
            print(f"  {platform}/{device}: {len(cells)} sets × {'/'.join(map(str, counts))} screens")
        for n in rep.notes:
            print(f"  · {n}")
        if rep.warnings:
            print(f"\nWarnings ({len(rep.warnings)}):")
            for w in rep.warnings:
                print(f"  ! {w}")
        if rep.errors:
            print(f"\nErrors ({len(rep.errors)}):")
            for e in rep.errors:
                print(f"  ✗ {e}")
        print("\n" + ("✗ not store-ready" if rep.errors else "✓ store-ready"))
    if args.sheet:
        print(f"contact sheet: {write_sheet(root, args.title)}")
    sys.exit(1 if rep.errors else 0)


# ---------------------------------------------------------------- contact sheet

SHEET_CSS = """
:root { --bg:#f6f6f4; --fg:#1d1d1f; --muted:#6e6e73; --card:#fff; --line:#e3e3e0; --accent:#0a66ff; }
@media (prefers-color-scheme: dark) { :root { --bg:#111113; --fg:#f2f2f2; --muted:#9a9aa0; --card:#1c1c1f; --line:#2c2c30; --accent:#5b9bff; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
header { padding:28px 24px 8px; }
h1 { margin:0 0 4px; font-size:22px; letter-spacing:-.01em; }
.sub { color:var(--muted); }
nav { display:flex; gap:8px; flex-wrap:wrap; padding:12px 24px 0; }
nav a { color:var(--accent); text-decoration:none; border:1px solid var(--line); border-radius:999px; padding:4px 12px; background:var(--card); }
section { padding:20px 24px 8px; }
h2 { font-size:16px; margin:0 0 12px; }
h2 small { color:var(--muted); font-weight:400; margin-left:6px; }
.scroll { overflow-x:auto; padding-bottom:12px; }
table { border-collapse:separate; border-spacing:10px 0; }
th { font-weight:600; text-align:left; padding:0 0 8px; white-space:nowrap; }
th small { display:block; color:var(--muted); font-weight:400; }
td { vertical-align:top; padding:0 0 14px; }
td.screen { color:var(--muted); white-space:nowrap; padding-right:4px; font-variant-numeric:tabular-nums; position:sticky; left:0; background:var(--bg); }
figure { margin:0; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:6px; width:var(--w); }
figure img { display:block; width:100%; height:auto; border-radius:9px; }
figcaption { color:var(--muted); font-size:11px; padding:4px 2px 0; font-variant-numeric:tabular-nums; }
.missing { width:var(--w); aspect-ratio:var(--ar); border:1px dashed #d33; border-radius:14px; color:#d33; display:grid; place-items:center; font-size:12px; }
"""


def write_sheet(root, title=None):
    """Write <root>/index.html: rows are screens, columns are locale × appearance, one section per device."""
    title = title or os.path.basename(root.rstrip("/"))
    groups = {}
    for platform, device, locale, appearance, name in walk(root):
        g = groups.setdefault((platform, device), {"cols": set(), "rows": set(), "cells": {}})
        g["cols"].add((locale, appearance))
        g["rows"].add(name)
        rel = "/".join([platform, device, locale, appearance, name])
        g["cells"][(name, locale, appearance)] = (rel, pngkit.image_info(os.path.join(root, rel)))
    total = sum(len(g["cells"]) for g in groups.values())
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
           f"<title>{html.escape(title)} · seedshot</title><style>{SHEET_CSS}</style></head><body>",
           f"<header><h1>{html.escape(title)}</h1><div class='sub'>{total} screenshots · "
           f"{len(groups)} device sets · generated by seedshot</div></header><nav>"]
    for platform, device in sorted(groups):
        out.append(f"<a href='#{platform}-{device}'>{html.escape(platform)} / {html.escape(device)}</a>")
    out.append("</nav>")
    for (platform, device), g in sorted(groups.items()):
        cols = sorted(g["cols"], key=lambda c: (c[0], c[1] != "light", c[1]))
        rows = sorted(g["rows"])
        sample = next((info for _, info in g["cells"].values() if info), None)
        ar = f"{sample['width']}/{sample['height']}" if sample else "9/19.5"
        width = 240 if sample and sample["width"] / sample["height"] > 0.6 else 170
        out.append(f"<section id='{platform}-{device}' style='--w:{width}px;--ar:{ar}'>"
                   f"<h2>{html.escape(platform)} / {html.escape(device)}"
                   f"<small>{len(rows)} screens × {len(cols)} sets</small></h2>"
                   f"<div class='scroll'><table><tr><th></th>")
        for locale, appearance in cols:
            out.append(f"<th>{html.escape(locale)}<small>{html.escape(appearance)}</small></th>")
        out.append("</tr>")
        for name in rows:
            label = os.path.splitext(name)[0]
            out.append(f"<tr><td class='screen'>{html.escape(label)}</td>")
            for locale, appearance in cols:
                cell = g["cells"].get((name, locale, appearance))
                if not cell:
                    out.append("<td><div class='missing'>missing</div></td>")
                    continue
                rel, info = cell
                size = f"{info['width']}×{info['height']}" if info else "unreadable"
                out.append(f"<td><figure><a href='{quote(rel)}' target='_blank'><img loading='lazy' "
                           f"src='{quote(rel)}' alt='{html.escape(label)} {html.escape(locale)} {appearance}'></a>"
                           f"<figcaption>{size}</figcaption></figure></td>")
            out.append("</tr>")
        out.append("</table></div></section>")
    out.append("</body></html>")
    path = os.path.join(root, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))
    return path


# ---------------------------------------------------------------- seed parity

URLISH = re.compile(r"^(https?://|www\.|[\w.+-]+@[\w-]+\.|[\w/.-]+\.(png|jpe?g|webp|svg|json)$|#[0-9a-fA-F]{3,8}$)")


def _kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return "null" if value is None else type(value).__name__


def _compare(base, other, path, problems, leftovers):
    if _kind(base) != _kind(other):
        problems.append(f"{path or '/'}: {_kind(base)} vs {_kind(other)}")
    elif isinstance(base, dict):
        for key in sorted(base.keys() - other.keys()):
            problems.append(f"{path}/{key}: missing")
        for key in sorted(other.keys() - base.keys()):
            problems.append(f"{path}/{key}: extra key")
        for key in sorted(base.keys() & other.keys()):
            _compare(base[key], other[key], f"{path}/{key}", problems, leftovers)
    elif isinstance(base, list):
        if len(base) != len(other):
            problems.append(f"{path}: {len(base)} items vs {len(other)}")
        for i, (a, b) in enumerate(zip(base, other)):
            _compare(a, b, f"{path}[{i}]", problems, leftovers)
    elif isinstance(base, str) and base == other:
        if len(re.findall(r"[^\W\d_]{2,}", base)) >= 2 and not URLISH.match(base):
            leftovers.append(f"{path}: \"{base[:60]}\"")


def check_seed(paths, base=None):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith(".json")]
        else:
            files.append(p)
    if len(files) < 2:
        sys.exit("error: need at least two locale files to compare")
    data = {}
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data[os.path.splitext(os.path.basename(f))[0]] = json.load(fh)
    base = base or next((k for k in ("en-US", "en", "en-GB") if k in data), next(iter(data)))
    if base not in data:
        sys.exit(f"error: base locale '{base}' not among {', '.join(data)}")
    failed = False
    for locale, doc in data.items():
        if locale == base:
            continue
        problems, leftovers = [], []
        _compare(data[base], doc, "", problems, leftovers)
        print(f"{'✗' if problems else '✓'} {locale} vs {base}: {len(problems)} structural differences, "
              f"{len(leftovers)} possibly untranslated")
        for p in problems[:50]:
            print(f"    ✗ {p}")
        for h in leftovers[:20]:
            print(f"    ? {h}")
        failed = failed or bool(problems)
    sys.exit(1 if failed else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output", nargs="?", help="screenshot output folder")
    ap.add_argument("--fix", action="store_true", help="strip alpha channels / reduce bit depth in place")
    ap.add_argument("--sheet", action="store_true", help="also write <output>/index.html")
    ap.add_argument("--title", help="contact sheet title (default: output folder name)")
    ap.add_argument("--json", action="store_true", help="machine-readable screenshot report")
    ap.add_argument("--seed", nargs="+", metavar="PATH", help="check per-locale seed JSON files instead")
    ap.add_argument("--base", help="base locale for --seed (default: en-US/en if present)")
    args = ap.parse_args()
    if args.seed:
        check_seed(args.seed, args.base)
    elif args.output:
        check_screenshots(args)
    else:
        ap.error("give a screenshot output folder, or --seed <dir>")


if __name__ == "__main__":
    main()
