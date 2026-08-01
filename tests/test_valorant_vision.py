import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from analyzer.video_analyzer import analyze_video
from analyzer.valorant_vision import detect_opponents, score_valorant_hud


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


if __name__ == "__main__":
    unittest.main()
