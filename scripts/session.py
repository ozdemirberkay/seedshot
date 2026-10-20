#!/usr/bin/env python3
"""Seedshot change tracker: leave a project exactly as Seedshot found it.

  start     snapshot the project before Seedshot changes anything
  track     register files or folders Seedshot is about to change or create
  status    list Seedshot's changes, and any other change made since start
  restore   save Seedshot's changes to .seedshot/seedshot.patch, then put every
            registered file back as it was at start; other changes stay
  apply     put a saved .seedshot/seedshot.patch back in (next release)

The snapshot is a git tree. In a git repository it is kept in the repo's own
object store under refs/worktree/seedshot; your index, branches, stash and
files are never touched. Outside git, a private repository under
~/.cache/seedshot holds it.

Also reads demo-account files for `ios.py launch --login` and
`android.py launch --login`. Run `session.py <command> --help` for details.
Standard library only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

SEEDSHOT_DIR = ".seedshot"
PATCH = "seedshot.patch"
LOGIN = "login.json"
REF = "refs/worktree/seedshot"
IDENTITY = {"GIT_AUTHOR_NAME": "seedshot", "GIT_AUTHOR_EMAIL": "seedshot@localhost",
            "GIT_COMMITTER_NAME": "seedshot", "GIT_COMMITTER_EMAIL": "seedshot@localhost"}
# .seedshot/ ignores itself, like .pytest_cache, so it never shows up in git status.
OWN_IGNORE = ("# Seedshot's files: the plan, the saved seedshot mode, the demo account.\n"
              "# Kept on this machine for the next release, never committed.\n"
              "# To share the plan with your team: git add -f .seedshot/config.json\n*\n")
# What an older Seedshot wrote; replaced by OWN_IGNORE.
OLD_IGNORE = f"# Demo-account credentials for seedshot launches. Never commit them.\n{LOGIN}\n"
# Only used outside git. Inside a repository, its own .gitignore files decide.
DEFAULT_EXCLUDES = """\
.seedshot/
build/
.build/
DerivedData/
Pods/
node_modules/
.gradle/
.cxx/
.kotlin/
.dart_tool/
.expo/
.idea/
xcuserdata/
*.xcuserstate
.DS_Store
local.properties
"""
# Reverting one of these means installed dependencies may be ahead of the project.
DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "Podfile", "Podfile.lock", "Package.resolved", "pubspec.yaml", "pubspec.lock",
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "libs.versions.toml", "Gemfile", "Gemfile.lock",
}
LABELS = {"A": "added", "M": "modified", "D": "deleted", "T": "type changed"}


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def under(path, roots):
    return any(path == r or path.startswith(r + "/") for r in roots)


def is_own_file(path):
    return SEEDSHOT_DIR in path.split("/")


class Project:
    def __init__(self, path):
        self.root = os.path.realpath(path)
        if not os.path.isdir(self.root):
            die(f"{path} is not a folder")
        base = {k: v for k, v in os.environ.items()
                if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=self.root,
                             env=base, capture_output=True, text=True)
        if top.returncode == 0:
            self.in_git = True
            self.top = os.path.realpath(top.stdout.strip())
            self.env = dict(base)
            self.state = os.path.join(self.top, self.git("rev-parse", "--git-path", "seedshot").strip())
            self.real_index = os.path.join(self.top, self.git("rev-parse", "--git-path", "index").strip())
        else:
            self.in_git = False
            self.top = self.root
            self.state = os.path.join(os.path.expanduser("~/.cache/seedshot"),
                                      hashlib.sha1(self.root.encode()).hexdigest()[:16])
            self.env = dict(base, GIT_DIR=os.path.join(self.state, "git"), GIT_WORK_TREE=self.root)
            self.real_index = None
        self.env.update(IDENTITY)
        self.env["GIT_INDEX_FILE"] = os.path.join(self.state, "index")
        self.session_file = os.path.join(self.state, "session.json")

    def git(self, *args, check=True, text=True, input=None):
        proc = subprocess.run(["git", "--literal-pathspecs", *args], cwd=self.top, env=self.env,
                              input=input, capture_output=True, text=text)
        if check and proc.returncode != 0:
            err = proc.stderr if text else proc.stderr.decode(errors="replace")
            die(f"git {args[0]} failed: {err.strip()}")
        return proc.stdout

    def rel(self, path):
        """Project-relative path ('lib/seedshot') for a path given from the current folder."""
        full = os.path.abspath(os.path.expanduser(path))
        full = os.path.join(os.path.realpath(os.path.dirname(full)), os.path.basename(full))
        rel = os.path.relpath(full, self.top).replace(os.sep, "/").rstrip("/")
        if rel in ("", ".") or rel.startswith("../"):
            die(f"{path}: track individual files or folders inside the project")
        return rel

    # -- session state -------------------------------------------------------

    def load(self):
        try:
            with open(self.session_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def require(self):
        s = self.load()
        if not s:
            die("no Seedshot session in this project. Run `session.py start` first.")
        return s

    def save(self, s):
        os.makedirs(self.state, exist_ok=True)
        with open(self.session_file, "w") as f:
            json.dump(s, f, indent=2)

    def end(self):
        self.git("update-ref", "-d", REF, check=False)
        shutil.rmtree(self.state, ignore_errors=True)  # outside git this is the private repository

    def own_dir(self):
        """Create .seedshot/ with a .gitignore that hides the whole folder from git."""
        d = os.path.join(self.root, SEEDSHOT_DIR)
        os.makedirs(d, exist_ok=True)
        ignore = os.path.join(d, ".gitignore")
        try:
            with open(ignore) as f:
                current = f.read()
        except FileNotFoundError:
            current = OLD_IGNORE
        if current == OLD_IGNORE:  # a .gitignore the user edited is left alone
            with open(ignore, "w") as f:
                f.write(OWN_IGNORE)
        return d

    # -- snapshots -----------------------------------------------------------

    def snapshot(self):
        """Store the working tree (tracked and untracked files, minus ignored ones) as a git tree."""
        os.makedirs(self.state, exist_ok=True)
        if not self.in_git and not os.path.isdir(self.env["GIT_DIR"]):
            self.git("init", "-q")
            os.makedirs(os.path.join(self.env["GIT_DIR"], "info"), exist_ok=True)
            with open(os.path.join(self.env["GIT_DIR"], "info", "exclude"), "w") as f:
                f.write(DEFAULT_EXCLUDES)
        if self.real_index and os.path.exists(self.real_index):
            shutil.copyfile(self.real_index, self.env["GIT_INDEX_FILE"])  # reuse stat data: fast
        self.git("add", "-A", "--", ".")
        return self.git("write-tree").strip()

    def changes(self, s):
        """Return (seedshot, other, conflicts, tree) for everything changed since start."""
        tree = self.snapshot()
        out = self.git("diff-tree", "-r", "-z", "--no-renames", "--name-status",
                       s["baseline"] + "^{tree}", tree)
        items = out.split("\0")
        seedshot, other = [], []
        for status, path in zip(items[0::2], items[1::2]):
            if not path or is_own_file(path):
                continue
            (seedshot if under(path, s["tracked"]) else other).append((status, path))
        conflicts = set()
        head = self.git("rev-parse", "-q", "--verify", "HEAD", check=False).strip() if self.in_git else ""
        if s.get("head") and head and head != s["head"] and seedshot:
            committed = self.git("diff-tree", "-r", "-z", "--no-renames", "--name-only",
                                 s["head"], head, "--", *[p for _, p in seedshot])
            conflicts = {p for p in committed.split("\0") if p}
        return seedshot, other, conflicts, tree

    def restore_file(self, baseline, path):
        dest = os.path.join(self.top, path)
        mode = self.git("ls-tree", "-z", baseline, "--", path).split(" ", 1)[0]
        if mode == "160000":  # submodule pointer; not ours to touch
            return
        # --filters gives the file as a checkout would write it (line endings, LFS).
        data = self.git("cat-file", "--filters", f"{baseline}:{path}", text=False)
        if mode == "120000" or os.path.islink(dest) or os.path.isdir(dest):
            remove(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if mode == "120000":
            os.symlink(data.decode(), dest)
            return
        with open(dest, "wb") as f:  # rewriting in place keeps the file's permissions
            f.write(data)
        perms = os.stat(dest).st_mode & 0o777
        os.chmod(dest, perms | 0o111 if mode == "100755" else perms & ~0o111)

    def prune_dirs(self, path):
        d = os.path.dirname(os.path.join(self.top, path))
        while d.startswith(self.top + os.sep) and os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
            d = os.path.dirname(d)


def remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.remove(path)


def print_list(title, rows):
    if rows:
        print(title)
        for status, path in rows:
            print(f"  {LABELS.get(status, status):<9} {path}")


# -- commands ------------------------------------------------------------------

def cmd_start(p, args):
    s = p.load()
    if s:
        seedshot = p.changes(s)[0]
        print(f"session already active since {s['started']}; Seedshot changed {len(seedshot)} file(s) so far")
        return
    tree = p.snapshot()
    commit = p.git("commit-tree", tree, "-m", "seedshot baseline").strip()
    p.git("update-ref", REF, commit)
    head = p.git("rev-parse", "-q", "--verify", "HEAD", check=False).strip() if p.in_git else ""
    p.save({"started": time.strftime("%Y-%m-%d %H:%M"), "root": p.root,
            "baseline": commit, "head": head, "tracked": {}})
    p.own_dir()
    print(f"session started for {p.root}")
    print("register every file or folder before you change or create it: session.py track <path>…")


def cmd_track(p, args):
    s = p.require()
    for path in args.paths:
        rel = p.rel(path)
        if not is_own_file(rel):
            s["tracked"].setdefault(rel, os.path.lexists(os.path.join(p.top, rel)))
    p.save(s)
    print(f"tracking {len(s['tracked'])} path(s)")


def cmd_status(p, args):
    s = p.load()
    if not s:
        print("no Seedshot session: nothing to restore in this project")
        return
    seedshot, other, conflicts, _ = p.changes(s)
    print(f"Seedshot session since {s['started']} in {p.root}")
    if not seedshot:
        print("Seedshot has changed nothing yet")
    print_list("Seedshot's changes (restore puts these back):", seedshot)
    if conflicts:
        print("also changed by a commit since start (restore leaves these for you to fix by hand):")
        for path in sorted(conflicts):
            print(f"  {path}")
    print_list("Other changes since start (not Seedshot's; restore leaves them alone):", other)


def cmd_restore(p, args):
    s = p.require()
    seedshot, other, conflicts, tree = p.changes(s)
    keep = {p.rel(k) for k in args.keep or []}
    kept = [(st, path) for st, path in seedshot if under(path, keep)]
    saved = [(st, path) for st, path in seedshot if not under(path, keep)]
    revert = [(st, path) for st, path in saved if path not in conflicts]

    for _, path in kept:
        diff = p.git("diff", "--no-color", "--no-ext-diff", s["baseline"] + "^{tree}", tree, "--", path)
        if any(l.startswith("+") and "seedshot" in l.lower() for l in diff.splitlines()):
            print(f"warning: kept file {path} still contains seedshot code; remove that part by hand")

    if saved and not args.no_save:
        patch = p.git("diff", "--binary", "--no-renames", "--no-color", "--no-ext-diff", "--no-textconv",
                      "--src-prefix=a/", "--dst-prefix=b/", s["baseline"] + "^{tree}", tree,
                      "--", *[path for _, path in saved], text=False)
        out = os.path.join(p.own_dir(), PATCH)
        with open(out, "wb") as f:
            f.write(patch)

    for status, path in revert:
        if status == "A":
            remove(os.path.join(p.top, path))
            p.prune_dirs(path)
        else:
            p.restore_file(s["baseline"], path)
    # Folders Seedshot created: remove them whole, ignored files (build output) included.
    for path, existed in s["tracked"].items():
        if not existed and not under(path, keep) and not any(under(k, [path]) for k in keep) \
                and not any(under(c, [path]) for c in conflicts):
            remove(os.path.join(p.top, path))
            p.prune_dirs(path)
    p.end()

    print_list(f"restored {len(revert)} file(s) to how they were before Seedshot:", revert)
    if not revert:
        print("Seedshot's changes: none left to restore")
    print_list("kept as they are now (--keep):", kept)
    if conflicts:
        print("NOT restored, because a commit since start changed them too. Remove Seedshot's part by hand:")
        for path in sorted(conflicts):
            print(f"  {path}")
    print_list("left alone, not Seedshot's (yours, or written by a build):", other)
    if saved and not args.no_save:
        print(f"saved Seedshot's changes to {os.path.join(p.root, SEEDSHOT_DIR, PATCH)} "
              "(next release: session.py apply)")
    deps = sorted({path for _, path in revert if os.path.basename(path) in DEPENDENCY_FILES})
    if deps:
        print(f"note: dependency files were restored ({', '.join(deps)}). Run the project's install "
              "step (pod install, npm install, flutter pub get …) before the next build.")


def split_patch(data):
    chunks, cur = [], []
    for line in data.splitlines(keepends=True):
        if line.startswith(b"diff --git ") and cur:
            chunks.append(b"".join(cur))
            cur = []
        cur.append(line)
    if cur:
        chunks.append(b"".join(cur))
    return chunks


def cmd_apply(p, args):
    patch = args.patch or os.path.join(p.root, SEEDSHOT_DIR, PATCH)
    if not os.path.isfile(patch):
        die(f"no saved patch at {patch}")
    if not p.load():
        cmd_start(p, args)
    s = p.load()
    with open(patch, "rb") as f:
        chunks = split_patch(f.read())
    applied, failed = [], []
    for chunk in chunks:
        stat = p.git("apply", "--numstat", "-z", "-", input=chunk, text=False, check=False)
        path = stat.decode().split("\t", 2)[-1].rstrip("\0") if stat else ""
        if not path:
            continue
        s["tracked"].setdefault(path, os.path.lexists(os.path.join(p.top, path)))
        ok = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=p.top, env=p.env,
                            input=chunk, capture_output=True).returncode == 0
        (applied if ok else failed).append(path)
    p.save(s)
    print(f"applied {len(applied)} of {len(applied) + len(failed)} file(s) from {patch}")
    if failed:
        print("could not apply, because the code changed since. Put Seedshot's part back by hand "
              "(the patch shows what it was); these paths are already tracked:")
        for path in failed:
            print(f"  {path}")


# -- demo account for launches -------------------------------------------------

def login_params(path):
    """Read a demo-account file into SEEDSHOT_LOGIN_* launch parameters.

    {"email": "demo@example.com", "password": "…"} becomes SEEDSHOT_LOGIN_EMAIL
    and SEEDSHOT_LOGIN_PASSWORD. Values are never printed. A file git could
    commit is refused.
    """
    full = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(full):
        die(f"no demo-account file at {path}. Create it as JSON, e.g. "
            '{"email": "demo@example.com", "password": "…"}')
    try:
        ignored = subprocess.run(["git", "check-ignore", "-q", full], cwd=os.path.dirname(full),
                                 capture_output=True).returncode
    except FileNotFoundError:
        ignored = 128
    if ignored == 1:
        die(f"{path} is not git-ignored, so it could be committed. Add it to .gitignore first "
            f"({SEEDSHOT_DIR}/.gitignore, created by `session.py start`, ignores the whole folder).")
    try:
        with open(full) as f:
            data = json.load(f)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not data or not all(isinstance(v, str) for v in data.values()):
        die(f"{path} must be a JSON object of strings, e.g. "
            '{"email": "demo@example.com", "password": "…"}')
    return {"SEEDSHOT_LOGIN_" + re.sub(r"[^A-Z0-9]+", "_", k.upper()).strip("_"): v
            for k, v in data.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=".", help="project folder, where .seedshot/ lives (default: current)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="snapshot the project before Seedshot changes anything")
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("track", help="register files or folders before changing or creating them")
    s.add_argument("paths", nargs="+")
    s.set_defaults(fn=cmd_track)

    s = sub.add_parser("status", help="list Seedshot's changes and other changes since start")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("restore", help="save Seedshot's changes as a patch, then undo them")
    s.add_argument("--keep", action="append", metavar="PATH",
                   help="leave this file as it is now, e.g. a real bug fix (repeatable)")
    s.add_argument("--no-save", action="store_true", help="don't write .seedshot/seedshot.patch")
    s.set_defaults(fn=cmd_restore)

    s = sub.add_parser("apply", help="put a saved patch back in, starting a session if needed")
    s.add_argument("patch", nargs="?", help="default: .seedshot/seedshot.patch")
    s.set_defaults(fn=cmd_apply)

    args = p.parse_args()
    if not shutil.which("git"):
        die("git not found. Install Xcode Command Line Tools (xcode-select --install) or git.")
    args.fn(Project(args.project), args)


if __name__ == "__main__":
    main()
