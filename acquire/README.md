# Acquire Defects4J

`setup_defects4j.sh` clones the pinned tag from `env/pin.env` and runs upstream `init.sh` (Major 3.0.1, project repositories).

It does not copy Defects4J into Git. A working clone may exist under `external/defects4j/` (gitignored).

The Docker image runs this script during build.
