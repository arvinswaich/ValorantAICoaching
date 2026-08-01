def generate_coaching_report(data: dict) -> dict:
    """
    Turns raw analysis numbers into a coach-style report.
    Later, you can replace or improve this with an LLM.
    """

    placement_score = data.get("crosshair_placement_score", data.get("crosshair_centering_score", 0))
    head_level_score = data.get("head_level_score", 0)
    angle_score = data.get("angle_readiness_score", 0)
    stability_score = data.get("crosshair_stability_score", 0)
    sampled_frames = max(1, data.get("sampled_frames", 1))
    issue_counts = data.get("issue_counts", {})
    observations = data.get("frame_observations", [])
    contact_count = data.get("opponent_contact_count", 0)
    average_head_distance = data.get("average_crosshair_to_head_pixels")
    average_head_distance_percent = data.get("average_crosshair_to_head_percent")
    best_head_distance = data.get("best_crosshair_to_head_pixels")
    estimated_kills = data.get("estimated_kills", [])
    estimated_deaths = data.get("estimated_deaths", [])
    contact_score = _contact_score(average_head_distance_percent)

    mistakes = []
    fixes = []
    strengths = []
    focus_drills = []
    specific_moments = _specific_moments(observations)
    combat_moments = _combat_moments(data.get("opponent_contacts", []))

    if placement_score >= 70:
        strengths.append("Your crosshair is usually near useful fight geometry instead of floating in empty space.")
    if head_level_score >= 70:
        strengths.append("Your aim height looks close to likely head-level references in many sampled moments.")
    if angle_score >= 70:
        strengths.append("You are often centering near corners or doorframe-like edges before contact.")
    if stability_score >= 75:
        strengths.append("Your center view stays fairly stable between samples, which helps first-shot readiness.")
    if contact_score is not None and contact_score >= 78:
        strengths.append(
            "At detected opponent contacts, your crosshair was already close to the estimated head position."
        )

    if _issue_rate(issue_counts, "low_floor_aim", sampled_frames) >= 0.18 or head_level_score < 45:
        mistakes.append(
            "Your crosshair appears too low in several samples, which can force a vertical flick before the duel starts."
        )
        fixes.append(
            "Use map props as head-height anchors: tops of boxes, doorframe midlines, railings, and the upper edge of common cover."
        )
        focus_drills.append("Deathmatch drill: spend one full round only correcting height before every corner, even if it slows you down.")

    if _issue_rate(issue_counts, "blank_space", sampled_frames) >= 0.15:
        mistakes.append(
            "The crosshair spends noticeable time on low-information space, like blank wall or open floor, instead of a threat line."
        )
        fixes.append(
            "When rotating or clearing, keep the crosshair attached to the next corner an enemy could swing from, not the middle of the wall."
        )
        focus_drills.append("Custom map drill: walk a route and call out the next threat angle before your crosshair reaches it.")

    if _issue_rate(issue_counts, "not_pre_aiming_corner", sampled_frames) >= 0.20 or angle_score < 50:
        mistakes.append(
            "You are not consistently pre-aiming the nearest corner or doorway before the fight could appear."
        )
        fixes.append(
            "Place your crosshair about one enemy head-width away from the edge you are clearing so a swinging player runs into your crosshair."
        )
        focus_drills.append("Corner drill: clear each angle in two beats: crosshair placed first, movement second.")

    if _issue_rate(issue_counts, "unstable_crosshair", sampled_frames) >= 0.12 or stability_score < 55:
        mistakes.append(
            "Your crosshair looks unstable during movement in parts of the clip, which can make you late to stop and shoot."
        )
        fixes.append(
            "During clears, move your mouse less and let strafing do more of the angle change. Stop, confirm head height, then commit."
        )
        focus_drills.append("Range drill: strafe between bots while keeping the crosshair at head height without over-correcting.")

    if contact_score is not None and contact_score < 58:
        mistakes.append(
            "At detected opponent contacts, your crosshair needed a large correction before reaching the estimated head position."
        )
        fixes.append(
            "Pre-aim the exact swing path before exposing yourself; use the contact timestamps to compare your crosshair with the opponent's head."
        )
        focus_drills.append(
            "Contact review drill: pause at each detected opponent timestamp and trace the shortest path from crosshair to head."
        )

    if not mistakes:
        mistakes.append("No major crosshair placement issue was detected in the sampled frames.")
        fixes.append("Your next improvement is precision: pre-aim exact swing paths, not just general head height.")
        focus_drills.append("VOD drill: pause before each fight and predict the exact pixel where the enemy head should appear.")

    if not strengths:
        strengths.append("The clip has enough visual variety to give placement feedback, but the main pattern still needs cleanup.")

    base_score = min(100, round(
        placement_score * 0.45 + head_level_score * 0.2 + angle_score * 0.2 + stability_score * 0.15
    ))
    overall_score = (
        min(100, round(base_score * 0.78 + contact_score * 0.22))
        if contact_score is not None
        else base_score
    )

    return {
        "video_name": data.get("video_name"),
        "duration_seconds": data.get("duration_seconds"),
        "fps": data.get("fps"),
        "sampled_frames": data.get("sampled_frames"),
        "overall_score": overall_score,
        "metrics": {
            "crosshair_centering_score": placement_score,
            "crosshair_placement_score": placement_score,
            "head_level_score": head_level_score,
            "angle_readiness_score": angle_score,
            "crosshair_stability_score": stability_score,
            "contact_aim_score": contact_score,
        },
        "issue_counts": issue_counts,
        "strengths": strengths,
        "mistakes": mistakes,
        "fixes": fixes,
        "focus_drills": focus_drills,
        "specific_moments": specific_moments,
        "combat_moments": combat_moments,
        "combat_summary": {
            "opponent_contact_count": contact_count,
            "estimated_kill_count": len(estimated_kills),
            "estimated_death_count": len(estimated_deaths),
            "average_crosshair_to_head_pixels": average_head_distance,
            "best_crosshair_to_head_pixels": best_head_distance,
        },
        "valorant_validation": data.get("valorant_validation"),
        "analysis_note": (
            "Opponent, head, kill, and death results are confidence-based computer-vision estimates. "
            "Review the timestamps before treating an event as confirmed."
        ),
    }


