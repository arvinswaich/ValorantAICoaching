from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class CombatEventTracker:
    last_kill_time: float = -10.0
    last_death_time: float = -10.0
    previous_kill_score: float = 0.0
    previous_death_score: float = 0.0
    contacts: list = field(default_factory=list)
    kills: list = field(default_factory=list)
    deaths: list = field(default_factory=list)

    def update(self, frame, timestamp_seconds: float) -> dict:
        opponents = detect_opponents(frame)
        best_opponent = min(
            opponents,
            key=lambda item: item["crosshair_distance_pixels"],
            default=None,
        )

        if best_opponent:
            contact = {
                "timestamp_seconds": timestamp_seconds,
                **best_opponent,
            }
            self.contacts.append(contact)

        kill_score = detect_kill_confirmation_score(frame)
        death_score = detect_death_screen_score(frame)

        if (
            kill_score >= 68
            and self.previous_kill_score < 65
            and timestamp_seconds - self.last_kill_time >= 1.5
        ):
            self.kills.append({
                "timestamp_seconds": timestamp_seconds,
                "confidence": round(kill_score, 2),
            })
            self.last_kill_time = timestamp_seconds

        if (
            death_score >= 72
            and self.previous_death_score < 62
            and timestamp_seconds - self.last_death_time >= 4.0
        ):
            self.deaths.append({
                "timestamp_seconds": timestamp_seconds,
                "confidence": round(death_score, 2),
            })
            self.last_death_time = timestamp_seconds

        self.previous_kill_score = kill_score
        self.previous_death_score = death_score

        return {
            "opponent": best_opponent,
            "kill_cue_score": round(kill_score, 2),
            "death_cue_score": round(death_score, 2),
        }


def validate_valorant_video(video_path: str, sample_limit: int = 12) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "is_valorant": False,
            "confidence": 0,
            "reason": "The video could not be opened.",
            "sampled_frames": 0,
        }

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        return {
            "is_valorant": False,
            "confidence": 0,
            "reason": "The video does not contain readable frames.",
            "sampled_frames": 0,
        }

    positions = np.linspace(
        int(frame_count * 0.04),
        max(int(frame_count * 0.96), 0),
        min(sample_limit, frame_count),
        dtype=int,
    )
    frame_results = []
    for position in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(position))
        success, frame = cap.read()
        if success:
            frame_results.append(score_valorant_hud(frame))
    cap.release()

    if not frame_results:
        return {
            "is_valorant": False,
            "confidence": 0,
            "reason": "The video does not contain readable frames.",
            "sampled_frames": 0,
        }

    scores = [item["score"] for item in frame_results]
    positive_frames = sum(item["coherent_hud_score"] >= 58 for item in frame_results)
    positive_ratio = positive_frames / len(scores)
    team_bar_ratio = sum(item["team_bar_score"] >= 58 for item in frame_results) / len(frame_results)
    portrait_strip_ratio = sum(item["portrait_strip_score"] >= 52 for item in frame_results) / len(frame_results)
    minimap_ratio = sum(item["minimap_score"] >= 50 for item in frame_results) / len(frame_results)
    bottom_hud_ratio = sum(item["bottom_hud_score"] >= 50 for item in frame_results) / len(frame_results)
    coherent_hud_ratio = sum(item["coherent_hud_score"] >= 58 for item in frame_results) / len(frame_results)

    confidence = _clamp(
        np.mean(scores) * 0.50
        + np.percentile(scores, 70) * 0.25
        + coherent_hud_ratio * 25
    )
    has_repeated_hud = (
        team_bar_ratio >= 0.50
        and portrait_strip_ratio >= 0.42
        and minimap_ratio >= 0.42
        and bottom_hud_ratio >= 0.42
        and coherent_hud_ratio >= 0.42
    )
    is_valorant = confidence >= 61 and positive_ratio >= 0.42 and has_repeated_hud

    if is_valorant:
        reason = "Repeated Valorant HUD patterns were detected across the clip."
    else:
        reason = (
            "The clip does not contain enough repeated Valorant HUD evidence "
            "such as the team bar, minimap, and ability/health layout."
        )

    return {
        "is_valorant": is_valorant,
        "confidence": round(confidence, 2),
        "reason": reason,
        "sampled_frames": len(frame_results),
        "evidence": {
            "positive_frame_ratio": round(positive_ratio, 3),
            "team_bar_ratio": round(team_bar_ratio, 3),
            "portrait_strip_ratio": round(portrait_strip_ratio, 3),
            "minimap_ratio": round(minimap_ratio, 3),
            "bottom_hud_ratio": round(bottom_hud_ratio, 3),
            "coherent_hud_ratio": round(coherent_hud_ratio, 3),
        },
    }


