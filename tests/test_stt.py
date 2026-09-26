from jarvis.audio.stt import _best_alternative, pick_transcript
from jarvis.lang import EN, HE


def test_prefers_the_more_confident_decode():
    result = pick_transcript({HE: ("מה השעה", 0.95), EN: ("ma hashaa", 0.4)})
    assert result.text == "מה השעה"
    assert result.language == HE


def test_prefers_english_when_english_was_spoken():
    result = pick_transcript({HE: ("וואט טיים", 0.5), EN: ("what time is it", 0.93)})
    assert result.language == EN


def test_script_mismatch_is_penalised_on_equal_confidence():
    result = pick_transcript({HE: ("what time is it", 0.8), EN: ("what time is it", 0.8)})
    assert result.language == EN


def test_empty_candidates():
    assert not pick_transcript({HE: "", EN: "   "})


def test_best_alternative_reads_the_google_payload():
    payload = {
        "alternative": [
            {"transcript": "מה השעה", "confidence": 0.91},
            {"transcript": "מה שעה"},
        ]
    }
    assert _best_alternative(payload) == ("מה השעה", 0.91)
    assert _best_alternative({"alternative": []}) is None
    assert _best_alternative("plain text") == ("plain text", 0.5)
