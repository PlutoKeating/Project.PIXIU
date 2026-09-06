#!/usr/bin/env python3
"""Capture and operate an existing libvirt desktop; never synthesize UI results.

Requires virsh locally; SSH and GTK 3 Python bindings for X11 clipboard input.
Region capture additionally requires ImageMagick on the guest.
All guest/domain/output choices are explicit. Screenshot files are real pixels.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest", required=True, help="SSH destination")
    parser.add_argument("--domain", required=True, help="running libvirt domain")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("move", "click"):
        command = commands.add_parser(action)
        command.add_argument("x", type=int)
        command.add_argument("y", type=int)
    commands.add_parser("paste").add_argument("text")
    commands.add_parser("key").add_argument("codes", nargs="+", help="Linux KEY_* names")
    command = commands.add_parser("capture")
    command.add_argument("output", type=Path)
    command.add_argument("--region", help="ImageMagick live capture geometry")
    args = parser.parse_args()
    if args.width < 2 or args.height < 2:
        parser.error("display dimensions must both be at least 2")

    def ssh(command):
        return subprocess.run(["ssh", "-o", "BatchMode=yes", args.guest, command], check=True)

    def key(codes):
        subprocess.run(["virsh", "send-key", args.domain, "--codeset", "linux", *codes], check=True)

    if args.action in ("move", "click"):
        if not (0 <= args.x < args.width and 0 <= args.y < args.height):
            parser.error("coordinates must be inside the actual guest display")
        events = [
            {"type": "abs", "data": {"axis": "x", "value": round(args.x / (args.width - 1) * 32767)}},
            {"type": "abs", "data": {"axis": "y", "value": round(args.y / (args.height - 1) * 32767)}},
        ]
        subprocess.run(["virsh", "qemu-monitor-command", args.domain, json.dumps({
            "execute": "input-send-event", "arguments": {"events": events},
        })], check=True)
        if args.action == "click":
            for down in (True, False):
                time.sleep(0.15)
                subprocess.run(["virsh", "qemu-monitor-command", args.domain, json.dumps({
                    "execute": "input-send-event", "arguments": {"events": [
                        {"type": "btn", "data": {"button": "left", "down": down}},
                    ]},
                })], check=True)
            time.sleep(0.6)  # let native window/modal transitions settle
    elif args.action == "key":
        key(args.codes)
    elif args.action == "paste":
        # X11 clipboard only. Native Wayland may retain a different selection;
        # verify the visible field before submitting, or use its AT-SPI editor.
        # GTK owns the clipboard briefly; content goes only through the real UI.
        # Do not pass secrets: demo text is intentionally visible in process args.
        program = (
            "import gi,sys; gi.require_version('Gtk','3.0'); "
            "from gi.repository import Gtk,Gdk,GLib; "
            "c=Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD); c.set_text(sys.argv[1],-1); "
            "GLib.timeout_add_seconds(20,Gtk.main_quit); Gtk.main()"
        )
        ssh("DISPLAY=:0 GDK_BACKEND=x11 python3 -c " + shlex.quote(program)
            + " " + shlex.quote(args.text) + " >/dev/null 2>&1 </dev/null &")
        # Wait for ownership, not for any fabricated application response.
        time.sleep(1)
        key(["KEY_LEFTCTRL", "KEY_V"])
    else:
        if args.output.exists():
            parser.error("refusing to overwrite an existing screenshot")
        if not args.output.parent.is_dir():
            parser.error("output directory must already exist")
        if args.output.suffix.lower() != ".png":
            parser.error("output must have a .png extension")
        if not args.region:
            subprocess.run(["virsh", "screenshot", args.domain, str(args.output),
                            "--screen", "0"], check=True)
            if args.output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("capture is not a PNG")
            return
        # Capture bytes through a separate SSH connection, avoiding login banners
        # in the image stream; the temporary file has a unique, guest-owned path.
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", args.guest,
                                 "mktemp /var/tmp/pixiu-screen.XXXXXX.png"],
                                check=True, text=True, capture_output=True)
        remote = result.stdout.strip()
        if not remote.startswith("/var/tmp/pixiu-screen.") or "\n" in remote:
            raise RuntimeError("unexpected guest temporary path")
        try:
            command = "DISPLAY=:0 import -window root"
            if args.region:
                command += " -crop " + shlex.quote(args.region)
            ssh(command + " " + shlex.quote(remote))
            subprocess.run(["scp", "-q", args.guest + ":" + remote, str(args.output)], check=True)
            if args.output.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("capture is not a PNG")
        finally:
            ssh("rm -- " + shlex.quote(remote))


if __name__ == "__main__":
    main()
