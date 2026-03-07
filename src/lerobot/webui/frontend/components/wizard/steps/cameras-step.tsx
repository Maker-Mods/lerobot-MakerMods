"use client";

import { useState, useCallback } from "react";
import { Loader2, Camera } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CAMERA_NAME_OPTIONS } from "@/lib/wizard-types";
import { services } from "@/lib/services";
import { useWizard } from "../wizard-provider";
import { StepCard } from "../step-card";

/** Live camera feed via the backend MJPEG stream (same OpenCV source as recording). */
function CameraFeed({ opencvIndex }: { opencvIndex: number }) {
  // Unique timestamp per mount forces a fresh MJPEG connection
  const [ts] = useState(() => Date.now());
  return (
    <div className="border-t bg-muted/30 p-2">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/api/setup/cameras/stream/${opencvIndex}?t=${ts}`}
        alt={`Camera ${opencvIndex}`}
        className="w-full rounded"
      />
    </div>
  );
}

export function CamerasStep() {
  const { state, dispatch } = useWizard();
  const [detecting, setDetecting] = useState(false);

  const selectedCameras = state.cameraSelections.filter((c) => c.included);
  // Allow continuing with no cameras, but if any are selected they must be named
  const allNamed =
    selectedCameras.length === 0 || selectedCameras.every((c) => c.name !== "");

  // Names already used by other cameras
  const getUsedNames = useCallback(
    (excludeIndex: number): Set<string> => {
      const used = new Set<string>();
      for (const cam of state.cameraSelections) {
        if (cam.opencvIndex !== excludeIndex && cam.included && cam.name) {
          used.add(cam.name);
        }
      }
      return used;
    },
    [state.cameraSelections]
  );

  async function detectCameras() {
    setDetecting(true);
    try {
      // Use backend OpenCV detection — returns ground-truth camera indices
      const cameras = await services.listCameras();
      dispatch({ type: "SET_DETECTED_CAMERAS", cameras });
    } catch (err) {
      console.error("Failed to detect cameras", err);
    } finally {
      setDetecting(false);
    }
  }

  return (
    <StepCard
      title="Select Cameras"
      description="Detect cameras, toggle each on to see its live feed, then assign a name. Skip your built-in camera."
      nextDisabled={!allNamed}
    >
      <div className="space-y-6">
        <Button
          variant="outline"
          onClick={detectCameras}
          disabled={detecting}
          className="w-full"
        >
          {detecting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Camera className="mr-2 h-4 w-4" />
          )}
          {detecting ? "Detecting..." : "Detect Cameras"}
        </Button>

        {state.cameraSelections.length > 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {state.cameraSelections.length} camera(s) found. Select which to
              include:
            </p>
            {state.cameraSelections.map((cam) => {
              const usedNames = getUsedNames(cam.opencvIndex);
              return (
                <div
                  key={cam.opencvIndex}
                  className="overflow-hidden rounded-lg border"
                >
                  <div className="flex items-center gap-4 p-4">
                    <Switch
                      checked={cam.included}
                      onCheckedChange={(checked) =>
                        dispatch({
                          type: "TOGGLE_CAMERA",
                          opencvIndex: cam.opencvIndex,
                          included: checked,
                        })
                      }
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{cam.label}</p>
                    </div>
                    {cam.included && (
                      <div className="w-40">
                        <Select
                          value={cam.name || ""}
                          onValueChange={(name) =>
                            dispatch({
                              type: "SET_CAMERA_NAME",
                              opencvIndex: cam.opencvIndex,
                              name,
                            })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Name..." />
                          </SelectTrigger>
                          <SelectContent>
                            {CAMERA_NAME_OPTIONS.filter(
                              (n) => !usedNames.has(n)
                            ).map((name) => (
                              <SelectItem key={name} value={name}>
                                {name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>
                  {cam.included && <CameraFeed opencvIndex={cam.opencvIndex} />}
                </div>
              );
            })}
          </div>
        )}

        {state.cameraSelections.length === 0 && !detecting && (
          <p className="text-center text-sm text-muted-foreground">
            Click &quot;Detect Cameras&quot; to find connected cameras.
          </p>
        )}
      </div>
    </StepCard>
  );
}
