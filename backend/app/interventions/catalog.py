"""Versioned, original nonclinical activity instructions and engineering policy settings."""
CATALOG_VERSION = "student-guided-activities-v2"
POLICY_VERSION = "optional-multimodal-rules-v2"
CATEGORIES = ("pause", "movement", "planning", "reflection", "audio")
GOALS = ("rest", "refocus", "organize", "reflect")
STRATEGIES = ("generic", "preference", "adaptive", "multimodal_weighted")
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
    {"activity_id": "sensory_pause", "title": "Notice your surroundings", "category": "reflection", "duration_seconds": 60, "goals": ["rest", "reflect"], "movement": False, "audio": False,
     "instructions": ["Choose a comfortable seated position and keep your eyes open if you prefer.", "Notice a few colours, shapes or sounds around you without needing to change anything.", "Choose whether to continue, switch activity or return to your task."]},
    {"activity_id": "desk_reset", "title": "Make space for one task", "category": "planning", "duration_seconds": 120, "goals": ["organize"], "movement": False, "audio": False,
     "instructions": ["Choose one task and name the tools it needs.", "Set aside one distracting tab or item if convenient; remaining seated is fine.", "Choose a small first action and decide whether to begin now or rest first."]},
]

# Every guide totals the offered duration. Notes stay temporarily on the phone;
# the backend receives only session state and optional helpfulness feedback.
GUIDES = {
    "quiet_pause": [("Settle", 20), ("Notice and pause", 50), ("Choose what is next", 20)],
    "screen_break": [("Set the screen aside", 20), ("Rest your attention", 80), ("Return when ready", 20)],
    "comfortable_walk": [("Check the space", 30), ("Walk at your own pace", 240), ("Pause and choose", 30)],
    "next_small_step": [("Name the competing tasks", 60), ("Choose one small action", 80), ("Decide when to start", 40)],
    "private_reflection": [("Notice what is on your mind", 60), ("Find one manageable change", 80), ("Keep or discard your note", 40)],
    "chosen_audio": [("Choose your own audio", 30), ("Listen comfortably", 240), ("Stop and check in", 30)],
    "sensory_pause": [("Get comfortable", 15), ("Notice your surroundings", 30), ("Choose your next step", 15)],
    "desk_reset": [("Name one task", 30), ("Reduce one distraction", 60), ("Choose the first action", 30)],
}
for row in ACTIVITIES:
    row["summary"] = row["instructions"][1]
    row["guide_steps"] = [{"title": title, "duration_seconds": seconds, "instruction": instruction}
                          for (title, seconds), instruction in zip(GUIDES[row["activity_id"]], row["instructions"])]
    row["note_prompt"] = {"next_small_step": "What is one manageable next action?", "private_reflection": "What would make the next few minutes manageable?", "desk_reset": "What will you put your attention on first?"}.get(row["activity_id"])
BY_ID = {row["activity_id"]: row for row in ACTIVITIES}
NOTICE = "Optional everyday activities, not treatment or emergency support. Ranking scores describe policy preferences, not expected health benefit."
