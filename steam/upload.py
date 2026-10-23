"""Upload dist/ to Steam with SteamCMD.

    python steam/upload.py            render the .vdf files and upload
    python steam/upload.py --dry-run  render only, print what would run

Reads these environment variables (a steam/.env file works too, one
KEY=value per line; it is git-ignored only if you add it, so do):

    STEAM_USERNAME       the Steam account that uploads builds (required)
    STEAM_APP_ID         your App ID (required)
    STEAM_DEPOT_WINDOWS  usually App ID + 1 (required)
    STEAM_DEPOT_LINUX    leave empty to skip the Linux depot
    STEAM_DEPOT_DLC      leave empty to skip the DLC depot
    STEAM_BRANCH         beta branch to set live, e.g. "beta". Empty = upload only.
                         "default" is refused: Steam does not allow it from SteamCMD.
    BUILD_DESC           shown next to the build in Steamworks
    STEAMCMD             path to steamcmd(.exe/.sh); default: found on PATH

The first login on a machine asks for your password and a Steam Guard
confirmation. SteamCMD then caches the login in its config/config.vdf and
later runs need only the username.
"""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "build")
TEMPLATES = ["app_build.vdf", "depot_build_windows.vdf", "depot_build_linux.vdf", "depot_build_dlc.vdf"]


def load_env_file():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def var(name, required=False):
    v = os.environ.get(name, "").strip()
    if required and not v:
        sys.exit(f"missing {name}: set it in the environment or steam/.env")
    return v


def render(text, values):
    return re.sub(r"\$\{(\w+)\}", lambda m: values.get(m.group(1), ""), text)


def main():
    load_env_file()
    dry = "--dry-run" in sys.argv
    values = {
        "STEAM_APP_ID": var("STEAM_APP_ID", True),
        "STEAM_DEPOT_WINDOWS": var("STEAM_DEPOT_WINDOWS", True),
        "STEAM_DEPOT_LINUX": var("STEAM_DEPOT_LINUX"),
        "STEAM_DEPOT_DLC": var("STEAM_DEPOT_DLC"),
        "STEAM_BRANCH": var("STEAM_BRANCH"),
        "BUILD_DESC": var("BUILD_DESC") or time.strftime("build %Y-%m-%d %H:%M"),
    }
    if values["STEAM_BRANCH"] == "default":
        sys.exit("STEAM_BRANCH=default is not allowed by SteamCMD; set the build live on default in Steamworks.")
    if not os.path.isdir(os.path.join(ROOT, "dist", "windows")):
        sys.exit("dist/windows is missing: build the game first (see README, 'Build the Steam binaries').")

    os.makedirs(OUT, exist_ok=True)
    for name in TEMPLATES:
        text = render(open(os.path.join(HERE, name), encoding="utf-8").read(), values)
        if name == "app_build.vdf":
            lines = []
            for line in text.splitlines():
                # Drop depots that are not configured; switch the DLC depot on when it is.
                if '"" "depot_build_' in line:
                    continue
                if values["STEAM_DEPOT_DLC"] and '"depot_build_dlc.vdf"' in line:
                    line = line.replace("// ", "", 1)
                lines.append(line)
            text = "\n".join(lines) + "\n"
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(text)
    app_build = os.path.join(OUT, "app_build.vdf")
    print(open(app_build, encoding="utf-8").read())

    steamcmd = var("STEAMCMD") or shutil.which("steamcmd") or shutil.which("steamcmd.sh") or shutil.which("steamcmd.exe")
    cmd = [
        steamcmd or "steamcmd",
        "+@ShutdownOnFailedCommand", "1",
        # In CI there is nobody to type a password: fail instead of hanging.
        *(["+@NoPromptForPassword", "1"] if os.environ.get("CI") else []),
        "+login", var("STEAM_USERNAME", True),
        "+run_app_build", app_build,
        "+quit",
    ]
    print(" ".join(cmd))
    if dry:
        return
    if not steamcmd:
        sys.exit("steamcmd not found: install it (https://developer.valvesoftware.com/wiki/SteamCMD) or set STEAMCMD")
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
