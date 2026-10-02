#!/usr/bin/env python3
"""
Logitech MX Master 4 Linux Daemon
Handles Haptic Engine feedback (HID++ 0x19B0) and programmable thumb buttons.

Author: Yurko Gospodar (vivajarvis777-dev)
License: MIT
"""

import argparse
import configparser
import glob
import logging
import os
import re
import select
import signal
import subprocess
import sys
import time

DEFAULT_CONFIG_LOCATIONS = [
    os.path.expanduser("~/.config/mx4/config.ini"),
    os.path.abspath("./config.ini"),
    os.path.expanduser("~/.config/mx4-daemon.ini"),
]

# HID++ Protocol Constants
HIDPP_LONG_REPORT_ID = 0x11
HIDPP_DEVICE_INDEX = 0xFF
HIDPP_FEATURE_HAPTIC = 0x19B0
HIDPP_CMD_TRIGGER_HAPTIC = 0x4E

# Default feature index for MX Master 4 BLE firmware
DEFAULT_HAPTIC_FEATURE_INDEX = 0x0B

# Button HID++ Reprog Event Codes
CODE_WING_PANEL = 0x01A0       # Haptic thumb rest / wing panel
CODE_GESTURE_BUTTON = 0x00C3   # Button located above the thumb rest

logger = logging.getLogger("mx4-daemon")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Logitech MX Master 4 Haptic & Gesture Daemon for Linux"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file (default: ~/.config/mx4/config.ini)",
        default=None
    )
    parser.add_argument(
        "--test-haptic",
        type=int,
        metavar="WAVEFORM",
        nargs="?",
        const=2,
        help="Trigger a test haptic vibration pulse (1..14, default: 2) and exit"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Detect and display MX Master 4 hidraw interfaces and exit"
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable verbose debugging output"
    )
    return parser.parse_args()


def load_config(config_path=None):
    cfg = configparser.ConfigParser()
    found_path = None

    if config_path:
        if os.path.exists(config_path):
            found_path = config_path
        else:
            logger.warning("Specified config file not found: %s", config_path)
    else:
        for candidate in DEFAULT_CONFIG_LOCATIONS:
            if os.path.exists(candidate):
                found_path = candidate
                break

    if found_path:
        logger.info("Loading configuration from %s", found_path)
        cfg.read(found_path)
    else:
        logger.info("No config file found. Using built-in defaults.")

    config = {
        "debounce_sec": cfg.getfloat("daemon", "debounce_sec", fallback=0.40),
        "disable_x11_extra_buttons": cfg.getboolean("daemon", "disable_x11_extra_buttons", fallback=True),
        "default_waveform": cfg.getint("haptic", "default_waveform", fallback=2),
        "wing_action": cfg.get("wing_panel", "action", fallback="toggle_desktop"),
        "wing_waveform": cfg.getint("wing_panel", "haptic_waveform", fallback=2),
        "gesture_action": cfg.get("gesture_button", "action", fallback="/usr/local/bin/mx4-screenshot-menu"),
        "gesture_waveform": cfg.getint("gesture_button", "haptic_waveform", fallback=0),
    }

    # Resolve default screenshot script if path not directly found
    if config["gesture_action"] == "/usr/local/bin/mx4-screenshot-menu":
        user_script = os.path.expanduser("~/.local/bin/mx4-screenshot-menu")
        alt_script = os.path.expanduser("~/.local/bin/screenshot-to-clipboard")
        if os.path.isfile(user_script) and os.access(user_script, os.X_OK):
            config["gesture_action"] = user_script
        elif os.path.isfile(alt_script) and os.access(alt_script, os.X_OK):
            config["gesture_action"] = alt_script

    return config


