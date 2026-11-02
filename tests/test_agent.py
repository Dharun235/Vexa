from vexa.agent import ask, extract_program, parse_answer
from vexa.bench import score
from vexa.interpreter import execute_commands


class ScriptedClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages):
        self.seen.append(messages)
        return self.replies.pop(0)


PROGRAM = '```vexa\nload "image.jpg"\ndetect person\ncount person\n```'


def test_extract_program_takes_last_block_and_strips_thinking():
    reply = "<think>maybe ```vexa\nocr\n```</think>Here:\n" + PROGRAM
    assert extract_program(reply) == 'load "image.jpg"\ndetect person\ncount person\n'
    assert extract_program("ocr") == "ocr\n"


def test_ask_runs_program_and_answers(image, fake_vision):
    client = ScriptedClient([PROGRAM, "ANSWER: 1"])
    result = ask("How many people?", lambda c: execute_commands(c, image, fake_vision), client)
    assert result.answer == "1"
    assert result.attempts == 1
    assert '"person": 1' in client.seen[1][0]["content"]


def test_ask_repairs_invalid_program(image, fake_vision):
    bad = '```vexa\nload "image.jpg"\ncount person\n```'
    client = ScriptedClient([bad, PROGRAM, "ANSWER: 1"])
    result = ask("How many people?", lambda c: execute_commands(c, image, fake_vision), client)
    assert result.attempts == 2
    assert "Line 2: Run detect before counting" in result.errors[0]
    assert "count person" in client.seen[1][-1]["content"]
    assert result.answer == "1"


def test_ask_gives_up_after_max_attempts(image, fake_vision):
    client = ScriptedClient(["detect"] * 3)
    result = ask("q", lambda c: execute_commands(c, image, fake_vision), client)
    assert result.program is None and result.answer is None and len(result.errors) == 3


def test_parse_answer_and_score():
    assert parse_answer("ok\nANSWER: 4 people") == "4 people"
    assert score({"type": "number", "answer": [4]}, "4 people")
    assert not score({"type": "number", "answer": [4]}, "about 5")
    assert score({"type": "yesno", "answer": "no"}, "No, there is none.")
    assert score({"type": "text", "answer": "SN77A12290"}, "The serial is sn77a12290.")
    assert not score({"type": "text", "answer": "4821"}, None)


def test_ask_stops_when_object_is_not_detectable(image, fake_vision):
    fake_vision.labels = {0: "person", 1: "car"}
    client = ScriptedClient(['```vexa\nload "x"\ndetect all\ncount tree\n```'])
    result = ask("Is there a tree?", lambda c: execute_commands(c, image, fake_vision), client)
    assert result.attempts == 1 and result.program is None
    assert result.answer.startswith('Vexa cannot answer this: Unknown object "tree"')
