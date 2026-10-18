#!/usr/bin/env python3
"""Seedshot Android emulator helper.

Creates dedicated AVDs at Play-Store-safe resolutions, boots them, cleans the
status bar (SystemUI demo mode), switches dark mode and per-app locale,
launches the app with seedshot intent extras, and saves "settled",
alpha-free screenshots.

Run `android.py <command> --help` for details. Standard library only.
"""
import argparse
import hashlib
import os
import platform
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import time

import pngkit

AVD_PREFIX = "Seedshot_"

# Google Play rejects screenshots whose long side exceeds twice the short side
# (most modern Pixel profiles are 20:9), and asks for 9:16 on large screens and
# for featuring. These sizes satisfy both. See references/store-specs.md.
PROFILES = {
    "phone": {"avd": AVD_PREFIX + "Phone", "width": 1080, "height": 1920, "density": 420},
    "tablet": {"avd": AVD_PREFIX + "Tablet", "width": 1440, "height": 2560, "density": 320},
}

TAG_PREFERENCE = ["google_apis", "google_apis_playstore", "default", "aosp_atd", "google_atd"]
TAG_DISPLAY = {"google_apis": "Google APIs", "google_apis_playstore": "Google Play",
               "default": "Default Android System Image"}


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, check=True, timeout=None, text=True):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=text, timeout=timeout)
    except subprocess.TimeoutExpired:
        die(f"timed out: {' '.join(cmd)}")
    if check and proc.returncode != 0:
        err = proc.stderr if text else proc.stderr.decode(errors="replace")
        die(f"{' '.join(cmd)}\n{(err or '').strip()}")
    return proc


# ---------------------------------------------------------------- SDK paths

def sdk_root():
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        path = os.environ.get(env)
        if path and os.path.isdir(path):
            return path
    for path in ("~/Library/Android/sdk", "~/Android/Sdk", "~/AppData/Local/Android/Sdk",
                 "/opt/homebrew/share/android-commandlinetools", "/usr/local/share/android-sdk"):
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            return path
    return None


def adb_path():
    sdk = sdk_root()
    candidate = os.path.join(sdk, "platform-tools", "adb") if sdk else None
    return candidate if candidate and os.path.exists(candidate) else shutil.which("adb")


def emulator_path():
    sdk = sdk_root()
    candidate = os.path.join(sdk, "emulator", "emulator") if sdk else None
    return candidate if candidate and os.path.exists(candidate) else shutil.which("emulator")


def avd_home():
    if os.environ.get("ANDROID_AVD_HOME"):
        return os.environ["ANDROID_AVD_HOME"]
    user_home = os.environ.get("ANDROID_USER_HOME") or os.path.expanduser("~/.android")
    return os.path.join(user_home, "avd")


def adb(serial, *args, check=True, timeout=60, text=True):
    exe = adb_path() or die("adb not found; install Android SDK Platform-Tools")
    return run([exe, "-s", serial, *args], check=check, timeout=timeout, text=text)


def shell(serial, *args, check=True, timeout=60):
    # adb joins shell arguments into one remote command line, so quote each one.
    return adb(serial, "shell", " ".join(shlex.quote(a) for a in args), check=check, timeout=timeout)


def host_abi():
    return "arm64-v8a" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"


def system_images():
    sdk = sdk_root()
    base = os.path.join(sdk, "system-images") if sdk else None
    found = []
    if not base or not os.path.isdir(base):
        return found
    abi = host_abi()
    for api_dir in os.listdir(base):
        try:
            api = int(api_dir.split("-", 1)[1])
        except (IndexError, ValueError):
            continue
        for tag in os.listdir(os.path.join(base, api_dir)):
            path = os.path.join(base, api_dir, tag, abi)
            if os.path.exists(os.path.join(path, "system.img")):
                found.append({"api": api, "tag": tag, "abi": abi,
                              "rel": f"system-images/{api_dir}/{tag}/{abi}/",
                              "package": f"system-images;{api_dir};{tag};{abi}"})
    rank = {t: i for i, t in enumerate(TAG_PREFERENCE)}
    found.sort(key=lambda i: (-i["api"], rank.get(i["tag"], 99)))
    return found


def pick_image(api=None):
    images = system_images()
    if api:
        images = [i for i in images if i["api"] == api]
    # API 33+ is needed for per-app locales without root.
    modern = [i for i in images if i["api"] >= 33]
    return (modern or images or [None])[0]


# ---------------------------------------------------------------- devices

def running_emulators():
    """Map AVD name -> serial for every running emulator."""
    exe = adb_path()
    if not exe:
        return {}
    out = run([exe, "devices"], check=False).stdout
    result = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("emulator-"):
            name = run([exe, "-s", parts[0], "emu", "avd", "name"], check=False, timeout=10).stdout
            name = (name or "").splitlines()[0].strip() if name else ""
            if name:
                result[name] = parts[0]
    return result


