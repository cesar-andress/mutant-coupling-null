# Full-study protocol deviations

POST_OUTCOME_PRIMARY count: **0**.

## D-FS-1 — Host timeout envelope around Docker workers

1. Exact change: wrap each `docker run` in host `timeout --kill-after=60 1860`
   and container `timeout --kill-after=30 1800`. Name containers
   `mcn-full-{project}-{bug}` for clean kill. Scientific per-bug timeout remains
   1800 s.
2. Reason: GNU `timeout` inside the container can leave Java/ant children
   running past the watchdog; host envelope is a deterministic infrastructure
   enforcement of the already-frozen timeout policy.
3. Timestamp: 2026-10-05T19:20:00Z
4. Novel full-study outcome used to choose the fix: NO (engineering health of
   the watchdog only; no coupling rates consulted).
5. Affected: execution reliability / TIMEOUT classification. Matching, event,
   estimand, bootstrap, population, and eligibility unchanged.
6. Bias of primary effect: none intended; may convert previously hung jobs into
   explicit TIMEOUT rather than indefinite RUNNING.
7. Classification: **POST_OUTCOME_NON_PRIMARY**

## D-FS-2 — Canonical test-ID collisions excluded from ingest (not merged)

1. Exact change: 10 on-disk kill maps (Chart-26; Compress-9/11/12/16/18/20/25/28/29)
   raised `CanonicalIdCollisionError` because Major `testMap.csv` lists two or more
   `TestNo` with the identical `TestName` string. They are classified
   PARSER_FAILURE / MATRIX_INVALID and omitted from canonical tables and RQ1.
   Distinct parameterized decorations were **not** collapsed.
2. Reason: T8 uniqueness invariant. Merging would fabricate a single test
   identity. Isolated to Chart cloning tests and Compress `LongPathTest::testArchive`
   duplicates, not a global trigger-leakage or mutant-ID defect.
3. Timestamp: 2026-10-06T15:30:00Z (post-acquisition ETL/QA)
4. Coupling outcomes of these 10 bugs: not estimated (parse refused). Remaining
   sample not selected using their rates.
5. Affected: sample completeness (491 maps on disk → 481 canonical). Event,
   matching, bootstrap unchanged.
6. Classification: **POST_OUTCOME_NON_PRIMARY**
