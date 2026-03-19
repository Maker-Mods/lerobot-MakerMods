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
仅 LeKiwi 底盘键盘遥操作（与 4_xlerobot_teleop_keyboard 相同键位）
- 键位：i 前 k 后 j 左 l 右 u 左转 o 右转，n 加速 m 减速
- 直接连接 /dev/ttyACM0 上的 7/8/9 号舵机，无需 ZMQ、无需机械臂
- 需先 chmod 或加入 dialout：sudo chmod 666 /dev/ttyACM0

底盘控制逻辑来源于本包 lekiwi_base_control.py（与 Web UI 底盘共用）。

运行（在项目根或 XLeRobot/software 目录）：
  PYTHONPATH=src python -m lerobot.robots.lekiwi.run_lekiwi_keyboard_only
  PYTHONPATH=src python -m lerobot.robots.lekiwi.run_lekiwi_keyboard_only --port /dev/ttyACM0
或安装后：
  lerobot-lekiwi-keyboard
"""

import argparse
import sys
import time

# 底盘控制逻辑：本包统一来源（与 Web UI 从文件读命令的 runner 共用）
from lerobot.robots.lekiwi.lekiwi_base_control import (
    MinimalLeKiwiRobot,
    SmoothLeKiwiController,
    TELEOP_KEYS,
    SPEED_LEVELS,
)

# 电机与键盘：优先本仓库 lerobot.motors，若无则回退到 lerobot_new（兼容旧环境）
try:
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
except ImportError:
    sys.path.insert(0, "/home/lakesenberg/lerobot_new/src")
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

from lerobot.teleoperators.keyboard.teleop_keyboard import KeyboardTeleop
from lerobot.teleoperators.keyboard.configuration_keyboard import KeyboardTeleopConfig


def main():
    parser = argparse.ArgumentParser(
        description="LeKiwi 底盘键盘遥操作（键位同 4_xlerobot_teleop_keyboard）"
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="舵机串口")
    args = parser.parse_args()

    print(f"[LeKiwi] 连接 {args.port}（电机 7/8/9）...")
    bus = FeetechMotorsBus(
        port=args.port,
        motors={
            "base_left_wheel": Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
            "base_back_wheel": Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
            "base_right_wheel": Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
        },
    )
    bus.connect()
    for name in ["base_left_wheel", "base_back_wheel", "base_right_wheel"]:
        bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)
    bus.enable_torque()
    print("[LeKiwi] 底盘就绪（VELOCITY 模式）。键位: i/k 前后 j/l 左右 u/o 旋转 n/m 调速 b 退出")

    robot = MinimalLeKiwiRobot(bus, args.port)
    smooth = SmoothLeKiwiController()
    keyboard = KeyboardTeleop(KeyboardTeleopConfig())
    keyboard.connect()

    try:
        while True:
            pressed = set(keyboard.get_action().keys())
            if "b" in pressed or "B" in pressed:
                print("[LeKiwi] 退出")
                break
            if "n" in pressed or "N" in pressed:
                robot.speed_index = min(robot.speed_index + 1, 2)
            if "m" in pressed or "M" in pressed:
                robot.speed_index = max(robot.speed_index - 1, 0)
            base_action = smooth.update(pressed, robot)
            robot.send_action(base_action)
            time.sleep(1.0 / 50)
    finally:
        bus.sync_write(
            "Goal_Velocity",
            {"base_left_wheel": 0, "base_back_wheel": 0, "base_right_wheel": 0},
        )
        bus.disconnect()
        keyboard.disconnect()
        print("[LeKiwi] 已停车并断开。")


if __name__ == "__main__":
    main()
