import cv2
import numpy as np
from pathlib import Path
from analyzer.coach_rules import generate_coaching_report
from analyzer.valorant_vision import (
    CombatEventTracker,
    summarize_combat_events,
    validate_valorant_video,
)

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

    validation = validate_valorant_video(video_path)
    if not validation["is_valorant"]:
        cap.release()
        return {
            "error": (
                "This clip does not look like supported Valorant gameplay, so no score was generated. "
                "Use a first-person Valorant recording with the standard gameplay HUD visible."
            ),
            "error_code": "not_valorant",
            "video_name": Path(video_path).name,
            "validation": validation,
        }

    sampled_frames = 0
    placement_scores = []
    head_level_scores = []
    angle_readiness_scores = []
    stability_scores = []
    frame_observations = []
    issue_counts = {}

    frame_index = 0
    previous_center_gray = None
    placement_frame_step = max(1, int(fps / 2)) if fps else 15
    combat_frame_step = max(1, int(fps / 4)) if fps else 8
    combat_tracker = CombatEventTracker()

    while True:
        success, frame = cap.read()
        if not success:
            break

        timestamp = round(frame_index / fps, 2) if fps else 0

        # Combat cues are brief, so inspect about 4 frames per second.
        if frame_index % combat_frame_step == 0:
            combat_tracker.update(frame, timestamp)

        # Placement analysis at 2 frames per second keeps longer reviews responsive.
        if frame_index % placement_frame_step == 0:
            sampled_frames += 1
            placement = estimate_crosshair_placement(frame, previous_center_gray)
            previous_center_gray = placement.pop("_center_gray")

            placement["timestamp_seconds"] = timestamp
            placement_scores.append(placement["placement_score"])
            head_level_scores.append(placement["head_level_score"])
            angle_readiness_scores.append(placement["angle_readiness_score"])
            stability_scores.append(placement["stability_score"])
            frame_observations.append(placement)
            issue_counts[placement["primary_issue"]] = issue_counts.get(placement["primary_issue"], 0) + 1

        frame_index += 1

    cap.release()

    avg_placement_score = _average(placement_scores)
    avg_head_level_score = _average(head_level_scores)
    avg_angle_readiness_score = _average(angle_readiness_scores)
    avg_stability_score = _average(stability_scores)
    combat_data = summarize_combat_events(combat_tracker)

    raw_data = {
        "video_name": Path(video_path).name,
        "fps": round(fps, 2),
        "frame_count": frame_count,
        "duration_seconds": duration,
        "sampled_frames": sampled_frames,
        "crosshair_centering_score": avg_placement_score,
        "crosshair_placement_score": avg_placement_score,
        "head_level_score": avg_head_level_score,
        "angle_readiness_score": avg_angle_readiness_score,
        "crosshair_stability_score": avg_stability_score,
        "issue_counts": issue_counts,
        "frame_observations": frame_observations,
        "valorant_validation": validation,
        **combat_data,
    }

    coaching_report = generate_coaching_report(raw_data)
    return coaching_report


def _average(values) -> float:
    return round(sum(values) / len(values), 2) if values else 0


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return min(high, max(low, value))


def estimate_crosshair_centering(frame) -> float:
    """
    Backward-compatible wrapper for older code/tests.
    """
    return estimate_crosshair_placement(frame)["placement_score"]


