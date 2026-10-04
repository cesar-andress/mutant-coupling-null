# Per-test kill maps (T4)

Stock `defects4j mutation` does not set `exportKillMap`. This artifact applies a
minimal patch to `framework/projects/defects4j.build.xml`:

- `exportKillMap="true"`
- `testOrder=sort_methods` for the full relevant suite
- default map files `killMap.csv`, `covMap.csv`, `testMap.csv`

Apply:

```
./acquire/apply_killmap_patch.sh "$D4J_HOME"
```

Route A:

```
./scripts/route_a_killmap.sh Lang 1 results/raw/t4/Lang-1
```

Route B (stock, one test method at a time, no patch):

```
./scripts/route_b_per_test.sh Lang 1 results/raw/t4/Lang-1-route_b
```

Observed Major schemas (v3.0.1):

- `testMap.csv`: `TestNo,TestName,Runtime` with `TestName = Class[method]`
- `covMap.csv`: sparse `TestNo,MutantNo` (covered)
- `killMap.csv`: sparse `TestNo,MutantNo,FAIL|TIME|EXC` (kills only)

Cell semantics:

- killMap row → KILLED
- covMap row without killMap → SURVIVES (LIVE)
- neither → NOT_COVERED

Do not collapse NOT_COVERED into SURVIVES.
