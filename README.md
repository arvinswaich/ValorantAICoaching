# Valorant VOD Coach

A local Windows desktop app that reviews Valorant gameplay and turns crosshair-placement signals into specific coaching feedback.

## What it analyzes

- Crosshair placement around playable geometry
- Likely head-level discipline
- Corner and angle readiness
- Crosshair stability while moving
- Timestamped moments that need attention
- Focused fixes and practice drills

The current computer-vision model is heuristic. It evaluates what is around the center of the frame, but it does not yet identify enemy models or confirm exact kill and death moments.

## Run the desktop app

```powershell
pip install -r requirements.txt
python app.py
```

Everything runs locally. No web server, account, upload, or domain is required.

## Build a shareable Windows app

```powershell
.\build_windows.ps1
```

The finished app is created at:

```text
dist\ValorantVODCoach.exe
```

You can share that `.exe` with another Windows user. Windows SmartScreen may show an unrecognized-app warning because the executable is not code-signed.

## Project structure

- `app.py` - desktop entry point
- `desktop_app.py` - native Windows interface
- `analyzer/` - video analysis and coaching rules
- `build_windows.ps1` - executable build script
- `templates/` and `static/` - legacy browser UI retained for reference

## Next accuracy upgrade

Add a trained Valorant enemy detector and contact-event detection. That would let the coach measure crosshair-to-head distance at the exact moment an opponent appears.
