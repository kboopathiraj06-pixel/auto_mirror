"""
AutoMirror – AI Driver-Based Side Mirror Adjustment System
==========================================================
Backend: Flask + MediaPipe Face Mesh + OpenCV

MediaPipe gives us 468 3-D facial landmarks for:
  • Head yaw  (left/right rotation)
  • Head pitch (up/down tilt)
  • Eye gaze  (refined from inner/outer/upper/lower lids)

India RHD:  left mirror 1.4×  |  right mirror 0.6×

ESP32 servo-motor output: /api/servo_angles
  returns { left_h, left_v, right_h, right_v }
  all in degrees, ready to map directly to servo PWM.
"""

import cv2
import json
import math
import os
import time
import threading
import numpy as np
import mediapipe as mp
from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", template_folder="templates")

# ──────────────────────────────────────────────
#  MediaPipe setup
# ──────────────────────────────────────────────
mp_face_mesh = mp.solutions.face_mesh
mp_drawing   = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Landmark index groups (MediaPipe canonical)
# Left eye (from driver's own perspective ≡ camera-left)
L_EYE_INNER  = 133   # medial canthus
L_EYE_OUTER  = 33    # lateral canthus
L_EYE_TOP    = 159
L_EYE_BOT    = 145

# Right eye
R_EYE_INNER  = 362
R_EYE_OUTER  = 263
R_EYE_TOP    = 386
R_EYE_BOT    = 374

# Head geometry anchors
NOSE_TIP     = 1
CHIN         = 152
L_CHEEK      = 234
R_CHEEK      = 454
FOREHEAD     = 10

# ──────────────────────────────────────────────
#  Global state
# ──────────────────────────────────────────────
camera       = None
camera_lock  = threading.Lock()
frame_buffer = None
buffer_lock  = threading.Lock()
detection_running = False

mirror_state = {
    "left":  {"h": 0.0, "v": 0.0},
    "right": {"h": 0.0, "v": 0.0},
    # Normalised eye mid-point (0-1)
    "eye_x": 0.5, "eye_y": 0.5,
    # Head angles in degrees (MediaPipe estimation)
    "head_yaw":   0.0,   # + = looking right
    "head_pitch": 0.0,   # + = looking down
    "head_roll":  0.0,   # + = tilting right
    "face_detected":  False,
    "landmarks_count": 0,
    "calibrated": False,
    # ESP32-ready servo angles
    "servo": {"left_h": 90, "left_v": 90, "right_h": 90, "right_v": 90},
}
calibration_data = {
    "eye_x": 0.5,  "eye_y": 0.5,
    "yaw":   0.0,  "pitch": 0.0,
}

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")

# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def load_profiles():
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE) as f:
            return json.load(f)
    return {}

def save_profiles(profiles):
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def angle_to_servo(angle_deg, centre=90, scale=185/25):
    """Convert mirror angle (−25..+25°) → servo PWM (0..180°)."""
    return int(clamp(centre + angle_deg * scale, 0, 180))

def compute_mirror_angles(yaw, pitch, cal_yaw, cal_pitch):
    """
    India RHD:
      left  mirror → 1.4× sensitivity (driver's side)
      right mirror → 0.6× sensitivity (passenger side)
    yaw/pitch in degrees; output clamped to ±25° / ±20°
    """
    dy = yaw   - cal_yaw
    dp = pitch - cal_pitch

    left_h  = clamp(dy * 1.4, -25, 25)
    right_h = clamp(dy * 0.6, -25, 25)
    left_v  = clamp(dp * 1.4, -20, 20)
    right_v = clamp(dp * 0.6, -20, 20)

    return left_h, left_v, right_h, right_v

def lm(landmarks, idx, w, h):
    """Return pixel (x,y) for landmark index."""
    p = landmarks[idx]
    return int(p.x * w), int(p.y * h)

def lm_norm(landmarks, idx):
    """Return normalised (x,y) for landmark index."""
    p = landmarks[idx]
    return p.x, p.y

