# Tests

`test_environment.sh` checks Java 11, the pinned Defects4J SHA/tag, Major presence, Lang-1 metadata, and that stock `defects4j.build.xml` does not enable `exportKillMap`.

`test_smoke_outputs.sh` checks that a completed T3 smoke left a manifest with the T3 invariants (no exportKillMap, no coupling statistic).