def _issue_rate(issue_counts: dict, issue_name: str, sampled_frames: int) -> float:
    return issue_counts.get(issue_name, 0) / sampled_frames


def _specific_moments(observations: list) -> list:
    issue_priority = {
        "low_floor_aim": 0,
        "not_pre_aiming_corner": 1,
        "blank_space": 2,
        "unstable_crosshair": 3,
        "good": 4,
    }
    problem_moments = [
        item for item in observations
        if item.get("primary_issue") != "good"
    ]
    problem_moments.sort(
        key=lambda item: (
            issue_priority.get(item.get("primary_issue"), 9),
            item.get("placement_score", 100),
        )
    )

    moments = []
    for item in problem_moments[:6]:
        moments.append({
            "timestamp_seconds": item.get("timestamp_seconds"),
            "issue": _human_issue(item.get("primary_issue")),
            "detail": item.get("detail"),
            "tip": _moment_tip(item.get("primary_issue")),
        })
    return moments


def _human_issue(issue: str) -> str:
    labels = {
        "blank_space": "Aiming at low-value space",
        "low_floor_aim": "Crosshair likely too low",
        "not_pre_aiming_corner": "Corner not pre-aimed",
        "unstable_crosshair": "Crosshair drift",
        "good": "Good placement",
    }
    return labels.get(issue, "Crosshair placement issue")


def _moment_tip(issue: str) -> str:
    tips = {
        "blank_space": "Snap the crosshair to the next enemy entry point before you keep moving.",
        "low_floor_aim": "Lift to the head-height landmark nearest that angle before taking the fight.",
        "not_pre_aiming_corner": "Hold slightly off the edge so the enemy swing crosses your crosshair.",
        "unstable_crosshair": "Slow the clear down and use your strafe to adjust the angle.",
    }
    return tips.get(issue, "Keep the crosshair tied to the most likely threat angle.")


def _contact_score(distance_percent):
    if distance_percent is None:
        return None
    return round(max(0, min(100, 100 - distance_percent * 8)), 2)


def _combat_moments(contacts: list) -> list:
    moments = []
    for contact in sorted(
        contacts,
        key=lambda item: item.get("crosshair_distance_pixels", 0),
        reverse=True,
    )[:6]:
        distance = contact.get("crosshair_distance_pixels", 0)
        if distance <= 35:
            label = "Crosshair near estimated head"
            tip = "This contact required only a small correction."
        elif distance <= 90:
            label = "Moderate contact correction"
            tip = "Tighten the pre-aim so the opponent appears closer to center screen."
        else:
            label = "Large contact correction"
            tip = "Revisit the angle and pre-place the crosshair on the expected swing path."
        moments.append({
            "timestamp_seconds": contact.get("timestamp_seconds", 0),
            "issue": label,
            "distance_pixels": distance,
            "confidence": contact.get("confidence", 0),
            "detail": (
                f"Estimated head offset: {round(distance)} px "
                f"({round(contact.get('confidence', 0))}% confidence)."
            ),
            "tip": tip,
        })
    return moments
