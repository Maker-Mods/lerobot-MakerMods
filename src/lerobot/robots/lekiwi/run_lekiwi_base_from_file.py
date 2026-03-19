#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LeKiwi chassis control: read JSON command file and drive base motors.

Based on MakerMods_lekiwi.py — uses XLerobot + XLerobotConfig for:
  - Proper motor connection (bus1.connect)
  - Calibration (velocity mode, auto-calibration)
  - Configuration (OperatingMode.VELOCITY + enable_torque)
  - Kinematics (_from_keyboard_to_base_action / _body_to_wheel_raw)
  - Smooth acceleration/deceleration (SmoothLeKiwiController)

Usage:
  PYTHONPATH=src python -m lerobot.robots.lekiwi.run_lekiwi_base_from_file --port /dev/ttyACM0
  lerobot-lekiwi-base --port /dev/ttyACM0
"""

import argparse
import json
import os
import signal
import sys
import time

import numpy as np


def load_cmd(cmd_file: str) -> dict:
    """Read command JSON; return all-zero dict on missing/invalid file."""
    out = {
        "forward": False,
        "backward": False,
        "left": False,
        "right": False,
        "rotate_left": False,
        "rotate_right": False,
        "speed_index": 0,
    }
    if not os.path.isfile(cmd_file):
        return out
    try:
        with open(cmd_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return out
    for key in out:
        if key in data:
            if key == "speed_index":
                out[key] = max(0, min(2, int(data[key]) if data[key] is not None else 0))
            else:
                out[key] = bool(data[key])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LeKiwi base: read JSON command file and drive chassis via XLerobot."
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port for chassis")
    parser.add_argument(
        "--cmd-file",
        default=os.environ.get("LEROBOT_BASE_CMD_FILE", "/tmp/lerobot_base_cmd.json"),
        help="Path to JSON command file",
    )
    parser.add_argument("--wheel-radius", type=float, default=0.05)
    parser.add_argument("--base-radius", type=float, default=0.125)
    parser.add_argument(
        "--wheel-angles",
        default="0,240,120",
        help="Comma-separated wheel angles in degrees (default: 0,240,120 per MakerMods_lekiwi.py)",
    )
    args = parser.parse_args()

    wheel_angles = [int(a.strip()) for a in args.wheel_angles.split(",")]

    print(f"[LeKiwi base] Initializing XLerobot on {args.port} (motors 7/8/9)...", flush=True)
    print(f"[LeKiwi base] Wheel angles: {wheel_angles}, radius: {args.wheel_radius}, base_radius: {args.base_radius}", flush=True)

    # -- XLerobot + XLerobotConfig (same as MakerMods_lekiwi.py) --
    try:
        from lerobot.robots.xlerobot import XLerobotConfig, XLerobot
    except ImportError as e:
        print(f"[LeKiwi base] Cannot import XLerobot: {e}", flush=True)
        sys.exit(1)

    robot_config = XLerobotConfig(
        port1=args.port,
        port2=args.port,  # unused, same as port1 to avoid config error
        wheel_radius=args.wheel_radius,
        base_radius=args.base_radius,
        wheel_angles_deg=wheel_angles,
        cameras={},  # chassis-only, no cameras
    )

    try:
        robot = XLerobot(robot_config)
        robot.connect()
        print("[LeKiwi base] XLerobot connected and configured (VELOCITY mode).", flush=True)
    except Exception as e:
        msg = str(e)
        if "permission" in msg.lower() or "access" in msg.lower():
            print(
                f"[LeKiwi base] Cannot open port {args.port}: {e}\n"
                f"  → Run: sudo chmod 666 {args.port}",
                flush=True,
            )
        else:
            print(f"[LeKiwi base] Failed to connect: {e}", flush=True)
        sys.exit(1)

    print(f"[LeKiwi base] Reading commands from {args.cmd_file}", flush=True)

    def stop_and_exit() -> None:
        try:
            robot.stop_base()
            robot.disconnect()
        except Exception:
            pass
        print("[LeKiwi base] Stopped and disconnected.", flush=True)
        sys.exit(0)

    def sig_handler(_signum, _frame) -> None:
        stop_and_exit()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    try:
        while True:
            cmd = load_cmd(args.cmd_file)
            robot.speed_index = cmd["speed_index"]

            # Convert command booleans to pressed key strings (same as MakerMods_lekiwi.py keyboard flow)
            pressed = set()
            for direction in ("forward", "backward", "left", "right", "rotate_left", "rotate_right"):
                if cmd.get(direction):
                    pressed.add(robot.teleop_keys[direction])

            keyboard_keys = np.array(list(pressed))
            base_action = robot._from_keyboard_to_base_action(keyboard_keys) or {}
            robot.send_action(base_action)
            time.sleep(1.0 / 50)
    except Exception as e:
        print(f"[LeKiwi base] Error: {e}", flush=True)
    finally:
        stop_and_exit()


if __name__ == "__main__":
    main()
