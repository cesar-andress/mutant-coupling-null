# Test identifiers

Major `testMap.csv` names and Defects4J trigger lines are parsed by
`killmap.parse.parse_test_name`.

## Grammar

- `CLASS`
- `CLASS::METHOD`
- `CLASS::METHOD[DECORATION…]`
- `CLASS[METHOD]`
- `CLASS[METHOD[DECORATION…]]`

`METHOD` is the JUnit method name. Every trailing balanced `[…]` group is
**decoration** (parameter index or parameterized-run label). Decoration is
part of the canonical identity.

Canonical form: `CLASS::METHOD` or `CLASS::METHOD[i]` (decoration preserved).

Raw form is stored (`test_id_raw`) and is not used for equality.

## Collision rule

Two rows that differ only by decoration are **distinct executions**.
Dropping `[i]` is forbidden. Duplicate canonical IDs in one bug's test map
are a hard error.
