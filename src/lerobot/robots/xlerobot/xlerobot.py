#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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

import logging
import time
from functools import cached_property
from itertools import chain
from typing import Any

import numpy as np

from lerobot.cameras.utils import make_cameras_from_configs
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import (
    FeetechMotorsBus,
    OperatingMode,
)

from ..robot import Robot
from ..utils import ensure_safe_goal_position
from .config_xlerobot import XLerobotConfig
from .lekiwi_base_controller import SmoothLeKiwiController

logger = logging.getLogger(__name__)


class XLerobot(Robot):
    """
    The robot includes a three omniwheel mobile base and a remote follower arm.
    The leader arm is connected locally (on the laptop) and its joint positions are recorded and then
    forwarded to the remote follower arm (after applying a safety clamp).
    In parallel, keyboard teleoperation is used to generate raw velocity commands for the wheels.
    """

    config_class = XLerobotConfig
    name = "xlerobot"

    def __init__(self, config: XLerobotConfig):
        super().__init__(config)
        self.config = config
        self.teleop_keys = config.teleop_keys
        self.speed_levels = [
            {"xy": 0.1, "theta": 30},  # 慢速
            {"xy": 0.2, "theta": 60},  # 中速
            {"xy": 0.3, "theta": 90},  # 快速
        ]
        self.speed_index = 0
        self._lekiwi_smooth_controller = SmoothLeKiwiController()

        # 仅底盘模式：三个轮子电机全部挂在 port1 (/dev/ttyACM0)
        # 默认 ID 7/8/9（与原 XLeRobot 右臂总线一致）；
        # 若底盘电机被单独烧录为 1/2/3，请改为 Motor(1,...) Motor(2,...) Motor(3,...)
        cal_base = {k: v for k, v in self.calibration.items()
                    if k in ("base_left_wheel", "base_back_wheel", "base_right_wheel")}
        self.bus1 = FeetechMotorsBus(
            port=self.config.port1,
            motors={
                "base_left_wheel":  Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_back_wheel":  Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_right_wheel": Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
            },
            calibration=cal_base if cal_base else self.calibration,
        )
        self.left_arm_motors = []
        self.right_arm_motors = []
        self.head_motors = []
        self.base_motors = [m for m in self.bus1.motors if m.startswith("base")]
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def _state_ft(self) -> dict[str, type]:
        # 仅底盘模式：只有底盘速度状态
        return dict.fromkeys(("x.vel", "y.vel", "theta.vel"), float)

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3) for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._state_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._state_ft

    @property
    def is_connected(self) -> bool:
        return self.bus1.is_connected and all(
            cam.is_connected for cam in self.cameras.values()
        )

    def connect(self, calibrate: bool = True) -> None:
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        self.bus1.connect()

        # 底盘轮子使用速度模式，无需位置标定；直接写入默认标定值即可
        self.calibrate()

        for cam in self.cameras.values():
            cam.connect()

        self.configure()
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        return self.bus1.is_calibrated

    def calibrate(self) -> None:
        """底盘轮子使用速度模式，无需位置标定。
        此处自动写入全范围默认标定，homing_offset=0，range=0-4095。
        """
        logger.info("底盘模式：写入默认速度标定（无需手动操作）")
        cal = {}
        for name, motor in self.bus1.motors.items():
            cal[name] = MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=0,
                range_min=0,
                range_max=4095,
            )
        self.bus1.write_calibration(cal)
        self.calibration = cal
        self._save_calibration()
        logger.info("底盘标定完成")
        

    def configure(self):
        """底盘模式：配置三个轮子为速度控制模式。"""
        self.bus1.disable_torque()
        self.bus1.configure_motors()
        for name in self.base_motors:
            self.bus1.write("Operating_Mode", name, OperatingMode.VELOCITY.value)
        self.bus1.enable_torque()
        

    def setup_motors(self) -> None:
        """底盘模式：仅设置三个轮子电机 ID。"""
        for motor in reversed(self.base_motors):
            input(f"Connect the controller board to the '{motor}' motor only and press enter.")
            self.bus1.setup_motor(motor)
            print(f"'{motor}' motor id set to {self.bus1.motors[motor].id}")
        

    @staticmethod
    def _degps_to_raw(degps: float) -> int:
        steps_per_deg = 4096.0 / 360.0
        speed_in_steps = degps * steps_per_deg
        speed_int = int(round(speed_in_steps))
        # Cap the value to fit within signed 16-bit range (-32768 to 32767)
        if speed_int > 0x7FFF:
            speed_int = 0x7FFF  # 32767 -> maximum positive value
        elif speed_int < -0x8000:
            speed_int = -0x8000  # -32768 -> minimum negative value
        return speed_int

    @staticmethod
    def _raw_to_degps(raw_speed: int) -> float:
        steps_per_deg = 4096.0 / 360.0
        magnitude = raw_speed
        degps = magnitude / steps_per_deg
        return degps


    def _get_wheel_kinematics_matrix(self, base_radius: float) -> "np.ndarray":
        """构建三万向轮运动学矩阵（标准全向轮公式）。

        物理布局（以机器人正前方为 φ=0°，逆时针为正）：
          φ=0°  ：前轮（横向被动滚轮，前进时不转，横向移动时主动转）
          φ=120°：左后轮（斜向驱动，约偏后 30°）
          φ=240°：右后轮（斜向驱动，约偏后 30°）

        标准公式：v_wheel_i = -sin(φ_i)*vx + cos(φ_i)*vy + R*ω
        矩阵每行：[-sin(φ_i), cos(φ_i), base_radius]

        验证（前进 vx=1, vy=0, ω=0）：
          前轮(φ=0°)   : 0         → 被动滚轮滑行 ✓
          左后轮(φ=120°): -√3/2    → 向后旋转提供前向力 ✓
          右后轮(φ=240°): +√3/2    → 向前旋转提供前向力 ✓

        修改轮子布局时只需在 XLerobotConfig 中更新 wheel_angles_deg 即可。
        """
        angles = np.radians(np.array(self.config.wheel_angles_deg))
        return np.array([[-np.sin(a), np.cos(a), base_radius] for a in angles])

    def _body_to_wheel_raw(
        self,
        x: float,
        y: float,
        theta: float,
        max_raw: int = 3000,
    ) -> dict:
        """将底盘体坐标系速度指令转换为三轮原始速度命令。

        参数：
          x     : x 方向线速度 (m/s)
          y     : y 方向线速度 (m/s)
          theta : 自转角速度 (deg/s)
          max_raw: 单个轮允许的最大原始命令值（超出则等比缩放）

        返回：
          {"base_left_wheel": int, "base_back_wheel": int, "base_right_wheel": int}
        """
        wheel_radius = self.config.wheel_radius
        base_radius = self.config.base_radius

        # theta: deg/s → rad/s
        theta_rad = theta * (np.pi / 180.0)
        velocity_vector = np.array([x, y, theta_rad])

        # 运动学矩阵：v_wheel = M · [vx, vy, omega_rad]
        m = self._get_wheel_kinematics_matrix(base_radius)
        wheel_linear_speeds = m.dot(velocity_vector)
        wheel_angular_speeds = wheel_linear_speeds / wheel_radius

        # rad/s → deg/s
        wheel_degps = wheel_angular_speeds * (180.0 / np.pi)

        # 若超出 max_raw 限制则等比缩放
        steps_per_deg = 4096.0 / 360.0
        raw_floats = [abs(degps) * steps_per_deg for degps in wheel_degps]
        max_raw_computed = max(raw_floats)
        if max_raw_computed > max_raw:
            wheel_degps = wheel_degps * (max_raw / max_raw_computed)

        wheel_raw = [self._degps_to_raw(deg) for deg in wheel_degps]

        return {
            "base_left_wheel": wheel_raw[0],
            "base_back_wheel": wheel_raw[1],
            "base_right_wheel": wheel_raw[2],
        }

    def _wheel_raw_to_body(
        self,
        left_wheel_speed,
        back_wheel_speed,
        right_wheel_speed,
    ) -> "dict[str, Any]":
        """将三轮原始速度反解为底盘体坐标系速度（逆运动学）。

        返回：{"x.vel": float, "y.vel": float, "theta.vel": float}（单位 m/s 和 deg/s）
        """
        wheel_radius = self.config.wheel_radius
        base_radius = self.config.base_radius

        wheel_degps = np.array([
            self._raw_to_degps(left_wheel_speed),
            self._raw_to_degps(back_wheel_speed),
            self._raw_to_degps(right_wheel_speed),
        ])

        # deg/s → rad/s → 线速度 m/s
        wheel_linear_speeds = wheel_degps * (np.pi / 180.0) * wheel_radius

        # 逆运动学：[vx, vy, omega_rad] = M⁻¹ · v_wheel
        m = self._get_wheel_kinematics_matrix(base_radius)
        m_inv = np.linalg.inv(m)
        velocity_vector = m_inv.dot(wheel_linear_speeds)
        x, y, theta_rad = velocity_vector

        return {
            "x.vel": x,
            "y.vel": y,
            "theta.vel": theta_rad * (180.0 / np.pi),
        }

    def _from_keyboard_to_base_action(self, pressed_keys: np.ndarray):
        """LeKiwi 三轮底盘：速度档位 + 平滑加减速，前后端共用同一套逻辑。"""
        # 速度档位由 n/m 键更新
        if self.teleop_keys["speed_up"] in pressed_keys:
            self.speed_index = min(self.speed_index + 1, 2)
        if self.teleop_keys["speed_down"] in pressed_keys:
            self.speed_index = max(self.speed_index - 1, 0)
        return self._lekiwi_smooth_controller.update(set(pressed_keys), self)

    def get_observation(self) -> dict[str, Any]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        start = time.perf_counter()
        base_wheel_vel = self.bus1.sync_read("Present_Velocity", self.base_motors)
        base_vel = self._wheel_raw_to_body(
            base_wheel_vel["base_left_wheel"],
            base_wheel_vel["base_back_wheel"],
            base_wheel_vel["base_right_wheel"],
        )
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read state: {dt_ms:.1f}ms")

        camera_obs = self.get_camera_observation()
        return {**base_vel, **camera_obs}
    
    def get_camera_observation(self):
        obs_dict = {}
        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.async_read()
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read {cam_key}: {dt_ms:.1f}ms")
        
        return obs_dict

    def send_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """底盘模式：仅下发轮子速度指令。"""
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        base_goal_vel = {k: v for k, v in action.items() if k.endswith(".vel")}
        base_wheel_goal_vel = self._body_to_wheel_raw(
            base_goal_vel.get("x.vel", 0.0),
            base_goal_vel.get("y.vel", 0.0),
            base_goal_vel.get("theta.vel", 0.0),
        )
        if base_wheel_goal_vel:
            self.bus1.sync_write("Goal_Velocity", base_wheel_goal_vel)
        return base_goal_vel

    def stop_base(self):
        self.bus1.sync_write("Goal_Velocity", dict.fromkeys(self.base_motors, 0), num_retry=5)
        logger.info("底盘电机已停止")

    def disconnect(self):
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        self.stop_base()
        self.bus1.disconnect(self.config.disable_torque_on_disconnect)
        for cam in self.cameras.values():
            cam.disconnect()

        logger.info(f"{self} disconnected.")
