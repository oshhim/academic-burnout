"""Versioned, original nonclinical activity instructions and engineering policy settings."""
CATALOG_VERSION = "student-activities-v1"
POLICY_VERSION = "preference-feedback-rules-v1"
CATEGORIES = ("pause", "movement", "planning", "reflection", "audio")
GOALS = ("rest", "refocus", "organize", "reflect")
STRATEGIES = ("generic", "preference", "adaptive")
ACTIVITIES = [
    {"activity_id": "quiet_pause", "title": "A quiet pause", "category": "pause", "duration_seconds": 90, "goals": ["rest", "refocus"], "movement": False, "audio": False,
     "instructions": ["Pause your current task and sit comfortably.", "Let your attention settle on your surroundings; breathe in your usual comfortable way.", "Stop whenever you choose and decide what you would like to do next."]},
    {"activity_id": "screen_break", "title": "Step away from the screen", "category": "pause", "duration_seconds": 120, "goals": ["rest", "refocus"], "movement": False, "audio": False,
     "instructions": ["Set your screen aside if practical.", "Look around the room or at a comfortable distant point.", "Return when you choose; you can remain seated throughout."]},
    {"activity_id": "comfortable_walk", "title": "An optional short walk", "category": "movement", "duration_seconds": 300, "goals": ["rest", "refocus"], "movement": True, "audio": False,
     "instructions": ["Choose this only if walking is comfortable and the space is suitable.", "Walk at your own comfortable pace in a familiar space.", "Stop or choose a seated activity whenever you prefer."]},
    {"activity_id": "next_small_step", "title": "Choose one small next step", "category": "planning", "duration_seconds": 180, "goals": ["organize", "refocus"], "movement": False, "audio": False,
     "instructions": ["List the tasks currently competing for your attention.", "Choose one manageable next action; set the rest aside for now.", "Decide when to begin or choose to rest first."]},
    {"activity_id": "private_reflection", "title": "A private reflection", "category": "reflection", "duration_seconds": 180, "goals": ["reflect", "organize"], "movement": False, "audio": False,
     "instructions": ["Privately note what is occupying your attention.", "Consider what would make the next few minutes manageable.", "Keep or discard your notes yourself; this backend does not collect journal text."]},
    {"activity_id": "chosen_audio", "title": "Listen to something you choose", "category": "audio", "duration_seconds": 300, "goals": ["rest", "reflect"], "movement": False, "audio": True,
     "instructions": ["Choose familiar audio you find comfortable, using your own player.", "Use a comfortable volume and stop at any time.", "No audio is supplied, recorded or uploaded by this activity."]},
]
BY_ID = {row["activity_id"]: row for row in ACTIVITIES}
NOTICE = "Optional everyday activities, not treatment or emergency support. Ranking scores describe policy preferences, not expected health benefit."
