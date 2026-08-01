import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from analyzer.video_analyzer import analyze_video
from analyzer.valorant_vision import (
    detect_opponents,
    score_valorant_hud,
    validate_valorant_video,
)


class ValorantValidationTests(unittest.TestCase):
    def test_plain_frame_has_low_valorant_score(self):
        frame = np.full((360, 640, 3), 80, dtype=np.uint8)
        result = score_valorant_hud(frame)
        self.assertLess(result["score"], 30)

    def test_non_valorant_video_is_rejected_without_score(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "unrelated.mp4"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                10,
                (640, 360),
            )
            for frame_index in range(40):
                frame = np.full(
                    (360, 640, 3),
                    (frame_index * 4 % 255, 55, 95),
                    dtype=np.uint8,
                )
                cv2.putText(
                    frame,
                    "UNRELATED VIDEO",
                    (125, 190),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.1,
                    (255, 255, 255),
                    2,
                )
                writer.write(frame)
            writer.release()

            report = analyze_video(str(video_path))

        self.assertEqual(report.get("error_code"), "not_valorant")
        self.assertNotIn("overall_score", report)
        self.assertFalse(report["validation"]["is_valorant"])

    def test_generic_fps_hud_is_not_enough(self):
        frame = _generic_fps_frame()

        result = score_valorant_hud(frame)

        self.assertLess(result["portrait_strip_score"], 52)
        self.assertLess(result["coherent_hud_score"], 58)

    def test_repeated_valorant_layout_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "valorant-layout.mp4"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                10,
                (640, 360),
            )
            for frame_index in range(40):
                writer.write(_valorant_hud_frame(frame_index))
            writer.release()

            validation = validate_valorant_video(str(video_path))

        self.assertTrue(validation["is_valorant"], validation)
        self.assertGreaterEqual(validation["evidence"]["coherent_hud_ratio"], 0.42)

    def test_enemy_outline_returns_head_distance(self):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        color = (0, 255, 255)
        cv2.circle(frame, (320, 130), 11, color, 5)
        cv2.line(frame, (320, 142), (320, 218), color, 8)
        cv2.line(frame, (320, 155), (292, 190), color, 6)
        cv2.line(frame, (320, 155), (348, 190), color, 6)
        cv2.line(frame, (320, 216), (302, 270), color, 7)
        cv2.line(frame, (320, 216), (338, 270), color, 7)

        detections = detect_opponents(frame)

        self.assertTrue(detections)
        self.assertIn("estimated_head_position", detections[0])
        self.assertGreaterEqual(detections[0]["crosshair_distance_pixels"], 0)


def _generic_fps_frame():
    frame = np.full((360, 640, 3), 52, dtype=np.uint8)
    cv2.rectangle(frame, (145, 8), (290, 22), (210, 175, 15), -1)
    cv2.rectangle(frame, (350, 8), (495, 22), (20, 25, 225), -1)
    cv2.rectangle(frame, (8, 12), (145, 112), (32, 38, 42), -1)
    for offset in range(20, 140, 24):
        cv2.line(frame, (offset, 16), (offset - 12, 105), (145, 145, 145), 1)
    for offset in range(24, 110, 22):
        cv2.line(frame, (12, offset), (140, offset), (145, 145, 145), 1)
    cv2.putText(frame, "100", (18, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2)
    cv2.putText(frame, "30", (570, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2)
    cv2.line(frame, (310, 180), (330, 180), (240, 240, 240), 1)
    cv2.line(frame, (320, 170), (320, 190), (240, 240, 240), 1)
    return frame


def _valorant_hud_frame(frame_index=0):
    frame = np.full((360, 640, 3), 46 + frame_index % 3, dtype=np.uint8)
    teal = (200, 175, 15)
    red = (35, 40, 225)

    for side_start, color in ((148, teal), (346, red)):
        for slot_index in range(5):
            x1 = side_start + slot_index * 29
            cv2.rectangle(frame, (x1, 4), (x1 + 24, 36), color, 2)
            cv2.circle(frame, (x1 + 12, 16), 6, (210, 210, 210), 1)
            cv2.line(frame, (x1 + 5, 31), (x1 + 19, 22), (180, 180, 180), 1)

    cv2.rectangle(frame, (294, 2), (346, 40), (24, 27, 31), -1)
    cv2.putText(frame, "1:24", (299, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (245, 245, 245), 1)

    points = np.array([(15, 16), (130, 16), (145, 95), (82, 112), (12, 91)], np.int32)
    cv2.polylines(frame, [points], True, (175, 175, 175), 2)
    for offset in range(28, 125, 20):
        cv2.line(frame, (offset, 22), (offset - 10, 94), (125, 125, 125), 1)
    for offset in range(30, 95, 18):
        cv2.line(frame, (17, offset), (132, offset + 5), (125, 125, 125), 1)

    cv2.putText(frame, "100", (142, 345), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), 2)
    for slot_index in range(4):
        x1 = 244 + slot_index * 38
        cv2.rectangle(frame, (x1, 315), (x1 + 29, 350), (190, 190, 190), 1)
        cv2.circle(frame, (x1 + 14, 330), 7, teal if slot_index % 2 == 0 else (230, 230, 230), 2)
    cv2.putText(frame, "25", (500, 338), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (245, 245, 245), 2)
    cv2.line(frame, (312, 180), (328, 180), (245, 245, 245), 1)
    cv2.line(frame, (320, 172), (320, 188), (245, 245, 245), 1)
    return frame


if __name__ == "__main__":
    unittest.main()
