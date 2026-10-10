# Architecture

## Data flow

```
Input (paste/upload) -> validation (size, type, empty, length)
  -> local analysis (core/writing_analysis, core/argument_analysis)       [no network]
  -> profile retrieval (core/retrieval: approved examples, same genre first) + preferences
  -> revision plan (core/revision_engine.plan_revision; flags conflicting goals)
  -> consent gate (ui/common.consent_gate) -> provider.generate()          [network only if Gemini]
  -> response validation (parse_revision_response)
  -> quality checks (core/quality_checks)
  -> user decision: accept / edit / reject -> feedback_events
  -> preference learning (core/profile_learning) -> versioned preferences
```

Everything in `core/` is pure Python over text and works without a provider. The UI never calls the SDK directly.

## Provider abstraction

`providers/base.LLMProvider.generate(system, prompt, json_mode) -> LLMResponse`, with typed errors (`ProviderNotConfigured`, `ProviderRateLimited`, `ProviderTimeout`, `ProviderResponseError`). `GeminiProvider` uses the `google-genai` SDK, a configurable model and timeout, and retries transient errors (429, 5xx, timeouts) with backoff. `MockProvider` is used by tests and the offline demo; it can return scripted responses or raise scripted errors. To add a provider, subclass `LLMProvider` and register it in `ui/common.get_provider`.

## Features and their limits

| Feature | Definition | Why included | Limitation |
|---|---|---|---|
| Mean sentence length | words / sentences (regex splitter with abbreviation handling) | basic rhythm | splitter errs on unusual punctuation |
| Sentence length SD | population SD, shown only with 5+ sentences | variability | unstable on short text |
| MATTR-50 | mean type-token ratio over 50-word windows, needs 50+ words | diversity less sensitive to length | still topic dependent |
| Transitions, hedging per 100 words | counts of phrases from fixed lists | discourse habits | list based, English only |
| Punctuation, function words per 1000 | raw counts scaled | style markers | descriptive, not diagnostic |
| Flesch (approx.) | standard formula, heuristic syllables | readability proxy | English only, approximate |
| Cue-word argument labels | cue lexicons per component | cheap, inspectable | misses implicit reasoning; labels are hints |
| Distribution distance | Jensen-Shannon distance (base 2, 0..1) over sentence-length bins and function words | coarse comparison draft vs samples | does not establish authorship or "sounds like you" |
| Evidence level | label from word count and sample count | honesty about small samples | not a probability |

## Quality checks

Citation and quotation integrity, numbers added or missing, key-term retention, capitalised names, possible unsupported additions (vocabulary overlap), placeholders, length versus mode, repetition, readability, TF-IDF cosine (weak signal) and coarse closeness to your samples. Each returns pass, warn or info. None proves meaning preservation; the report says so.

## Profile learning

Each feedback event stores four measured changes between the original and the final text: length, transitions per 100 words, mean sentence length, hedging per 100 words. A change counts only above a threshold. Votes: accept = +1, edit = +1.5 (measured on your edited text), reject = 0.5 toward the opposite direction. A preference activates with at least 3 informative events and 70% weighted agreement, and is withdrawn if evidence stops agreeing. Preferences you set yourself are never overridden. Reset ignores earlier feedback for that dimension. Every change creates a row in `preference_versions` that can be restored. Approved examples (only label `approved`) are retrieved with TF-IDF cosine similarity, same genre first, at most 3 per prompt.

## Database

SQLite, `PRAGMA foreign_keys=ON`, schema versioned with `PRAGMA user_version` and SQL files in `database/migrations/`. Tables: `profiles`, `genre_profiles`, `samples`, `examples`, `drafts`, `revisions` (parent links for the chain), `feedback_events`, `preferences`, `preference_versions`, `avoid_phrases`, `onboarding_answers`, `analysis_reports`, `benchmark_cases`, `app_settings`. Every repository method takes `profile_id` and filters on it; queries are parameterised. Deleting a profile cascades.
