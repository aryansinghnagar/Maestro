PLUGIN_META = {
    "name": "media-gestures",
    "version": "1.0.0",
    "description": "Media playback gestures: play/pause",
    "author": "gesture-controller-core",
}

GESTURE_DEFINITIONS = [
    {
        "name": "ThumbsUp",
        "type": "static",
        "priority": 10,
        "states": [
            {
                "id": "Idle",
                "transitions": [
                    {
                        "to": "ThumbUpPose",
                        "condition": "thumb_extended == True and index_extended == False and middle_extended == False and ring_extended == False and pinky_extended == False",
                    }
                ],
            },
            {
                "id": "ThumbUpPose",
                "min_duration_ms": 200,
                "max_duration_ms": 2000,
                "transitions": [
                    {"to": "Trigger", "condition": "True"},
                    {"to": "Idle", "condition": "thumb_extended == False", "abort": True},
                ],
            },
            {
                "id": "Trigger",
                "is_terminal": True,
                "action": "Media:PlayPause",
                "cooldown_ms": 1000,
            },
        ],
    }
]
