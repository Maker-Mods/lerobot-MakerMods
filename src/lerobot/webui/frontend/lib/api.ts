// Types inlined from former types.ts (kept for real API usage when USE_MOCK=false)

interface CameraConfig {
  index: number;
  name: string;
  width: number;
  height: number;
  fps: number;
}

interface SingleArmConfig {
  follower_port: string | null;
  leader_port: string | null;
  cameras: CameraConfig[];
}

interface BimanualConfig {
  left_follower_port: string | null;
  left_leader_port: string | null;
  right_follower_port: string | null;
  right_leader_port: string | null;
  cameras: CameraConfig[];
}

interface LastRecordingConfig {
  repo_id: string | null;
  task: string | null;
  num_episodes: number;
  episode_time_s: number;
}

interface Config {
  mode: "single" | "bimanual";
  single_arm: SingleArmConfig;
  bimanual: BimanualConfig;
  last_recording: LastRecordingConfig;
}

type ProcessState = "not_started" | "running" | "stopped" | "error";

interface ProcessStatus {
  process_id: string;
  process_type: string;
  state: ProcessState;
  pid: number | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_seconds: number | null;
  error_message: string | null;
}

interface CalibrationStatus {
  device_type: string;
  device_id: string;
  robot_type: string;
  port: string | null;
  is_calibrated: boolean;
  calibration_path: string | null;
}

interface HFLoginStatus {
  is_logged_in: boolean;
  username: string | null;
}

interface SystemStatus {
  active_processes: ProcessStatus[];
  hf_status: HFLoginStatus;
  missing_calibrations: CalibrationStatus[];
}

interface PortInfo {
  port: string;
  description: string | null;
  hwid: string | null;
}

interface CameraInfo {
  index: number;
  name: string | null;
  backend: string;
  is_builtin: boolean;
}

interface CameraPreview {
  index: number;
  image_path: string;
  image_url: string;
}

interface RecordingRequest {
  repo_id: string;
  single_task: string;
  num_episodes: number;
  episode_time_s: number;
  display_data: boolean;
}

interface HFRepoInfo {
  repo_id: string;
  repo_type: string;
  private: boolean;
  url: string | null;
}

interface StartResponse {
  process_id: string;
  message: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API Error: ${res.status}`);
  }

  return res.json();
}

// Config
export const api = {
  config: {
    get: () => fetchAPI<Config>("/api/config/"),
    save: (config: Config) =>
      fetchAPI<Config>("/api/config/", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    reset: () => fetchAPI<Config>("/api/config/", { method: "DELETE" }),
  },

  setup: {
    listPorts: () => fetchAPI<PortInfo[]>("/api/setup/ports"),
    listCameras: (excludeBuiltin?: boolean) =>
      fetchAPI<CameraInfo[]>(
        `/api/setup/cameras${excludeBuiltin ? "?exclude_builtin=true" : ""}`
      ),
    capturePreviews: (indices?: number[]) =>
      fetchAPI<Record<number, CameraPreview>>("/api/setup/cameras/preview", {
        method: "POST",
        body: JSON.stringify(indices ?? null),
      }),
    getPreviewUrl: (index: number) =>
      `${API_BASE}/api/setup/cameras/preview/${index}`,
  },

  calibration: {
    getStatus: () =>
      fetchAPI<CalibrationStatus[]>("/api/calibration/status"),
    getMissing: () =>
      fetchAPI<CalibrationStatus[]>("/api/calibration/missing"),
    start: (params: {
      device_type: string;
      device_id: string;
      robot_type: string;
      port: string;
    }) =>
      fetchAPI<StartResponse>("/api/calibration/start", {
        method: "POST",
        body: JSON.stringify(params),
      }),
    stop: (processId: string) =>
      fetchAPI<{ message: string }>(`/api/calibration/stop/${processId}`, {
        method: "POST",
      }),
  },

  teleoperation: {
    start: (params: { display_data: boolean }) =>
      fetchAPI<StartResponse>("/api/teleoperation/start", {
        method: "POST",
        body: JSON.stringify(params),
      }),
    stop: (processId: string) =>
      fetchAPI<{ message: string }>(`/api/teleoperation/stop/${processId}`, {
        method: "POST",
      }),
    getStatus: (processId: string) =>
      fetchAPI<ProcessStatus>(`/api/teleoperation/status/${processId}`),
  },

  recording: {
    start: (params: RecordingRequest) =>
      fetchAPI<StartResponse>("/api/recording/start", {
        method: "POST",
        body: JSON.stringify(params),
      }),
    stop: (processId: string) =>
      fetchAPI<{ message: string }>(`/api/recording/stop/${processId}`, {
        method: "POST",
      }),
    getStatus: (processId: string) =>
      fetchAPI<ProcessStatus>(`/api/recording/status/${processId}`),
    clearCache: (repoId: string) =>
      fetchAPI<{ message: string }>(
        `/api/recording/cache?repo_id=${encodeURIComponent(repoId)}`,
        { method: "DELETE" }
      ),
  },

  huggingface: {
    whoami: () => fetchAPI<HFLoginStatus>("/api/huggingface/whoami"),
    listRepos: () => fetchAPI<HFRepoInfo[]>("/api/huggingface/repos"),
    createRepo: (repoName: string, isPrivate: boolean = false) =>
      fetchAPI<HFRepoInfo>("/api/huggingface/repos", {
        method: "POST",
        body: JSON.stringify({ repo_name: repoName, private: isPrivate }),
      }),
  },

  system: {
    getStatus: () => fetchAPI<SystemStatus>("/api/system/status"),
  },
};
