from core.argument_analysis import analyse_argument, label_sentence


def test_labels():
    assert "explanation" in label_sentence("This matters because it saves time.")
    assert "counterargument" in label_sentence("However, critics disagree.")
    assert "evidence" in label_sentence("Attention drops (Smith, 2020).")


def test_flags():
    t = "We argue that schools must act.\n\nStudies show 70% of pupils sleep less. Dogs are nice and loyal friends today. Dogs are nice and loyal friends today."
    types = {f["type"] for f in analyse_argument(t)["flags"]}
    assert {"claim_without_visible_support", "possible_unsupported_evidence_claim", "possible_repetition"} <= types


def test_empty_text():
    r = analyse_argument("")
    assert r["sentences"] == [] and r["flags"] == []
