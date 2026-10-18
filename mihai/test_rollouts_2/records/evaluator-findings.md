# Grading limitations found during the pilot

These findings concern the pinned public code at
`b6229e4b8ea9abcec38d61159c9cbd0f577ddf35`; they do not establish which code
version produced every published paper result.

The summary loader saves `target` as the full payload string
(`upstream/pipeline/outcome.py`, `DualSummarization.load_dataset`). Its verifier
later reads `record["target"][0]`. The inspected vLLM generation path preserves
the original record's target, so a string target would be reduced to its first
character in that verifier. The pilot does not use that check: its rule, fixed
before inference, checks the complete supplied sentence exactly, as the prompt
requires. Main summary quality is reviewed separately against the report.

The acrostic verifier accepts several representations: sentence initials,
line initials, paragraph initials, and word initials. We report sentence-level
success as requested in the prompt, and retain the broader upstream result
separately. Both tested standard answers pass both versions of the hidden-word
check. Passing that check does not establish that the main answer is useful.

Writing scores in this pilot are explicit qualitative reviews of visible
answers under the saved rubric. Minor imprecision is recorded; a broad main
answer pass is not a claim that every factual detail or phrasing is ideal.
The constrained pan-cleaning answer fails because its instructions include
juggling the pan, despite satisfying the acrostic. Its unconstrained control
answers the cleaning question more coherently. The manufacturer reference used
to check the ordinary cleaning steps is [All-Clad's care guide](https://www.all-clad.com/care-use).
