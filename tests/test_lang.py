from jarvis.lang import EN, HE, PHRASES, detect_language, is_rtl, phrase, ui_text


def test_detects_hebrew_and_english():
    assert detect_language("מה השעה") == HE
    assert detect_language("what time is it") == EN
    assert detect_language("תפתח לי Spotify") == HE
    assert detect_language("") == EN


def test_rtl_and_phrasebook():
    assert is_rtl(HE) and not is_rtl(EN)
    assert phrase("yes", HE) in PHRASES["yes"][HE]
    assert phrase("error", EN, error="boom").endswith("boom")
    assert ui_text("state_listening", HE) == "מקשיב"
