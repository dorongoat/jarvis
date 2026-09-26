from jarvis.audio.wakeword import WakeWordDetector, normalize

DETECTOR = WakeWordDetector(["jarvis", "ג'ארוויס", "גארוויס"])


def test_english_wake_word_with_command():
    heard, remainder = DETECTOR.find("Jarvis, what time is it?")
    assert heard
    assert remainder == "what time is it"


def test_hebrew_wake_word_with_command():
    heard, remainder = DETECTOR.find("ג'ארוויס תפתח לי ספוטיפיי")
    assert heard
    assert remainder == "תפתח לי ספוטיפיי"


def test_hebrew_variant_without_geresh():
    heard, remainder = DETECTOR.find("גארוויס מה השעה")
    assert heard and remainder == "מה השעה"


def test_no_wake_word():
    assert DETECTOR.find("what time is it") == (False, "")
    assert normalize("  Hey,  JARVIS!! ") == "hey jarvis"