def wait_for_boot(serial, timeout):
    deadline = time.time() + timeout
    run([adb_path(), "-s", serial, "wait-for-device"], timeout=timeout)
    while time.time() < deadline:
        out = shell(serial, "getprop", "sys.boot_completed", check=False, timeout=15).stdout.strip()
        if out == "1":
            return
        time.sleep(2)
    die(f"{serial} did not finish booting within {timeout}s")


def free_port(start=5580):
    for port in range(start, 5682, 2):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    die("no free emulator port found")


# ---------------------------------------------------------------- commands

def cmd_doctor(args):
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}{(' — ' + detail) if detail else ''}")

    sdk = sdk_root()
    line(bool(sdk), "Android SDK", sdk or "not found; install Android Studio or set ANDROID_HOME")
    line(bool(adb_path()), "adb", adb_path() or "install SDK Platform-Tools")
    line(bool(emulator_path()), "emulator", emulator_path() or "install the Android Emulator package")
    image = pick_image()
    if image:
        line(True, "system image", f"{image['package']}" + ("" if image["api"] >= 33 else
             "  (API < 33: per-app locale unavailable, root fallback needed)"))
    else:
        line(False, "system image",
             f"none for {host_abi()}; e.g. sdkmanager \"system-images;android-35;google_apis;{host_abi()}\" (~1.5 GB, ask the user first)")
    for cls, prof in PROFILES.items():
        exists = os.path.exists(os.path.join(avd_home(), prof["avd"] + ".ini"))
        print(f"· AVD {prof['avd']} ({prof['width']}x{prof['height']}) — {'exists' if exists else 'will be created by: android.py avd ' + cls}")
    sys.exit(0 if ok else 1)


def cmd_avd(args):
    prof = dict(PROFILES[args.kind])
    image = pick_image(args.api) or die("no usable system image installed (run doctor)")
    name = args.name or prof["avd"]
    home = avd_home()
    avd_dir = os.path.join(home, name + ".avd")
    os.makedirs(avd_dir, exist_ok=True)
    target = f"android-{image['api']}"
    with open(os.path.join(home, name + ".ini"), "w") as f:
        f.write(f"avd.ini.encoding=UTF-8\npath={avd_dir}\npath.rel=avd/{name}.avd\ntarget={target}\n")
    config = {
        "avd.ini.encoding": "UTF-8",
        "AvdId": name,
        "avd.ini.displayname": name.replace("_", " "),
        "abi.type": image["abi"],
        "hw.cpu.arch": "arm64" if image["abi"] == "arm64-v8a" else "x86_64",
        "image.sysdir.1": image["rel"],
        "tag.id": image["tag"],
        "tag.display": TAG_DISPLAY.get(image["tag"], image["tag"]),
        "PlayStore.enabled": "true" if "playstore" in image["tag"] else "false",
        "target": target,
        "hw.lcd.width": str(prof["width"]),
        "hw.lcd.height": str(prof["height"]),
        "hw.lcd.density": str(prof["density"]),
        "hw.initialOrientation": "portrait",
        "hw.ramSize": "4096",
        "hw.gpu.enabled": "yes",
        "hw.gpu.mode": "auto",
        "hw.keyboard": "yes",  # a hardware keyboard keeps the soft keyboard out of shots
        "hw.mainKeys": "no",
        "hw.sdCard": "no",
        "hw.accelerometer": "yes",
        "skin.dynamic": "yes",
        "skin.name": f"{prof['width']}x{prof['height']}",
        "skin.path": "_no_skin",
        "showDeviceFrame": "no",
        "disk.dataPartition.size": "6G",
        "fastboot.forceColdBoot": "yes",
    }
    with open(os.path.join(avd_dir, "config.ini"), "w") as f:
        f.writelines(f"{k}={v}\n" for k, v in config.items())
    print(name)
    print(f"{name}: {prof['width']}x{prof['height']} @{prof['density']}dpi on {image['package']}", file=sys.stderr)


def cmd_boot(args):
    running = running_emulators()
    if args.avd in running:
        serial = running[args.avd]
    else:
        exe = emulator_path() or die("emulator not found")
        port = free_port()
        serial = f"emulator-{port}"
        log = open(os.path.join(avd_home(), f"{args.avd}.seedshot.log"), "w")
        cmd = [exe, "-avd", args.avd, "-port", str(port), "-no-snapshot", "-no-boot-anim", "-no-audio",
               "-gpu", "auto"]
        if args.headless:
            cmd.append("-no-window")
        subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    wait_for_boot(serial, args.timeout)
    # Instant animations settle screens faster; keep the screen awake and unlocked.
    for key in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale"):
        shell(serial, "settings", "put", "global", key, "0", check=False)
    shell(serial, "settings", "put", "secure", "show_ime_with_hard_keyboard", "0", check=False)
    shell(serial, "settings", "put", "secure", "immersive_mode_confirmations", "confirmed", check=False)
    shell(serial, "svc", "power", "stayon", "true", check=False)
    shell(serial, "wm", "dismiss-keyguard", check=False)
    print(serial)


