# Valorant VOD Coach

Turn your Valorant gameplay into clear, focused coaching feedback.

Valorant VOD Coach is a Windows desktop app that reviews recorded gameplay and helps players build better crosshair-placement habits. It highlights repeatable mistakes, calls out useful moments by timestamp, and creates a practical training plan for the next session.

## Download

[Download the latest Windows release](https://github.com/arvinswaich/ValorantAICoaching/releases/latest)

1. Download `ValorantVODCoach.exe` from the latest release.
2. Open the app and choose a recorded Valorant VOD.
3. Select **Analyze VOD** to generate your review.

No account, installation wizard, or web browser is required.

## Automatic Updates

Starting with version 1.0.1, the packaged app checks GitHub Releases for updates when it opens. When a newer version is available, it can download the verified Windows executable, replace the current app, and restart automatically. You can also select **Check for updates** in the sidebar.

Users of version 1.0.0 need to download version 1.0.1 manually once. Updates released after that can be installed from inside the app.

## Coaching Report

Each review includes:

- A Valorant gameplay validation check before scoring
- An overall crosshair-placement score
- Head-level discipline feedback
- Angle and corner-readiness analysis
- Crosshair-stability analysis
- Detected opponent-contact timestamps
- Estimated crosshair-to-head distance at contact
- Estimated personal kill and death cues
- Timestamped moments worth reviewing
- Specific coaching fixes and practice drills
- A report that can be exported for later review

## Supported Videos

- MP4
- MOV
- MKV
- AVI
- WebM

Windows 10 or Windows 11 is required.

## Privacy

Your gameplay is analyzed locally on your computer. VODs are not uploaded to a server or shared with anyone.

## Early Release Notice

This is an early computer-vision release. The app rejects clips when it cannot find repeated Valorant HUD evidence, but validation is not perfect. Opponent, head, kill, and death detections are confidence-based estimates and should be checked against the reported timestamps. Results may vary with video quality, resolution, HUD settings, enemy-highlight color, map geometry, and spectator overlays.

Windows may display an unrecognized-app warning because this release is not yet digitally code-signed.

## Feedback

Found an issue or have an idea for a better coaching feature? [Open a GitHub issue](https://github.com/arvinswaich/ValorantAICoaching/issues).
