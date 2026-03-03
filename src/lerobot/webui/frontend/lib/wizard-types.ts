// Robot mode
export type RobotMode = "single" | "bimanual";

// Port info from backend
export interface PortInfo {
  port: string;
  description: string | null;
  hwid: string | null;
}

// Camera info from browser MediaDevices API
export interface CameraInfo {
  deviceId: string;
  label: string;
  opencvIndex: number; // position in the full videoinput device list = OpenCV index
}

// Camera selection in wizard
export interface CameraSelection {
  deviceId: string;
  label: string; // original device label for display
  name: string; // "front_cam" | "hand_cam" | "side_cam"
  included: boolean;
  opencvIndex: number; // actual OpenCV camera index (preserved from full device list)
}

// Recording configuration
export interface RecordingConfig {
  repoId: string;
  task: string;
  numEpisodes: number;
  episodeTimeS: number;
  resetTimeS: number;
  displayData: boolean;
}

// API start response
export interface StartResponse {
  process_id: string;
  message: string;
}

// Wizard state
export interface WizardState {
  currentStep: number; // 0-5
  completedSteps: boolean[];

  // Step 0: Robot Type
  robotMode: RobotMode | null;

  // Step 1: Ports
  detectedPorts: PortInfo[];
  portAssignments: Record<string, string>; // role → port path

  // Step 2: Cameras
  detectedCameras: CameraInfo[];
  cameraSelections: CameraSelection[];

  // Step 3: Calibration
  calibrationFiles: Record<string, string[]>; // "robots/so101_follower" → filenames
  calibrationSelections: Record<string, string | null>; // role → filename or "new" or null
  newCalibrationNames: Record<string, string>; // role → user-entered name for new calibration

  // Step 4: Teleoperation
  teleProcessId: string | null;

  // Step 5: Recording
  recordingConfig: RecordingConfig;
  recordProcessId: string | null;
}

// Port roles by mode
export const SINGLE_PORT_ROLES = ["follower", "leader"] as const;
export const BIMANUAL_PORT_ROLES = [
  "left_follower",
  "right_follower",
  "left_leader",
  "right_leader",
] as const;

// Camera name options
export const CAMERA_NAME_OPTIONS = [
  "front_cam",
  "hand_cam",
  "side_cam",
] as const;

// Calibration directory mapping
export function getCalibrationPaths(mode: RobotMode): { role: string; category: string; robotType: string }[] {
  if (mode === "single") {
    return [
      { role: "follower", category: "robots", robotType: "so101_follower" },
      { role: "leader", category: "teleoperators", robotType: "so101_leader" },
    ];
  }
  return [
    { role: "left_follower", category: "robots", robotType: "bi_so101_follower" },
    { role: "right_follower", category: "robots", robotType: "bi_so101_follower" },
    { role: "left_leader", category: "teleoperators", robotType: "bi_so101_leader" },
    { role: "right_leader", category: "teleoperators", robotType: "bi_so101_leader" },
  ];
}

// Step definitions
export const STEPS = [
  { label: "Robot Type", description: "Choose your robot arm configuration" },
  { label: "Ports", description: "Detect and assign USB device ports" },
  { label: "Cameras", description: "Select and name your cameras" },
  { label: "Calibration", description: "Choose calibration for each arm" },
  { label: "Teleoperate", description: "Test robot teleoperation" },
  { label: "Record", description: "Record training data" },
] as const;

// Initial state
export const INITIAL_RECORDING_CONFIG: RecordingConfig = {
  repoId: "",
  task: "",
  numEpisodes: 10,
  episodeTimeS: 60,
  resetTimeS: 10,
  displayData: true,
};

export const INITIAL_STATE: WizardState = {
  currentStep: 0,
  completedSteps: [false, false, false, false, false, false],
  robotMode: null,
  detectedPorts: [],
  portAssignments: {},
  detectedCameras: [],
  cameraSelections: [],
  calibrationFiles: {},
  calibrationSelections: {},
  newCalibrationNames: {},
  teleProcessId: null,
  recordingConfig: { ...INITIAL_RECORDING_CONFIG },
  recordProcessId: null,
};