DEMO = [
    ["enter"],
    ["clock", "-e", "hhmm", "{time}"],
    ["battery", "-e", "level", "100", "-e", "plugged", "false", "-e", "powersave", "false"],
    ["network", "-e", "wifi", "show", "-e", "level", "4", "-e", "fully", "true"],
    ["network", "-e", "mobile", "hide"],  # avoids carrier-specific "3G/LTE" badges
    ["network", "-e", "airplane", "hide"],
    ["notifications", "-e", "visible", "false"],
    ["status", "-e", "volume", "hide", "-e", "bluetooth", "hide", "-e", "location", "hide",
     "-e", "alarm", "hide", "-e", "sync", "hide", "-e", "mute", "hide", "-e", "speakerphone", "hide"],
]


def demo_broadcast(serial, command, *extras):
    shell(serial, "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", command, *extras,
          check=False)


def cmd_demo(args):
    if args.exit:
        demo_broadcast(args.serial, "exit")
        print("demo mode off")
        return
    shell(args.serial, "settings", "put", "global", "sysui_demo_allowed", "1")
    hhmm = args.time.replace(":", "").zfill(4)
    for entry in DEMO:
        demo_broadcast(args.serial, entry[0], *[e.replace("{time}", hhmm) for e in entry[1:]])
    print(f"demo mode on ({args.time}, full battery and signal, no notifications)")


def cmd_appearance(args):
    shell(args.serial, "cmd", "uimode", "night", "yes" if args.mode == "dark" else "no")
    print(f"appearance: {args.mode}")


def cmd_install(args):
    exe = adb_path()
    verb = "install-multiple" if len(args.apk) > 1 else "install"
    run([exe, "-s", args.serial, verb, "-r", "-t", "-g", *args.apk], timeout=600)
    print(f"installed {', '.join(os.path.basename(a) for a in args.apk)} (runtime permissions granted)")


def set_locale(serial, package, tag):
    api = int(shell(serial, "getprop", "ro.build.version.sdk").stdout.strip() or 0)
    if api >= 33:
        shell(serial, "cmd", "locale", "set-app-locales", package, "--locales", tag, check=False)
        got = shell(serial, "cmd", "locale", "get-app-locales", package, check=False).stdout
        if tag.lower() in got.lower():
            return "per-app"
    # Fallback: system-wide locale. Needs root, i.e. a google_apis (non-Play) image.
    adb(serial, "root", check=False)
    wait_for_boot(serial, 120)  # adbd restarts when switching to root
    shell(serial, "setprop", "persist.sys.locale", tag, check=False)
    shell(serial, "setprop", "ctl.restart", "zygote", check=False)
    time.sleep(5)
    wait_for_boot(serial, 180)
    current = shell(serial, "getprop", "persist.sys.locale", check=False).stdout.strip()
    if current.lower() != tag.lower():
        die(f"could not set locale {tag}: per-app locales need API 33+, system locale needs a google_apis (rootable) image")
    return "system"


def launcher_activity(serial, package):
    out = shell(serial, "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.LAUNCHER", package, check=False).stdout
    lines = [l.strip() for l in out.splitlines() if "/" in l]
    return lines[-1] if lines else die(f"no launcher activity found for {package}; is it installed?")


def cmd_launch(args):
    shell(args.serial, "am", "force-stop", args.package, check=False)
    how = set_locale(args.serial, args.package, args.locale)
    component = args.activity or launcher_activity(args.serial, args.package)
    if component.startswith("."):
        component = f"{args.package}/{component}"
    params = {"SEEDSHOT_LOCALE": args.locale}
    if args.screen:
        params["SEEDSHOT_SCREEN"] = args.screen
    for kv in args.param or []:
        k, _, v = kv.partition("=")
        params[k] = v
    extras = []
    for k, v in params.items():
        extras += ["--es", k, v]
    shell(args.serial, "am", "start", "-W", "-n", component, *extras, timeout=120)
    print(f"launched {component} [{args.locale}, {how} locale] screen={args.screen or '-'}")


