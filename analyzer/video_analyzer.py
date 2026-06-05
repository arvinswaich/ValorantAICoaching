import cv2
from pathlib import Path
from analyzer.coach_rules import generate_coaching_report

def analyze_video(video_path: str) -> dict:
    """
    Basic video analysis foundation.
    Later, this is where you add:
    - crosshair tracking
    - enemy detection
    - minimap analysis
    - death/kill detection
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return {
            "error": "Could not open video.",
            "video_name": Path(video_path).name
        }

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = round(frame_count / fps, 2) if fps else 0

    sampled_frames = 0
    center_crosshair_scores = []

    frame_index = 0

    while True:
        success, frame = cap.read()
        if not success:
            break

        # Analyze about 1 frame per second for now
        if fps and frame_index % int(fps) == 0:
            sampled_frames += 1
            score = estimate_crosshair_centering(frame)
            center_crosshair_scores.append(score)

        frame_index += 1

    cap.release()

    avg_centering_score = (
        round(sum(center_crosshair_scores) / len(center_crosshair_scores), 2)
        if center_crosshair_scores else 0
    )

    raw_data = {
        "video_name": Path(video_path).name,
        "fps": round(fps, 2),
        "frame_count": frame_count,
        "duration_seconds": duration,
        "sampled_frames": sampled_frames,
        "crosshair_centering_score": avg_centering_score,
    }

    coaching_report = generate_coaching_report(raw_data)
    return coaching_report


def estimate_crosshair_centering(frame) -> float:
    """
    Temporary placeholder metric.

    This does NOT truly detect crosshair placement yet.
    It gives a rough score based on whether the center of the screen is clear/visible.

    Later upgrade:
    - detect actual crosshair color/shape
    - compare crosshair height to likely enemy head level
    - detect if crosshair is aimed at floor/wall
    """

    height, width, _ = frame.shape

    center_x = width // 2
    center_y = height // 2

    # Grab small center area
    box_size = 40
    center_region = frame[
        center_y - box_size:center_y + box_size,
        center_x - box_size:center_x + box_size
    ]

    # Basic sharpness/contrast estimate
    gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
    contrast = gray.std()

    # Normalize to 0-100
    score = min(100, max(0, contrast * 3))
    return round(score, 2)
