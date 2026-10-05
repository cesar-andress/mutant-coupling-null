"""SCHEMA_VERSION = 1 — canonical mutation tables."""

SCHEMA_VERSION = 1

BUGS_COLUMNS = [
    "project",
    "bug_id",
    "fixed_commit",
    "buggy_commit",
    "d4j_version",
    "d4j_sha",
    "n_trigger",
    "patch_files",
    "eligible",
    "exclusion_reason",
]

TESTS_COLUMNS = [
    "project",
    "bug_id",
    "test_id",
    "test_class",
    "test_method",
    "test_decoration",
    "test_id_raw",
    "is_trigger",
    "stable",
    "n_mutants_covered",
    "coverage_gain_if_added",
    "trigger_provenance",
    "timestamp_relation",
    "test_added_date",
]

MUTANTS_COLUMNS = [
    "project",
    "bug_id",
    "mutant_id",
    "operator",
    "mutated_file",
    "mutated_class",
    "mutated_method",
    "mutated_line",
    "is_in_patch_line",
    "is_in_patch_method",
    "is_in_patch_class",
]

CELLS_COLUMNS = [
    "project",
    "bug_id",
    "test_id",
    "mutant_id",
    "test_covers_mutant",
    "test_kills_mutant",
    "kill_reason",
]
