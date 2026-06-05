from flask import Flask, render_template, request, redirect, url_for
from pathlib import Path
from analyzer.video_analyzer import analyze_video

app = Flask(__name__)

UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return "No video uploaded", 400

    video = request.files["video"]

    if video.filename == "":
        return "No selected file", 400

    save_path = UPLOAD_FOLDER / video.filename
    video.save(save_path)

    report = analyze_video(str(save_path))

    return render_template("report.html", report=report)

if __name__ == "__main__":
    app.run(debug=True)