def grab(serial):
    """Return (frame bytes, width, height, rgb-or-None)."""
    data = adb(serial, "exec-out", "screencap", text=False, timeout=30).stdout
    width, height, fmt = struct.unpack("<III", data[:12])
    header = len(data) - width * height * 4
    if fmt in (1, 2) and header in (12, 16):  # RGBA_8888 / RGBX_8888
        return data, width, height, data[header:]
    return data, width, height, None


def cmd_shot(args):
    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    time.sleep(args.delay)
    deadline = time.time() + args.settle_timeout
    frame, width, height, pixels = grab(args.serial)
    settled = False
    while time.time() < deadline:
        time.sleep(args.interval)
        nxt = grab(args.serial)
        if hashlib.sha1(nxt[0]).digest() == hashlib.sha1(frame).digest():
            settled = True
            break
        frame, width, height, pixels = nxt
    if pixels is not None:
        pngkit.write_rgb_png(out, width, height, pngkit.rgba_to_rgb(pixels))
    else:  # unusual pixel format: fall back to the device's PNG encoder, then drop alpha
        with open(out, "wb") as f:
            f.write(adb(args.serial, "exec-out", "screencap", "-p", text=False).stdout)
        pngkit.strip_alpha(out)
    note = "" if settled else "  (warning: screen kept changing; check for looping animations)"
    print(f"saved {out} {width}x{height}{note}")


def cmd_cleanup(args):
    running = running_emulators()
    targets = {n: s for n, s in running.items() if n.startswith(AVD_PREFIX) and (not args.avd or n in args.avd)}
    for name, serial in targets.items():
        demo_broadcast(serial, "exit")
        shell(serial, "cmd", "uimode", "night", "no", check=False)
        adb(serial, "emu", "kill", check=False)
        print(f"stopped {name} ({serial})")
    if args.delete:
        for name in (args.avd or [p["avd"] for p in PROFILES.values()]):
            for path in (os.path.join(avd_home(), name + ".ini"), os.path.join(avd_home(), name + ".avd")):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            print(f"deleted AVD {name}")
    if not targets and not args.delete:
        print("no seedshot emulators running")


def main():
    p = argparse.ArgumentParser(prog="android.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("doctor", help="check SDK, emulator and system images")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("avd", help="create/refresh a dedicated AVD at a store-safe resolution; prints its name")
    s.add_argument("kind", choices=sorted(PROFILES))
    s.add_argument("--api", type=int, help="system image API level (default: newest installed, 33+ preferred)")
    s.add_argument("--name", help="AVD name (default: Seedshot_Phone / Seedshot_Tablet)")
    s.set_defaults(fn=cmd_avd)

    s = sub.add_parser("boot", help="start an AVD (or reuse it if running), wait for boot; prints the serial")
    s.add_argument("avd")
    s.add_argument("--headless", action="store_true", help="no emulator window")
    s.add_argument("--timeout", type=int, default=420)
    s.set_defaults(fn=cmd_boot)

    s = sub.add_parser("demo", help="clean status bar via SystemUI demo mode")
    s.add_argument("serial")
    s.add_argument("--time", default="09:41")
    s.add_argument("--exit", action="store_true", help="leave demo mode")
    s.set_defaults(fn=cmd_demo)

    s = sub.add_parser("appearance", help="switch light/dark mode")
    s.add_argument("serial")
    s.add_argument("mode", choices=["light", "dark"])
    s.set_defaults(fn=cmd_appearance)

    s = sub.add_parser("install", help="install APK(s), granting runtime permissions")
    s.add_argument("serial")
    s.add_argument("apk", nargs="+")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("launch", help="(re)launch the app in a locale with seedshot intent extras")
    s.add_argument("serial")
    s.add_argument("package")
    s.add_argument("--locale", required=True, help="BCP 47 tag, e.g. tr-TR, en-US")
    s.add_argument("--screen", help="value for the SEEDSHOT_SCREEN extra")
    s.add_argument("--activity", help="component to start (default: the launcher activity)")
    s.add_argument("--param", action="append", metavar="KEY=VALUE", help="extra string intent extra (repeatable)")
    s.set_defaults(fn=cmd_launch)

    s = sub.add_parser("shot", help="save an alpha-free screenshot once the screen stops changing")
    s.add_argument("serial")
    s.add_argument("out")
    s.add_argument("--delay", type=float, default=1.5)
    s.add_argument("--interval", type=float, default=0.8)
    s.add_argument("--settle-timeout", type=float, default=10.0)
    s.set_defaults(fn=cmd_shot)

    s = sub.add_parser("cleanup", help="leave demo mode and stop seedshot emulators")
    s.add_argument("avd", nargs="*", help="limit to these AVD names")
    s.add_argument("--delete", action="store_true", help="also delete the seedshot AVDs")
    s.set_defaults(fn=cmd_cleanup)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
