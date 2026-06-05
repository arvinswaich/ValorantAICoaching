# Valorant VOD AI Foundation

A starter MVP for a Valorant VOD review tool.

## What it does right now
- Lets a user upload a short MP4 clip
- Saves the clip
- Extracts basic video data
- Samples frames
- Creates a simple coaching report
- Gives you a clean foundation to expand into computer vision + AI feedback

## Tech stack
- Python
- Flask
- OpenCV
- HTML/CSS

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Next upgrades
1. Detect crosshair position more accurately.
2. Detect enemy contact moments.
3. Detect kill/death from screen text or timeline.
4. Add AI-generated coaching explanations.
5. Add user accounts and match history.
