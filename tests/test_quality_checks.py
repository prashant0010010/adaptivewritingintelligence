from core.quality_checks import run_quality_checks

ORIG = 'Smith (Smith, 2019) argued that "attention is a limited resource for students" and 45% agreed. Social media affects students strongly.'


def names(q, status="warn"):
    return {c["name"] for c in q["checks"] if c["status"] == status}


def test_identical_text_has_no_warnings():
    assert run_quality_checks(ORIG, ORIG)["warnings"] == 0


def test_missing_and_added_citation_flagged():
    q = run_quality_checks(ORIG, ORIG.replace("(Smith, 2019)", "(Jones, 2020)"))
    assert "Citation integrity" in names(q)


def test_altered_quotation_flagged():
    q = run_quality_checks(ORIG, ORIG.replace("limited resource", "scarce resource"))
    assert "Quotation integrity" in names(q)


def test_added_number_flagged():
    q = run_quality_checks(ORIG, ORIG + " Also 90% improved.")
    assert "Numbers and statistics" in names(q) and q["metrics"]["numbers_added"] >= 1


def test_key_terms_lost_flagged():
    q = run_quality_checks(ORIG, "Things happen to people sometimes in life and so on today.")
    assert "Key-term retention" in names(q)


def test_unsupported_addition_flagged_but_placeholder_ok():
    extra = ORIG + " Quantum entanglement drastically reshapes marine biology funding worldwide."
    assert "Possible unsupported additions" in names(run_quality_checks(ORIG, extra))
    ph = ORIG + " [ADD EVIDENCE: a source for the sleep claim]"
    q = run_quality_checks(ORIG, ph)
    assert q["metrics"]["placeholders"] == 1 and "Possible unsupported additions" not in names(q)


def test_length_vs_objective_for_minimal_edit():
    q = run_quality_checks(ORIG, ORIG + " " + ORIG, mode="minimal_edit")
    assert "Length vs objective" in names(q)


def test_note_says_not_proof():
    assert "do not prove" in run_quality_checks(ORIG, ORIG)["note"]
