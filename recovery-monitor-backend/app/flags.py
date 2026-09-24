"""Session-level flagging rules (#36). Deterministic and separate from the ML model.

A session goes to the physio review queue when any rule fires. Every rule returns a plain reason.
Severity: "urgent" for pain signals, "review" for everything else.
"""


def session_flag(result: dict | None, check_in: dict | None, previous_check_in: dict | None,
                 protocol: dict | None) -> dict:
    reasons, urgent = [], False
    threshold = (protocol or {}).get("pain_threshold", 5)

    if result:
        reasons.extend((result.get("flag") or {}).get("reasons", []))
        if result.get("status") == "uncertain" and not any("confidence" in r.lower() for r in reasons):
            reasons.append("Low tracking confidence or unsuitable camera angle")
        conf = result.get("confidence")
        if conf is not None and conf < 0.6 and not any("confidence" in r.lower() for r in reasons):
            reasons.append(f"Pose tracking confidence is low ({conf:.0%})")

    if check_in:
        pain = check_in["pain_score"]
        if pain >= threshold:
            reasons.append(f"Pain {pain}/10 is at or above the plan's threshold of {threshold}")
            urgent = True
        if previous_check_in and pain > previous_check_in["pain_score"]:
            reasons.append(f"Pain went up from {previous_check_in['pain_score']} to {pain} since the last session")
            urgent = urgent or pain - previous_check_in["pain_score"] >= 2

    return {
        "flagged": bool(reasons),
        "severity": "urgent" if urgent else "review" if reasons else "none",
        "reasons": reasons,
    }