def score_valorant_hud(frame) -> dict:
    height, width, _ = frame.shape
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    top_bar = hsv[0:int(height * 0.13), int(width * 0.20):int(width * 0.80)]
    left_team = top_bar[:, :top_bar.shape[1] // 2]
    right_team = top_bar[:, top_bar.shape[1] // 2:]
    teal_ratio = _color_ratio(left_team, "teal")
    red_ratio = _color_ratio(right_team, "red")
    team_color_score = _clamp(
        min(1.0, teal_ratio / 0.009) * 50
        + min(1.0, red_ratio / 0.009) * 50
    )

    left_portraits = frame[0:int(height * 0.12), int(width * 0.23):int(width * 0.46)]
    right_portraits = frame[0:int(height * 0.12), int(width * 0.54):int(width * 0.77)]
    left_slots = _active_hud_slots(left_portraits, 5)
    right_slots = _active_hud_slots(right_portraits, 5)
    slot_balance = max(0, 100 - abs(left_slots - right_slots) * 24)
    portrait_strip_score = _clamp(
        min(left_slots, right_slots) / 4 * 78
        + slot_balance * 0.22
    )

    timer = frame[0:int(height * 0.115), int(width * 0.455):int(width * 0.545)]
    timer_detail_score = _hud_detail_score(timer, target_edge_ratio=0.075, target_bright_ratio=0.035)
    team_bar_score = _clamp(
        team_color_score * 0.55
        + portrait_strip_score * 0.30
        + timer_detail_score * 0.15
    )

    minimap = frame[
        int(height * 0.01):int(height * 0.32),
        int(width * 0.005):int(width * 0.245),
    ]
    minimap_gray = cv2.cvtColor(minimap, cv2.COLOR_BGR2GRAY)
    minimap_hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
    minimap_edges = cv2.Canny(minimap_gray, 55, 145)
    edge_ratio = np.count_nonzero(minimap_edges) / max(1, minimap_edges.size)
    neutral_bright_ratio = np.count_nonzero(
        (minimap_hsv[:, :, 1] < 75) & (minimap_hsv[:, :, 2] > 115)
    ) / max(1, minimap_hsv.shape[0] * minimap_hsv.shape[1])
    line_count = _line_count(minimap_edges, min_length=max(12, width // 90))
    minimap_contrast = float(minimap_gray.std())
    minimap_score = _clamp(
        min(1.0, edge_ratio / 0.075) * 32
        + min(1.0, neutral_bright_ratio / 0.15) * 24
        + min(1.0, line_count / 28) * 26
        + min(1.0, minimap_contrast / 42) * 18
    )

    health_panel = frame[
        int(height * 0.86):int(height * 0.99),
        int(width * 0.20):int(width * 0.36),
    ]
    ability_panel = frame[
        int(height * 0.82):int(height * 0.995),
        int(width * 0.37):int(width * 0.63),
    ]
    ammo_panel = frame[
        int(height * 0.82):int(height * 0.99),
        int(width * 0.75):int(width * 0.94),
    ]
    health_score = _hud_detail_score(health_panel, 0.060, 0.025)
    ammo_score = _hud_detail_score(ammo_panel, 0.060, 0.022)
    ability_detail_score = _hud_detail_score(ability_panel, 0.070, 0.022)
    ability_slots = _active_hud_slots(ability_panel, 4)
    ability_score = _clamp(ability_detail_score * 0.45 + min(1.0, ability_slots / 3) * 55)
    bottom_hud_score = _clamp(
        health_score * 0.30
        + ability_score * 0.42
        + ammo_score * 0.28
    )

    center = frame[
        max(0, height // 2 - 26):min(height, height // 2 + 27),
        max(0, width // 2 - 26):min(width, width // 2 + 27),
    ]
    center_hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    center_gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
    bright_or_colored = (
        (center_hsv[:, :, 2] > 185)
        | ((center_hsv[:, :, 1] > 95) & (center_hsv[:, :, 2] > 105))
    )
    center_ratio = np.count_nonzero(bright_or_colored) / max(1, bright_or_colored.size)
    center_edge_ratio = np.count_nonzero(cv2.Canny(center_gray, 70, 165)) / max(1, center_gray.size)
    crosshair_score = _clamp(
        min(1.0, center_ratio / 0.12) * 55
        + min(1.0, center_edge_ratio / 0.18) * 45
    )

    aspect_ratio = width / max(1, height)
    aspect_score = 100 if 1.55 <= aspect_ratio <= 2.0 else 25
    essential_scores = sorted((team_bar_score, portrait_strip_score, minimap_score, bottom_hud_score))
    coherent_hud_score = _clamp(
        np.mean(essential_scores[:3]) * 0.82
        + essential_scores[3] * 0.13
        + aspect_score * 0.05
    )
    score = (
        team_bar_score * 0.25
        + portrait_strip_score * 0.20
        + minimap_score * 0.25
        + bottom_hud_score * 0.25
        + crosshair_score * 0.05
    )

    return {
        "score": round(_clamp(score), 2),
        "coherent_hud_score": round(coherent_hud_score, 2),
        "team_bar_score": round(team_bar_score, 2),
        "portrait_strip_score": round(portrait_strip_score, 2),
        "timer_score": round(timer_detail_score, 2),
        "minimap_score": round(minimap_score, 2),
        "bottom_hud_score": round(bottom_hud_score, 2),
        "health_score": round(health_score, 2),
        "ability_score": round(ability_score, 2),
        "ammo_score": round(ammo_score, 2),
        "crosshair_score": round(crosshair_score, 2),
    }


def detect_opponents(frame) -> list:
    height, width, _ = frame.shape
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    red = _color_mask(hsv, "red", saturation=135, value=125)
    yellow = cv2.inRange(hsv, np.array([19, 120, 145]), np.array([40, 255, 255]))
    purple = cv2.inRange(hsv, np.array([132, 95, 120]), np.array([169, 255, 255]))
    mask = cv2.bitwise_or(red, cv2.bitwise_or(yellow, purple))

    mask[:int(height * 0.12), :] = 0
    mask[int(height * 0.73):, :] = 0
    mask[:, :int(width * 0.06)] = 0
    mask[:, int(width * 0.97):] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 9))
    connected = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    connected = cv2.dilate(connected, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = height * width
    crosshair_x = width / 2
    crosshair_y = height / 2
    diagonal = np.hypot(width, height)
    detections = []

    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        box_area = box_width * box_height
        if box_area < frame_area * 0.00010 or box_area > frame_area * 0.06:
            continue
        if box_height < height * 0.035 or box_height > height * 0.60:
            continue
        if y + box_height * 0.5 > height * 0.65:
            continue

        aspect = box_height / max(1, box_width)
        fill_ratio = area / max(1, box_area)
        if not 1.15 <= aspect <= 4.8 or not 0.05 <= fill_ratio <= 0.82:
            continue
        if x > width * 0.78 and y < height * 0.36:
            continue

        original_pixels = np.count_nonzero(mask[y:y + box_height, x:x + box_width])
        outline_ratio = original_pixels / max(1, box_area)
        if outline_ratio < 0.025:
            continue

        head_x = x + box_width * 0.5
        head_y = y + box_height * 0.14
        distance_pixels = float(np.hypot(head_x - crosshair_x, head_y - crosshair_y))
        distance_percent = float(distance_pixels / max(1, diagonal) * 100)
        shape_score = _clamp(100 - abs(aspect - 2.4) * 24)
        outline_score = _clamp(outline_ratio * 650)
        confidence = _clamp(shape_score * 0.55 + outline_score * 0.45)
        if confidence < 42:
            continue

        detections.append({
            "bounding_box": [int(x), int(y), int(box_width), int(box_height)],
            "estimated_head_position": [round(head_x, 1), round(head_y, 1)],
            "crosshair_distance_pixels": round(distance_pixels, 1),
            "crosshair_distance_percent": round(distance_percent, 2),
            "confidence": round(confidence, 2),
        })

    detections.sort(key=lambda item: item["crosshair_distance_pixels"])
    return detections[:4]


def detect_kill_confirmation_score(frame) -> float:
    height, width, _ = frame.shape
    roi = frame[
        int(height * 0.70):int(height * 0.91),
        int(width * 0.43):int(width * 0.57),
    ]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 65, 155)
    edge_ratio = np.count_nonzero(edges) / max(1, edges.size)
    red_ratio = _color_ratio(hsv, "red")
    white_ratio = np.count_nonzero(
        (hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 185)
    ) / max(1, hsv.shape[0] * hsv.shape[1])

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.4,
        minDist=max(8, roi.shape[0] // 5),
        param1=115,
        param2=24,
        minRadius=max(5, height // 120),
        maxRadius=max(12, height // 26),
    )
    circle_score = 100 if circles is not None else 0
    return _clamp(
        min(1.0, edge_ratio / 0.12) * 30
        + min(1.0, red_ratio / 0.035) * 25
        + min(1.0, white_ratio / 0.055) * 20
        + circle_score * 0.25
    )


def detect_death_screen_score(frame) -> float:
    height, width, _ = frame.shape
    panel = frame[
        int(height * 0.16):int(height * 0.84),
        int(width * 0.69):int(width * 0.985),
    ]
    panel_hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    panel_gray = cv2.cvtColor(panel, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(panel_gray, 55, 135)
    red_ratio = _color_ratio(panel_hsv, "red")
    dark_ratio = np.count_nonzero(panel_hsv[:, :, 2] < 72) / max(1, panel_hsv.shape[0] * panel_hsv.shape[1])
    horizontal_lines = _horizontal_line_count(edges, min_length=max(25, width // 24))

    health_region = frame[
        int(height * 0.82):height,
        int(width * 0.16):int(width * 0.42),
    ]
    bottom_hsv = cv2.cvtColor(health_region, cv2.COLOR_BGR2HSV)
    health_white_ratio = np.count_nonzero(
        (bottom_hsv[:, :, 1] < 90) & (bottom_hsv[:, :, 2] > 150)
    ) / max(1, bottom_hsv.shape[0] * bottom_hsv.shape[1])
    health_teal_ratio = np.count_nonzero(
        (bottom_hsv[:, :, 0] >= 60)
        & (bottom_hsv[:, :, 0] <= 110)
        & (bottom_hsv[:, :, 1] > 35)
        & (bottom_hsv[:, :, 2] > 70)
    ) / max(1, bottom_hsv.shape[0] * bottom_hsv.shape[1])
    health_signal = health_white_ratio + health_teal_ratio
    missing_health_score = _clamp((0.014 - health_signal) / 0.014 * 100)

    score = _clamp(
        min(1.0, red_ratio / 0.028) * 30
        + min(1.0, dark_ratio / 0.62) * 20
        + min(1.0, horizontal_lines / 14) * 25
        + missing_health_score * 0.25
    )
    if health_signal >= 0.014 or health_white_ratio > 0.20:
        return min(score, 42)
    return score


def summarize_combat_events(tracker: CombatEventTracker) -> dict:
    contacts = _deduplicate_contacts(tracker.contacts)
    distances = [item["crosshair_distance_pixels"] for item in contacts]
    distance_percents = [item["crosshair_distance_percent"] for item in contacts]
    return {
        "opponent_contacts": contacts,
        "opponent_contact_count": len(contacts),
        "estimated_kills": tracker.kills,
        "estimated_deaths": tracker.deaths,
        "estimated_kill_count": len(tracker.kills),
        "estimated_death_count": len(tracker.deaths),
        "average_crosshair_to_head_pixels": round(float(np.mean(distances)), 1) if distances else None,
        "best_crosshair_to_head_pixels": round(float(np.min(distances)), 1) if distances else None,
        "average_crosshair_to_head_percent": round(float(np.mean(distance_percents)), 2) if distance_percents else None,
    }


def _deduplicate_contacts(contacts: list) -> list:
    if not contacts:
        return []
    selected = []
    for contact in sorted(contacts, key=lambda item: item["timestamp_seconds"]):
        if not selected or contact["timestamp_seconds"] - selected[-1]["timestamp_seconds"] >= 1.0:
            selected.append(contact)
        elif contact["crosshair_distance_pixels"] < selected[-1]["crosshair_distance_pixels"]:
            selected[-1] = contact
    return selected


def _hud_detail_score(region, target_edge_ratio: float, target_bright_ratio: float) -> float:
    if region.size == 0:
        return 0
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 60, 150)
    edge_ratio = np.count_nonzero(edges) / max(1, edges.size)
    bright_neutral = (hsv[:, :, 1] < 80) & (hsv[:, :, 2] > 165)
    bright_colored = (hsv[:, :, 1] > 105) & (hsv[:, :, 2] > 125)
    hud_pixel_ratio = np.count_nonzero(bright_neutral | bright_colored) / max(1, gray.size)
    contrast = float(gray.std())
    return _clamp(
        min(1.0, edge_ratio / target_edge_ratio) * 45
        + min(1.0, hud_pixel_ratio / target_bright_ratio) * 35
        + min(1.0, contrast / 48) * 20
    )


def _active_hud_slots(region, slot_count: int) -> int:
    if region.size == 0 or slot_count <= 0:
        return 0
    slot_width = region.shape[1] / slot_count
    active_slots = 0
    for slot_index in range(slot_count):
        start = int(round(slot_index * slot_width))
        end = int(round((slot_index + 1) * slot_width))
        slot = region[:, start:end]
        if slot.size == 0:
            continue
        gray = cv2.cvtColor(slot, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(slot, cv2.COLOR_BGR2HSV)
        edge_ratio = np.count_nonzero(cv2.Canny(gray, 65, 155)) / max(1, gray.size)
        visible_pixels = (
            ((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 145))
            | ((hsv[:, :, 1] > 95) & (hsv[:, :, 2] > 115))
        )
        visible_ratio = np.count_nonzero(visible_pixels) / max(1, gray.size)
        if edge_ratio >= 0.022 and visible_ratio >= 0.018 and gray.std() >= 14:
            active_slots += 1
    return active_slots


def _color_mask(hsv, color: str, saturation: int = 55, value: int = 90):
    if color == "teal":
        return cv2.inRange(hsv, np.array([68, saturation, value]), np.array([105, 255, 255]))
    if color == "red":
        lower = cv2.inRange(hsv, np.array([0, saturation, value]), np.array([13, 255, 255]))
        upper = cv2.inRange(hsv, np.array([168, saturation, value]), np.array([179, 255, 255]))
        return cv2.bitwise_or(lower, upper)
    raise ValueError(f"Unknown color mask: {color}")


def _color_ratio(hsv, color: str) -> float:
    mask = _color_mask(hsv, color)
    return np.count_nonzero(mask) / max(1, mask.size)


def _line_count(edges, min_length: int) -> int:
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(12, min_length // 2),
        minLineLength=min_length,
        maxLineGap=7,
    )
    return 0 if lines is None else len(lines)


def _horizontal_line_count(edges, min_length: int) -> int:
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(15, min_length // 2),
        minLineLength=min_length,
        maxLineGap=9,
    )
    if lines is None:
        return 0
    count = 0
    for x1, y1, x2, y2 in lines[:, 0]:
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx > 0 and dy / dx < 0.18:
            count += 1
    return count


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return min(high, max(low, float(value)))
