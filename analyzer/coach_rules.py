def generate_coaching_report(data: dict) -> dict:
    """
    Turns raw analysis numbers into a coach-style report.
    Later, you can replace or improve this with an LLM.
    """

    score = data.get("crosshair_centering_score", 0)

    mistakes = []
    fixes = []

    if score < 35:
        mistakes.append("Your crosshair control looks inconsistent in this clip.")
        fixes.append("Focus on keeping your crosshair near likely head level before fights.")
    elif score < 65:
        mistakes.append("Your crosshair control looks decent, but it may drift during movement.")
        fixes.append("Before peeking, pause briefly and pre-aim where the enemy head would appear.")
    else:
        mistakes.append("Your crosshair control looks stable in the sampled frames.")
        fixes.append("Next upgrade should analyze timing, utility, and positioning.")

    mistakes.append("This first version does not yet detect enemies, kills, or deaths.")
    fixes.append("Add enemy-contact detection next so the feedback becomes more specific.")

    overall_score = min(100, round(score))

    return {
        "video_name": data.get("video_name"),
        "duration_seconds": data.get("duration_seconds"),
        "fps": data.get("fps"),
        "sampled_frames": data.get("sampled_frames"),
        "overall_score": overall_score,
        "metrics": {
            "crosshair_centering_score": score
        },
        "mistakes": mistakes,
        "fixes": fixes,
        "next_build_goal": "Detect when an enemy appears on screen and measure crosshair distance from the enemy."
    }
