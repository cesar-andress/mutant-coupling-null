# Environment

Do not install experimental dependencies on the host.

Pinned values: `pin.env`.

- Defects4J requested version: 3.0.1
- Defects4J tag: `v3.0.1`
- Defects4J commit: `6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09`
- Upstream: `https://github.com/rjust/defects4j.git`
- Java: 11
- Major: 3.0.1 (Defects4J `init.sh` zip `major-3.0.1_jre11.zip`)
- Container base: `ubuntu:22.04`

Build:

```
docker build -f env/Dockerfile -t mutant-coupling-null:t3-env .
```

Or:

```
./scripts/run_t3_smoke.sh
```

That script builds the image and runs the Lang-1 FIXED stock-mutation smoke test.

The image clones Defects4J at the pinned tag. Do not vendor that clone in Git.

Note: on 2026-10-04, `origin/master` HEAD was `8c16da8230843cdc918eaf4ddb449637f02b83c6`. That is **not** `v3.0.1`. This artifact pins the release tag.