def find_hidraw_devices():
    """Find all hidraw devices associated with MX Master 4."""
    matches = []
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent_file = os.path.join(path, "device/uevent")
            if os.path.exists(uevent_file):
                with open(uevent_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "046D:B042" in content.upper() or "MX MASTER 4" in content.upper():
                        dev_name = os.path.basename(path)
                        matches.append(f"/dev/{dev_name}")
        except Exception as e:
            logger.debug("Error checking %s: %e", path, e)

    # Fallback to standard hidraw endpoints if detection sysfs was inconclusive
    if not matches:
        for cand in ("/dev/hidraw2", "/dev/hidraw1", "/dev/hidraw0", "/dev/hidraw3"):
            if os.path.exists(cand):
                matches.append(cand)
                break

    return matches


def trigger_haptic(fd, waveform=2, feature_index=DEFAULT_HAPTIC_FEATURE_INDEX):
    """
    Send HID++ 0x19B0 haptic trigger report to MX Master 4.
    Waveform presets:
      0x01: Sharp Tick
      0x02: Subtle Click (Standard feedback)
      0x03..0x0E: Distinct pulse & click variants
    """
    if waveform <= 0:
        return
    try:
        report = bytes([
            HIDPP_LONG_REPORT_ID,
            HIDPP_DEVICE_INDEX,
            feature_index,
            HIDPP_CMD_TRIGGER_HAPTIC,
            waveform,
            0x00,
            0x00
        ] + [0x00] * 13)
        os.write(fd, report)
        logger.debug("Haptic waveform %d triggered (feature 0x%02X)", waveform, feature_index)
    except Exception as e:
        logger.error("Failed to write haptic command: %s", e)


def disable_extra_x11_buttons():
    """
    Disable buttons 10 and 11 in X11 pointer map to prevent desktop
    environments (e.g. Cinnamon window manager) from interpreting native gestures.
    """
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env or not env["DISPLAY"]:
            env["DISPLAY"] = ":0"

        cmd_list = subprocess.check_output(
            ["xinput", "list", "--short"],
            env=env,
            stderr=subprocess.DEVNULL
        ).decode()

        for line in cmd_list.splitlines():
            if "MX Master" in line and "pointer" in line:
                match = re.search(r"id=(\d+)", line)
                if match:
                    dev_id = match.group(1)
                    bmap = subprocess.check_output(
                        ["xinput", "get-button-map", dev_id],
                        env=env,
                        stderr=subprocess.DEVNULL
                    ).decode().split()

                    if len(bmap) >= 11:
                        # Clear button 10 (index 9) and button 11 (index 10)
                        bmap[9] = "0"
                        bmap[10] = "0"
                        subprocess.run(
                            ["xinput", "set-button-map", dev_id] + bmap,
                            env=env,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        logger.info("X11 pointer %s button map updated (disabled 10 & 11)", dev_id)
    except FileNotFoundError:
        logger.debug("xinput not installed; skipping X11 button map adjustment.")
    except Exception as e:
        logger.warning("Could not adjust X11 button map: %s", e)


def execute_action(action_str):
    """Execute a configured action string."""
    if not action_str or action_str.lower() == "none":
        return

    if action_str == "toggle_desktop":
        toggle_desktop()
    else:
        try:
            env = os.environ.copy()
            if "DISPLAY" not in env or not env["DISPLAY"]:
                env["DISPLAY"] = ":0"
            subprocess.Popen(action_str, shell=True, env=env)
            logger.info("Executed command: %s", action_str)
        except Exception as e:
            logger.error("Error running action '%s': %s", action_str, e)


def toggle_desktop():
    """Toggle showing desktop using wmctrl."""
    try:
        env = os.environ.copy()
        if "DISPLAY" not in env or not env["DISPLAY"]:
            env["DISPLAY"] = ":0"

        out = subprocess.check_output(
            ["wmctrl", "-m"],
            env=env,
            stderr=subprocess.DEVNULL
        ).decode()

        if 'showing the desktop" mode: OFF' in out:
            subprocess.run(["wmctrl", "-k", "on"], env=env, check=True)
            logger.info("Desktop mode set: ON")
        else:
            subprocess.run(["wmctrl", "-k", "off"], env=env, check=True)
            logger.info("Desktop mode set: OFF")
    except FileNotFoundError:
        logger.warning("wmctrl not found. Please install wmctrl (`sudo apt install wmctrl`).")
    except Exception as e:
        logger.error("Error toggling desktop via wmctrl: %s", e)


def run_daemon(config):
    running = True

    def sig_handler(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received (%s). Exiting...", signum)
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    logger.info("MX Master 4 Daemon active.")
    logger.info("Wing action: '%s' (haptic=%d)", config["wing_action"], config["wing_waveform"])
    logger.info("Gesture button action: '%s' (haptic=%d)", config["gesture_action"], config["gesture_waveform"])

    last_action_time = 0.0

    while running:
        devices = find_hidraw_devices()
        if not devices:
            time.sleep(2)
            continue

        device_path = devices[0]

        if config["disable_x11_extra_buttons"]:
            disable_extra_x11_buttons()

        try:
            logger.info("Opening interface %s...", device_path)
            fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            logger.error(
                "Permission denied opening %s. Ensure user is in 'plugdev' group or udev rule is installed.",
                device_path
            )
            time.sleep(5)
            continue
        except OSError as e:
            logger.warning("Failed to open %s (%s). Retrying in 2s...", device_path, e)
            time.sleep(2)
            continue

        try:
            logger.info("Connected to %s. Listening for HID++ reports...", device_path)
            while running:
                r, _, _ = select.select([fd], [], [], 1.5)
                if not r:
                    continue

                data = os.read(fd, 64)
                if len(data) >= 6 and data[0] == HIDPP_LONG_REPORT_ID:
                    key_code = (data[4] << 8) | data[5]
                    now = time.time()

                    if now - last_action_time > config["debounce_sec"]:
                        if key_code == CODE_WING_PANEL:
                            logger.info("Wing panel pressed (0x%04X)", key_code)
                            trigger_haptic(fd, waveform=config["wing_waveform"])
                            execute_action(config["wing_action"])
                            last_action_time = now

                        elif key_code == CODE_GESTURE_BUTTON:
                            logger.info("Gesture thumb button pressed (0x%04X)", key_code)
                            trigger_haptic(fd, waveform=config["gesture_waveform"])
                            execute_action(config["gesture_action"])
                            last_action_time = now

        except (OSError, IOError) as e:
            logger.info("Device disconnected or read error (%s). Reconnecting...", e)
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
            time.sleep(2)


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    if args.list_devices:
        devices = find_hidraw_devices()
        if devices:
            print("Found MX Master 4 hidraw interface(s):")
            for dev in devices:
                print(f"  - {dev}")
        else:
            print("No MX Master 4 interface detected.")
        sys.exit(0)

    if args.test_haptic is not None:
        devices = find_hidraw_devices()
        if not devices:
            print("Error: No MX Master 4 interface found to test haptic.", file=sys.stderr)
            sys.exit(1)
        waveform = args.test_haptic
        dev = devices[0]
        try:
            fd = os.open(dev, os.O_RDWR)
            print(f"Testing haptic waveform {waveform} on {dev}...")
            trigger_haptic(fd, waveform=waveform)
            os.close(fd)
            print("Done! You should have felt the haptic vibration.")
        except Exception as e:
            print(f"Failed to test haptic: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    config = load_config(args.config)
    run_daemon(config)


if __name__ == "__main__":
    main()