def estimate_crosshair_placement(frame, previous_center_gray=None) -> dict:
    """
    Estimate crosshair placement quality from the area around the screen center.

    Valorant renders the crosshair at screen center, so this does not find the
    player's crosshair position. Instead, it judges what the crosshair is placed
    on: useful angle geometry, likely head-level reference lines, blank wall/floor
    space, and frame-to-frame stability.
    """
    height, width, _ = frame.shape

    center_x = width // 2
    center_y = height // 2

    center_region = _crop(frame, center_x, center_y, 120, 120)
    aim_region = _crop(frame, center_x, center_y, 260, 180)

    gray = cv2.cvtColor(aim_region, cv2.COLOR_BGR2GRAY)
    center_gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
    contrast = float(center_gray.std())
    sharpness = float(cv2.Laplacian(center_gray, cv2.CV_64F).var())

    edges = cv2.Canny(gray, 60, 150)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    upper_edge_density = _edge_density(gray[: gray.shape[0] // 2, :])
    lower_edge_density = _edge_density(gray[gray.shape[0] // 2 :, :])

    vertical_count, close_vertical_count, horizontal_mid_count = _count_angle_geometry(edges)
    blank_score = _clamp(100 - ((edge_density * 1700) + (contrast * 1.7)))
    floor_bias = _clamp((lower_edge_density - upper_edge_density) * 900)

    information_score = _clamp((edge_density * 1500) + (contrast * 1.25) + min(sharpness / 35, 18))
    angle_readiness_score = _clamp(
        25 + close_vertical_count * 18 + vertical_count * 6 + horizontal_mid_count * 8 + edge_density * 450
    )
    head_level_score = _clamp(
        35 + horizontal_mid_count * 12 + close_vertical_count * 10 + contrast * 0.7 - floor_bias * 0.55 - blank_score * 0.25
    )
    stability_score = _estimate_stability(center_gray, previous_center_gray)

    primary_issue = _classify_primary_issue(
        blank_score=blank_score,
        floor_bias=floor_bias,
        close_vertical_count=close_vertical_count,
        angle_readiness_score=angle_readiness_score,
        stability_score=stability_score,
        information_score=information_score,
    )

    placement_score = _clamp(
        information_score * 0.28
        + angle_readiness_score * 0.28
        + head_level_score * 0.28
        + stability_score * 0.16
    )

    return {
        "placement_score": round(placement_score, 2),
        "head_level_score": round(head_level_score, 2),
        "angle_readiness_score": round(angle_readiness_score, 2),
        "stability_score": round(stability_score, 2),
        "center_detail_score": round(information_score, 2),
        "blank_space_score": round(blank_score, 2),
        "floor_bias_score": round(floor_bias, 2),
        "primary_issue": primary_issue,
        "detail": _describe_frame(primary_issue, close_vertical_count, horizontal_mid_count),
        "_center_gray": center_gray,
    }


def _crop(frame, center_x: int, center_y: int, width: int, height: int):
    frame_h, frame_w, _ = frame.shape
    half_w = width // 2
    half_h = height // 2
    x1 = max(0, center_x - half_w)
    x2 = min(frame_w, center_x + half_w)
    y1 = max(0, center_y - half_h)
    y2 = min(frame_h, center_y + half_h)
    return frame[y1:y2, x1:x2]


def _edge_density(gray_region) -> float:
    if gray_region.size == 0:
        return 0
    edges = cv2.Canny(gray_region, 60, 150)
    return float(np.count_nonzero(edges) / edges.size)


def _count_angle_geometry(edges):
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=26,
        minLineLength=22,
        maxLineGap=8,
    )

    if lines is None:
        return 0, 0, 0

    height, width = edges.shape
    center_x = width / 2
    center_y = height / 2
    vertical_count = 0
    close_vertical_count = 0
    horizontal_mid_count = 0

    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        length = max(1, np.hypot(dx, dy))
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2

        if dy / length > 0.82:
            vertical_count += 1
            if abs(mid_x - center_x) < width * 0.22:
                close_vertical_count += 1
        elif dx / length > 0.82 and abs(mid_y - center_y) < height * 0.24:
            horizontal_mid_count += 1

    return vertical_count, close_vertical_count, horizontal_mid_count


def _estimate_stability(center_gray, previous_center_gray) -> float:
    if previous_center_gray is None or previous_center_gray.shape != center_gray.shape:
        return 75

    motion_delta = float(cv2.absdiff(center_gray, previous_center_gray).mean())
    return _clamp(100 - max(0, motion_delta - 8) * 3.2)


def _classify_primary_issue(
    blank_score,
    floor_bias,
    close_vertical_count,
    angle_readiness_score,
    stability_score,
    information_score,
) -> str:
    if blank_score > 58:
        return "blank_space"
    if floor_bias > 32 and information_score < 62:
        return "low_floor_aim"
    if close_vertical_count == 0 and angle_readiness_score < 48:
        return "not_pre_aiming_corner"
    if stability_score < 45:
        return "unstable_crosshair"
    return "good"


def _describe_frame(primary_issue, close_vertical_count, horizontal_mid_count) -> str:
    if primary_issue == "blank_space":
        return "Crosshair is sitting on low-information space instead of a playable edge."
    if primary_issue == "low_floor_aim":
        return "Center view looks biased toward floor texture, which usually means the aim is too low."
    if primary_issue == "not_pre_aiming_corner":
        return "No strong nearby corner/doorframe geometry is being held at center screen."
    if primary_issue == "unstable_crosshair":
        return "Center view changes sharply between samples; aim may be drifting during movement."
    if close_vertical_count and horizontal_mid_count:
        return "Crosshair is close to useful angle geometry and likely head-level references."
    return "Crosshair placement looks usable in this sampled moment."
