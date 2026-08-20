from jobfinder.affine import AffineReply, split_thinking, _extract_json


def test_split_thinking_strips_qwen_markers():
    thinking, content = split_thinking(
        "<think>\nNeed to weigh Python vs Go\n</think>\nHire the Python intern."
    )
    assert "Python vs Go" in thinking
    assert content == "Hire the Python intern."


def test_split_thinking_without_marker():
    thinking, content = split_thinking("Just the answer")
    assert thinking == ""
    assert content == "Just the answer"


def test_extract_json_from_fenced_block():
    payload = _extract_json('```json\n{"score": 71, "summary": "ok"}\n```')
    assert payload == {"score": 71, "summary": "ok"}


def test_extract_json_from_prose():
    payload = _extract_json('Here you go {"score": 12, "reasons": ["x"]}')
    assert payload["score"] == 12
    assert payload["reasons"] == ["x"]


def test_extract_json_rejects_arrays():
    assert _extract_json("[1, 2]") is None


def test_affine_reply_text():
    reply = AffineReply(content="  hello  ", thinking="secret")
    assert reply.text() == "hello"
