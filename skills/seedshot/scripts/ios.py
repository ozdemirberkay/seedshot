#!/usr/bin/env python3
"""Seedshot iOS simulator helper.

Wraps the xcrun simctl steps needed to capture store screenshots:
dedicated simulators per device class, a clean status bar, appearance,
locale-aware launches with seedshot parameters, and "settled" screenshots.

Run `ios.py <command> --help` for details. Standard library only.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import pngkit

DEVICE_PREFIX = "Seedshot "

# Ordered preferences per device class. The first one available on the chosen
# runtime wins. Every entry renders at a size App Store Connect accepts for the
# slot named in the comment (see references/store-specs.md).
DEVICE_CLASSES = {
    # iPhone with Dynamic Island (medium display), the required iPhone slot.
    "phone": ["iPhone 17 Pro", "iPhone 16 Pro", "iPhone 17", "iPhone 16",
              "iPhone 15 Pro", "iPhone 15", "iPhone 14 Pro"],
    # iPad 13-inch display, required when the app runs on iPad.
    "tablet": ["iPad Pro 13-inch (M5)", "iPad Pro 13-inch (M4)",
               "iPad Air 13-inch (M3)", "iPad Air 13-inch (M2)",
               "iPad Pro (12.9-inch) (6th generation)",
               "iPad Pro (12.9-inch) (5th generation)"],
    # Optional: iPhone with Dynamic Island (large display), 6.9".
    "phone-large": ["iPhone 17 Pro Max", "iPhone 16 Pro Max", "iPhone 15 Pro Max",
                    "iPhone 16 Plus", "iPhone Air"],
    # Optional: iPad 11-inch display (otherwise scaled down from 13").
    "tablet-11": ["iPad Pro 11-inch (M5)", "iPad Pro 11-inch (M4)",
                  "iPad Air 11-inch (M3)", "iPad Air 11-inch (M2)"],
}

# Region used for AppleLocale when a locale has no region (e.g. "tr" -> tr_TR).
DEFAULT_REGIONS = {
    "ar": "SA", "cs": "CZ", "da": "DK", "de": "DE", "el": "GR", "en": "US",
    "es": "ES", "fi": "FI", "fr": "FR", "he": "IL", "hi": "IN", "hu": "HU",
    "id": "ID", "it": "IT", "ja": "JP", "ko": "KR", "ms": "MY", "nb": "NO",
    "nl": "NL", "pl": "PL", "pt": "BR", "ro": "RO", "ru": "RU", "sk": "SK",
    "sv": "SE", "th": "TH", "tr": "TR", "uk": "UA", "vi": "VN",
    "zh-Hans": "CN", "zh-Hant": "TW",
}


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, check=True, capture=True, env=None):
    proc = subprocess.run(cmd, capture_output=capture, text=True, env=env)
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        die(f"{' '.join(cmd)}\n{err}")
    return proc


def simctl_json(*args):
    return json.loads(run(["xcrun", "simctl", "list", "-j", *args]).stdout)


def version_tuple(v):
    out = []
    for part in str(v).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def ios_runtimes():
    runtimes = simctl_json("runtimes")["runtimes"]
    return [r for r in runtimes
            if r.get("isAvailable") and (r.get("platform") == "iOS" or r.get("name", "").startswith("iOS"))]


def pick_runtime(explicit=None):
    runtimes = ios_runtimes()
    if not runtimes:
        die("no iOS simulator runtime installed. Install one in Xcode > Settings > Components.")
    if explicit:
        for r in runtimes:
            if explicit in (r["identifier"], r["version"], r["name"]):
                return r
        die(f"runtime '{explicit}' not found. Available: {', '.join(r['name'] for r in runtimes)}")
    # Prefer the newest runtime the installed SDK targets; a newer beta runtime
    # can be unstable with an older Xcode.
    sdk = run(["xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"], check=False).stdout.strip()
    runtimes.sort(key=lambda r: version_tuple(r["version"]), reverse=True)
    if sdk:
        for r in runtimes:
            if version_tuple(r["version"])[:2] <= version_tuple(sdk)[:2]:
                return r
    return runtimes[0]



# ---------------------------------------------------------------- commands

def cmd_doctor(args):
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}{(' — ' + detail) if detail else ''}")

    if not shutil.which("xcrun"):
        line(False, "xcrun", "install Xcode from the App Store, then run: sudo xcode-select -s /Applications/Xcode.app")
        sys.exit(1)
    xc = run(["xcodebuild", "-version"], check=False)
    line(xc.returncode == 0, "Xcode", (xc.stdout or xc.stderr).strip().replace("\n", ", "))
    runtimes = ios_runtimes()
    line(bool(runtimes), "iOS simulator runtimes", ", ".join(r["name"] for r in runtimes) or
         "none; install one in Xcode > Settings > Components")
    if runtimes:
        rt = pick_runtime(args.runtime)
        print(f"  → seedshot will use {rt['name']} ({rt['identifier']})")
        supported = {d["name"] for d in rt.get("supportedDeviceTypes", [])}
        for cls, prefs in DEVICE_CLASSES.items():
            found = next((p for p in prefs if p in supported), None)
            line(found is not None or cls not in ("phone", "tablet"), f"device class '{cls}'",
                 found or "no matching device type for this runtime")
    try:
        import PIL  # noqa: F401
        line(True, "Pillow (optional)", "available")
    except ImportError:
        print("· Pillow (optional) — not installed; verify.py --fix uses a slower pure-Python fallback")
    sys.exit(0 if ok else 1)


def find_or_create_device(device_type_name, runtime):
    supported = {d["name"]: d["identifier"] for d in runtime.get("supportedDeviceTypes", [])}
    if device_type_name not in supported:
        return None
    name = DEVICE_PREFIX + device_type_name
    devices = simctl_json("devices")["devices"].get(runtime["identifier"], [])
    for d in devices:
        if d["name"] == name and d.get("isAvailable", True):
            return d["udid"]
    return run(["xcrun", "simctl", "create", name, supported[device_type_name],
                runtime["identifier"]]).stdout.strip()


def cmd_device(args):
    runtime = pick_runtime(args.runtime)
    candidates = DEVICE_CLASSES.get(args.kind, [args.kind])
    for name in candidates:
        udid = find_or_create_device(name, runtime)
        if udid:
            if args.json:
                print(json.dumps({"udid": udid, "deviceType": name, "runtime": runtime["name"]}))
            else:
                print(udid)
                print(f"{DEVICE_PREFIX}{name} on {runtime['name']}", file=sys.stderr)
            return
    die(f"none of these device types exist for {runtime['name']}: {', '.join(candidates)}")


def cmd_boot(args):
    run(["xcrun", "simctl", "bootstatus", args.udid, "-b"])
    if args.show:
        run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", args.udid], check=False)
    print(f"booted {args.udid}")


def cmd_statusbar(args):
    if args.clear:
        run(["xcrun", "simctl", "status_bar", args.udid, "clear"], check=False)
        print("status bar overrides cleared")
        return
    run(["xcrun", "simctl", "status_bar", args.udid, "override",
         "--time", args.time,
         "--dataNetwork", "wifi", "--wifiMode", "active", "--wifiBars", "3",
         "--cellularMode", "active", "--cellularBars", "4", "--operatorName", "",
         "--batteryState", "discharging", "--batteryLevel", "100"])
    print(f"status bar set ({args.time}, full battery and signal)")


def cmd_appearance(args):
    run(["xcrun", "simctl", "ui", args.udid, "appearance", args.mode])
    print(f"appearance: {args.mode}")


def cmd_install(args):
    if not os.path.isdir(args.app):
        die(f"{args.app} is not an .app bundle directory")
    run(["xcrun", "simctl", "install", args.udid, args.app])
    print(f"installed {os.path.basename(args.app)}")


def apple_locale_args(tag):
    """Map a BCP 47 tag to (AppleLanguages entry, AppleLocale id).

    'tr' -> ('tr-TR', 'tr_TR'); 'en-GB' -> ('en-GB', 'en_GB');
    'zh-Hans' -> ('zh-Hans-CN', 'zh-Hans_CN').
    """
    parts = tag.replace("_", "-").split("-")
    lang = parts[0].lower()
    script = next((p.title() for p in parts[1:] if len(p) == 4), None)
    region = next((p.upper() for p in parts[1:] if len(p) == 2 or (len(p) == 3 and p.isdigit())), None)
    base = f"{lang}-{script}" if script else lang
    region = region or DEFAULT_REGIONS.get(base) or DEFAULT_REGIONS.get(lang)
    language = "-".join(p for p in (lang, script, region) if p)
    locale = f"{base}_{region}" if region else base
    return language, locale


def cmd_launch(args):
    run(["xcrun", "simctl", "terminate", args.udid, args.bundle_id], check=False)
    env = dict(os.environ)
    params = {"SEEDSHOT_LOCALE": args.locale}
    if args.screen:
        params["SEEDSHOT_SCREEN"] = args.screen
    for kv in args.param or []:
        k, _, v = kv.partition("=")
        params[k] = v
    for k, v in params.items():
        env["SIMCTL_CHILD_" + k] = v  # visible to the app as environment variables
    language, locale = apple_locale_args(args.locale)
    argv = ["-AppleLanguages", f"({language})", "-AppleLocale", locale]
    for k, v in params.items():  # also as launch arguments (-KEY value -> UserDefaults)
        argv += [f"-{k}", v]
    run(["xcrun", "simctl", "launch", args.udid, args.bundle_id, *argv], env=env)
    print(f"launched {args.bundle_id} [{args.locale}] screen={args.screen or '-'}")


def capture(udid, tmp_path):
    # simctl's PNG output carries an alpha channel, which both stores reject.
    # BMP keeps the full unmasked framebuffer and converts losslessly to RGB.
    run(["xcrun", "simctl", "io", udid, "screenshot", "--type=bmp", tmp_path])
    with open(tmp_path, "rb") as f:
        return f.read()


def cmd_shot(args):
    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp.bmp"
    time.sleep(args.delay)
    deadline = time.time() + args.settle_timeout
    frame = capture(args.udid, tmp)
    settled = False
    while time.time() < deadline:
        time.sleep(args.interval)
        nxt = capture(args.udid, tmp)
        if hashlib.sha1(nxt).digest() == hashlib.sha1(frame).digest():
            settled = True
            break
        frame = nxt
    os.remove(tmp)
    width, height, rgb = pngkit.bmp_to_rgb(frame)
    pngkit.write_rgb_png(out, width, height, rgb)
    note = "" if settled else "  (warning: screen kept changing; check for looping animations)"
    print(f"saved {out} {width}x{height}{note}")


def seedshot_devices():
    out = []
    for runtime_id, devices in simctl_json("devices")["devices"].items():
        for d in devices:
            if d["name"].startswith(DEVICE_PREFIX):
                out.append(d)
    return out


def cmd_cleanup(args):
    devices = seedshot_devices()
    targets = [d for d in devices if not args.udid or d["udid"] in args.udid]
    for d in targets:
        if d["state"] == "Booted":
            run(["xcrun", "simctl", "status_bar", d["udid"], "clear"], check=False)
            run(["xcrun", "simctl", "ui", d["udid"], "appearance", "light"], check=False)
            run(["xcrun", "simctl", "shutdown", d["udid"]], check=False)
        if args.delete:
            run(["xcrun", "simctl", "delete", d["udid"]], check=False)
        print(f"{'deleted' if args.delete else 'shut down'} {d['name']} ({d['udid']})")
    if not targets:
        print("no seedshot simulators found")


def main():
    p = argparse.ArgumentParser(prog="ios.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("doctor", help="check Xcode, runtimes and device types")
    s.add_argument("--runtime", help="runtime identifier, version or name")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("device", help="print the UDID of a dedicated simulator, creating it if needed")
    s.add_argument("kind", help="phone | tablet | phone-large | tablet-11 | an exact device type name")
    s.add_argument("--runtime", help="runtime identifier, version or name (default: newest matching the SDK)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_device)

    s = sub.add_parser("boot", help="boot a simulator and wait until it is ready")
    s.add_argument("udid")
    s.add_argument("--show", action="store_true", help="also open the Simulator app window")
    s.set_defaults(fn=cmd_boot)

    s = sub.add_parser("statusbar", help="clean status bar: 9:41, full battery, full signal")
    s.add_argument("udid")
    s.add_argument("--time", default="9:41")
    s.add_argument("--clear", action="store_true", help="remove overrides")
    s.set_defaults(fn=cmd_statusbar)

    s = sub.add_parser("appearance", help="switch light/dark mode")
    s.add_argument("udid")
    s.add_argument("mode", choices=["light", "dark"])
    s.set_defaults(fn=cmd_appearance)

    s = sub.add_parser("install", help="install a built .app bundle")
    s.add_argument("udid")
    s.add_argument("app", help="path to the .app built for iphonesimulator")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("launch", help="(re)launch the app in a locale with seedshot parameters")
    s.add_argument("udid")
    s.add_argument("bundle_id")
    s.add_argument("--locale", required=True, help="BCP 47 tag, e.g. tr-TR, en-US, de, zh-Hans")
    s.add_argument("--screen", help="value for SEEDSHOT_SCREEN")
    s.add_argument("--param", action="append", metavar="KEY=VALUE",
                   help="extra parameter passed as env var and launch argument (repeatable)")
    s.set_defaults(fn=cmd_launch)

    s = sub.add_parser("shot", help="save a screenshot once the screen stops changing")
    s.add_argument("udid")
    s.add_argument("out", help="output .png path (folders are created)")
    s.add_argument("--delay", type=float, default=1.5, help="seconds to wait before the first frame")
    s.add_argument("--interval", type=float, default=0.8, help="seconds between comparison frames")
    s.add_argument("--settle-timeout", type=float, default=10.0)
    s.set_defaults(fn=cmd_shot)

    s = sub.add_parser("cleanup", help="clear overrides and shut down seedshot simulators")
    s.add_argument("udid", nargs="*", help="limit to these UDIDs (default: all 'Seedshot …' simulators)")
    s.add_argument("--delete", action="store_true", help="delete the simulators instead of keeping them for next time")
    s.set_defaults(fn=cmd_cleanup)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