def estimate_head_angles(landmarks, img_w, img_h):
    """
    Lightweight head-pose estimation from facial landmarks.
    Returns (yaw, pitch, roll) in degrees.

    Yaw   – nose deviation left/right from eye-midpoint
    Pitch – nose elevation relative to eye-line
    Roll  – eye tilt
    """
    # Key points (normalised)
    le_x, le_y = (lm_norm(landmarks, L_EYE_INNER)[0] + lm_norm(landmarks, L_EYE_OUTER)[0]) / 2, \
                 (lm_norm(landmarks, L_EYE_INNER)[1] + lm_norm(landmarks, L_EYE_INNER)[1]) / 2
    re_x, re_y = (lm_norm(landmarks, R_EYE_INNER)[0] + lm_norm(landmarks, R_EYE_OUTER)[0]) / 2, \
                 (lm_norm(landmarks, R_EYE_INNER)[1] + lm_norm(landmarks, R_EYE_OUTER)[1]) / 2

    eye_mid_x = (le_x + re_x) / 2
    eye_mid_y = (le_y + re_y) / 2

    nose_x, nose_y   = lm_norm(landmarks, NOSE_TIP)
    chin_x, chin_y   = lm_norm(landmarks, CHIN)
    lc_x,  _         = lm_norm(landmarks, L_CHEEK)
    rc_x,  _         = lm_norm(landmarks, R_CHEEK)

    face_width = abs(rc_x - lc_x) or 0.001

    # Yaw: nose X offset from eye-midpoint, normalised by face width
    yaw_raw   = (nose_x - eye_mid_x) / face_width
    yaw_deg   = yaw_raw * 90          # empirical scale

    # Pitch: nose is below eyes normally; if driver tilts head down, nose_y increases
    face_vert = abs(chin_y - eye_mid_y) or 0.001
    pitch_raw = (nose_y - eye_mid_y) / face_vert - 0.5   # 0 = neutral
    pitch_deg = pitch_raw * 60

    # Roll: angle of eye-to-eye line
    eye_dx = re_x - le_x
    eye_dy = re_y - le_y
    roll_deg = math.degrees(math.atan2(eye_dy, eye_dx))

    return yaw_deg, pitch_deg, roll_deg

def get_camera():
    global camera
    with camera_lock:
        if camera is None or not camera.isOpened():
            for idx in range(3):
                cam = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cam.isOpened():
                    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cam.set(cv2.CAP_PROP_FPS,           30)
                    camera = cam
                    break
        return camera

