# Limitations and roadmap

## Status of each feature

| Feature | Status |
|---|---|
| Profiles, samples (paste, TXT, DOCX, PDF), SQLite persistence, deletion | Implemented |
| Lexical, sentence, punctuation, transition, hedging features | Implemented (deterministic, English-oriented) |
| Argument analysis, local | Implemented as cue-word heuristics (approximation) |
| Argument analysis, model-based | Implemented, needs an API or the demo provider; output is a labelled estimate |
| Revision modes, side-by-side, diff, version history, restore | Implemented; real rewriting needs Gemini |
| Feedback learning | Implemented as counting and thresholds; not model training |
| Quality checks | Implemented; heuristic flags, not proofs |
| Evaluation | Implemented harness; built-in cases are synthetic; demo provider results are only a pipeline check |
| Reports | Markdown, TXT, DOCX |

## Known limits

- English only. Sentence splitting, cue lists and syllable counting are heuristic.
- Style is not stable across genres or topics; small samples give unstable measurements. Evidence labels are coarse.
- Cue-word analysis cannot see implicit reasoning or judge whether support is good.
- Quality checks can miss added claims and can flag harmless changes.
- Learning uses four coarse dimensions. It cannot learn "voice" in a deeper sense. A rejection may be about something other than the measured dimension.
- OCR is not supported (image-only PDFs are rejected). DOCX tables are flattened.
- Gemini: not tested against the live service in this build (no key or network was available). SDK usage was checked against google-genai 2.x; model names, quotas and the free tier can change, so verify in Google's documentation.
- Local profiles are not an access-control mechanism.
- No claim is made that this beats any commercial tool, and no detector-evasion goal is built in.

## Roadmap ideas

OCR for scans; embedding-based retrieval; more learned dimensions with per-genre confidence intervals; export and import of a profile; paragraph-level accept/reject; a multilingual lexicon; side-by-side human rating sessions for evaluation.
