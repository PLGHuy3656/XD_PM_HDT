from swiftletcare_ai.schemas import AnomalyEvent, CountMessage, Detection, DetectionMessage


def test_detection_message_matches_contract():
    m = DetectionMessage("CAM-01", 1728135000, [Detection("swiftlet", 0.94, [120, 80, 165, 140], 21)]).to_dict()
    assert m == {"cameraId": "CAM-01", "timestamp": 1728135000, "detections": [
        {"class": "swiftlet", "confidence": 0.94, "bbox": [120, 80, 165, 140], "trackId": 21}]}


def test_count_message_matches_contract():
    assert CountMessage("CAM-01", 1728135000, 125, 98).to_dict() == {
        "cameraId": "CAM-01", "timestamp": 1728135000, "entryCount": 125, "exitCount": 98, "netChange": 27}


def test_predator_event_matches_contract():
    d = AnomalyEvent("CAM-01", "PREDATOR_DETECTED", "snake", 0.91, 1728135000,
                     [250, 160, 340, 230], "snapshot_url").to_dict()
    assert d["eventType"] == "PREDATOR_DETECTED" and d["class"] == "snake"
    assert d["bbox"] == [250, 160, 340, 230] and d["snapshot"] == "snapshot_url"