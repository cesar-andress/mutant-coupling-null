# Decisions (artifact-local)

Implementation decisions for the public artifact start here.

## A003

Author of the public artifact is César Andrés (ORCID 0009-0001-8968-3404). `.zenodo.json` and `CITATION.cff` are the Zenodo/GitHub citation files. No DOI until a hygiene-checked GitHub Release is archived.

## A002

Pin Defects4J to tag `v3.0.1` commit `6d54320e0db5a357f9ab38a8e4d2e5aead7e1c09`, not to default-branch HEAD `8c16da8230843cdc918eaf4ddb449637f02b83c6` observed on 2026-10-04. T3 uses stock `defects4j mutation` without `exportKillMap`.

## A001

Initialization only. No experiment. Original code under MIT. Third-party data remain under upstream licenses.
