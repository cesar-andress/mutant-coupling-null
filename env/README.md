# Environment

Do not install experimental dependencies globally.

This directory will later pin a project-local environment (Python, Java, Defects4J, mutation tool). Nothing is installed in this initialization.

Suggested later layout (not created as live environments):

- a project virtualenv that is gitignored;
- pinned `requirements.txt` / lock files after the first authorized setup.

See also `../containers/`.
