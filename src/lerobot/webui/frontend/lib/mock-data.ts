import type { PortInfo, CameraInfo, StartResponse } from "./wizard-types";

export const ports: PortInfo[] = [
  {
    port: "/dev/tty.usbmodem5AB01799231",
    description: "Feetech Motor Controller",
    hwid: "USB VID:PID=1A86:55D4",
  },
  {
    port: "/dev/tty.usbmodem5AB01800861",
    description: "Feetech Motor Controller",
    hwid: "USB VID:PID=1A86:55D4",
  },
  {
    port: "/dev/tty.usbmodem5AB01799541",
    description: "Feetech Motor Controller",
    hwid: "USB VID:PID=1A86:55D4",
  },
  {
    port: "/dev/tty.usbmodem5AB01802741",
    description: "Feetech Motor Controller",
    hwid: "USB VID:PID=1A86:55D4",
  },
];

export const cameras: CameraInfo[] = [
  { opencvIndex: 0, label: "USB Camera" },
  { opencvIndex: 1, label: "Logitech C920" },
  { opencvIndex: 2, label: "USB 2.0 Camera" },
];

export const calibrationFiles: Record<string, string[]> = {
  "robots/so101_follower": [
    "left_follower.json",
    "right_follower.json",
    "right_follower_2.json",
  ],
  "teleoperators/so101_leader": ["left_leader.json", "right_leader.json"],
  "robots/bi_so101_follower": [
    "bimanual_follower_left.json",
    "bimanual_follower_right.json",
  ],
  "teleoperators/bi_so101_leader": [
    "bimanual_leader_left.json",
    "bimanual_leader_right.json",
  ],
};

export function startResponse(type: string): StartResponse {
  return {
    process_id: `mock-${type}-${Date.now()}`,
    message: `${type} started (mock)`,
  };
}