# ──────────────────────────────────────────────
#  Detection loop (background thread)
# ──────────────────────────────────────────────
def detection_loop():
    global frame_buffer, detection_running
    detection_running = True

    with mp_face_mesh.FaceMesh(
        max_num_faces       = 1,
        refine_landmarks    = True,        # uses Attention Mesh (iris tracking)
        min_detection_confidence = 0.5,
        min_tracking_confidence  = 0.5,
    ) as face_mesh:

        while detection_running:
            cam = get_camera()
            if cam is None:
                time.sleep(0.5)
                continue

            ret, frame = cam.read()
            if not ret:
                time.sleep(0.1)
                continue

            h_img, w_img = frame.shape[:2]

            # MediaPipe needs RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = face_mesh.process(rgb)
            rgb.flags.writeable = True

            face_found = False

            if results.multi_face_landmarks:
                face_found = True
                fl = results.multi_face_landmarks[0].landmark
                mirror_state["landmarks_count"] = len(fl)

                # Head angles
                yaw, pitch, roll = estimate_head_angles(fl, w_img, h_img)
                mirror_state["head_yaw"]   = round(yaw,   2)
                mirror_state["head_pitch"] = round(pitch, 2)
                mirror_state["head_roll"]  = round(roll,  2)

                # Eye midpoint (normalised)
                le_x = (fl[L_EYE_INNER].x + fl[L_EYE_OUTER].x) / 2
                le_y = (fl[L_EYE_TOP].y   + fl[L_EYE_BOT].y)   / 2
                re_x = (fl[R_EYE_INNER].x + fl[R_EYE_OUTER].x) / 2
                re_y = (fl[R_EYE_TOP].y   + fl[R_EYE_BOT].y)   / 2
                eye_x = (le_x + re_x) / 2
                eye_y = (le_y + re_y) / 2
                mirror_state["eye_x"] = round(float(eye_x), 4)
                mirror_state["eye_y"] = round(float(eye_y), 4)

                # Mirror angles
                cal = calibration_data
                lh, lv, rh, rv = compute_mirror_angles(yaw, pitch, cal["yaw"], cal["pitch"])
                mirror_state["left"]["h"]  = round(lh, 2)
                mirror_state["left"]["v"]  = round(lv, 2)
                mirror_state["right"]["h"] = round(rh, 2)
                mirror_state["right"]["v"] = round(rv, 2)

                # Servo angles for ESP32
                mirror_state["servo"] = {
                    "left_h":  angle_to_servo(lh),
                    "left_v":  angle_to_servo(lv),
                    "right_h": angle_to_servo(rh),
                    "right_v": angle_to_servo(rv),
                }

                # ── Draw overlays (clean monochrome style) ──
                CYAN   = (200, 220, 255)   # pale blue-white for face outline
                BRIGHT = (0,   210, 255)   # vivid cyan for key points
                DIM    = (80,  120, 160)   # muted for subtle connections

                # Face oval silhouette – FACEMESH_FACE_OVAL only, thin dim line
                oval_spec = mp_drawing.DrawingSpec(color=DIM, thickness=1, circle_radius=0)
                mp_drawing.draw_landmarks(
                    frame,
                    results.multi_face_landmarks[0],
                    mp_face_mesh.FACEMESH_FACE_OVAL,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=oval_spec,
                )

                # Left eye outline – single color
                eye_spec = mp_drawing.DrawingSpec(color=CYAN, thickness=1, circle_radius=0)
                mp_drawing.draw_landmarks(
                    frame,
                    results.multi_face_landmarks[0],
                    mp_face_mesh.FACEMESH_LEFT_EYE,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=eye_spec,
                )
                mp_drawing.draw_landmarks(
                    frame,
                    results.multi_face_landmarks[0],
                    mp_face_mesh.FACEMESH_RIGHT_EYE,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=eye_spec,
                )

                # Key point dots: eye corners + nose tip (no jarring colors)
                le_px = lm(fl, L_EYE_INNER, w_img, h_img)
                re_px = lm(fl, R_EYE_INNER, w_img, h_img)
                le_out = lm(fl, L_EYE_OUTER, w_img, h_img)
                re_out = lm(fl, R_EYE_OUTER, w_img, h_img)
                nx, ny = lm(fl, NOSE_TIP, w_img, h_img)

                # Eye crosshair dots
                for pt in [le_px, re_px, le_out, re_out]:
                    cv2.circle(frame, pt, 2, BRIGHT, -1)

                # Nose dot
                cv2.circle(frame, (nx, ny), 4, BRIGHT, -1)
                cv2.circle(frame, (nx, ny), 6, DIM,    1)   # outer ring

                # Eye midpoint indicator (shows where gaze center is)
                emx = int((le_px[0] + re_px[0]) / 2)
                emy = int((le_px[1] + re_px[1]) / 2)
                cv2.line(frame, (emx-8, emy), (emx+8, emy), BRIGHT, 1)
                cv2.line(frame, (emx, emy-8), (emx, emy+8), BRIGHT, 1)

                # ── HUD text (semi-transparent bar background) ──
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w_img, 52), (10, 14, 22), -1)
                cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

                cv2.putText(frame,
                    f"Yaw {yaw:+.1f}   Pitch {pitch:+.1f}   Roll {roll:+.1f}",
                    (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, BRIGHT, 1, cv2.LINE_AA)
                cv2.putText(frame,
                    f"L: {lh:+.1f} / {lv:+.1f}     R: {rh:+.1f} / {rv:+.1f} deg",
                    (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 220, 160), 1, cv2.LINE_AA)

            mirror_state["face_detected"] = face_found

            # Encode frame
            _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with buffer_lock:
                frame_buffer = jpg.tobytes()

            time.sleep(0.033)   # ~30 fps cap

# ──────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("templates", "menu.html")

@app.route("/calibration")
def calibration():
    return send_from_directory("templates", "calibration.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# Video stream
def generate_frames():
    while True:
        with buffer_lock:
            frame = frame_buffer
        if frame:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.033)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# Full mirror state (used by frontend polling)
@app.route("/api/mirror_state")
def api_mirror_state():
    return jsonify(mirror_state)

# ESP32 servo endpoint – outputs clean servo angle dict
@app.route("/api/servo_angles")
def api_servo_angles():
    """
    Designed for ESP32 consumption.
    Returns { left_h, left_v, right_h, right_v } all in 0-180° servo range.
    Map directly to Servo.write() in Arduino.
    """
    return jsonify(mirror_state["servo"])

# Calibrate – lock current head pose as neutral
@app.route("/api/calibrate", methods=["POST"])
def api_calibrate():
    calibration_data["yaw"]   = mirror_state["head_yaw"]
    calibration_data["pitch"] = mirror_state["head_pitch"]
    calibration_data["eye_x"] = mirror_state["eye_x"]
    calibration_data["eye_y"] = mirror_state["eye_y"]
    mirror_state["calibrated"] = True
    return jsonify({"status": "ok", "calibration": calibration_data})

# Manual override (delta adjust)
@app.route("/api/manual_adjust", methods=["POST"])
def api_manual_adjust():
    data  = request.get_json(force=True)
    side  = data.get("side", "left")
    axis  = data.get("axis", "h")
    delta = float(data.get("delta", 0))
    limit = 25 if axis == "h" else 20
    mirror_state[side][axis] = float(clamp(mirror_state[side][axis] + delta, -limit, limit))
    # recompute servo
    mirror_state["servo"][f"{side}_{axis}"] = angle_to_servo(mirror_state[side][axis])
    return jsonify({"status": "ok", "mirror": mirror_state[side]})

# Reset all to centre
@app.route("/api/reset_mirrors", methods=["POST"])
def api_reset_mirrors():
    for s in ("left", "right"):
        mirror_state[s]["h"] = 0.0
        mirror_state[s]["v"] = 0.0
    calibration_data.update({"yaw": 0.0, "pitch": 0.0, "eye_x": 0.5, "eye_y": 0.5})
    mirror_state["calibrated"] = False
    mirror_state["servo"] = {"left_h": 90, "left_v": 90, "right_h": 90, "right_v": 90}
    return jsonify({"status": "ok"})

# Profiles
@app.route("/api/profiles", methods=["GET"])
def get_profiles():
    return jsonify(load_profiles())

@app.route("/api/profiles/save", methods=["POST"])
def save_profile():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    profiles = load_profiles()
    profiles[name] = {
        "left":        dict(mirror_state["left"]),
        "right":       dict(mirror_state["right"]),
        "calibration": dict(calibration_data),
        "servo":       dict(mirror_state["servo"]),
    }
    save_profiles(profiles)
    return jsonify({"status": "saved", "name": name})

@app.route("/api/profiles/load", methods=["POST"])
def load_profile():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    profiles = load_profiles()
    if name not in profiles:
        return jsonify({"error": "profile not found"}), 404
    p = profiles[name]
    mirror_state["left"]  = dict(p["left"])
    mirror_state["right"] = dict(p["right"])
    calibration_data.update(p.get("calibration", {"yaw": 0.0, "pitch": 0.0, "eye_x": 0.5, "eye_y": 0.5}))
    mirror_state["servo"] = dict(p.get("servo", {"left_h": 90, "left_v": 90, "right_h": 90, "right_v": 90}))
    mirror_state["calibrated"] = True
    return jsonify({"status": "loaded", "name": name, "mirror": mirror_state})

@app.route("/api/profiles/delete", methods=["POST"])
def delete_profile():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    profiles = load_profiles()
    if name in profiles:
        del profiles[name]
        save_profiles(profiles)
    return jsonify({"status": "deleted"})

# ──────────────────────────────────────────────
#  Start
# ──────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=detection_loop, daemon=True)
    t.start()
    print("\n╔══════════════════════════════════════╗")
    print("║   AutoMirror  –  AI Mirror System    ║")
    print("║   MediaPipe Face Mesh  ·  India RHD  ║")
    print("╠══════════════════════════════════════╣")
    print("║  Dashboard → http://localhost:5000   ║")
    print("║  ESP32 API → /api/servo_angles       ║")
    print("╚══════════════════════════════════════╝\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)