# Adding a tool pack (and its illness)

Cure Lab's engine is tool-agnostic. It runs learner code in a **Jupyter
kernel**, grades it with hidden checks written in the same language, and
knows nothing about R or Seurat. A new tool (Scanpy, Signac, DESeq2, …) is a
new directory under `packs/`. The house rule is **one illness and one patient
per campaign**.

```
packs/<tool>/
  pack.yaml                    tool, kernel, source pin, init code, debug rules
  campaigns/<campaign>/
    campaign.yaml              title, illness id, unlock rule
    missions/NN_<slug>.yaml    one file per mission, run in file-name order
    quizzes.yaml               journal-club questions
    notebook/NN_<slug>.yaml    preloaded notebook pages
  <helpers>                    check helpers in the tool's language
  reference/                   builds checkpoints + expected values at image build
  Dockerfile                   base image with the tool + a Jupyter kernel
illnesses/<disease>.yaml       patient + trait tree (tool-agnostic)
web/public/art/<patient>/      optional custom art (see ART.md)
```

`engine/tests/fixtures/pack_py` is a complete, minimal Python pack and makes
a good template.

## pack.yaml

```yaml
id: scanpy
name: Scanpy
tool: Scanpy (Python)
tool_version: "1.11.0"
language: python
kernel: python3                 # any installed Jupyter kernelspec
editor_mode: python             # CodeMirror mode: r or python
source_pin:                     # where every quote must come from, pinned
  repo: scverse/scanpy-tutorials
  ref: <tag or commit>
  path: ""
  site: https://scanpy.readthedocs.io/en/stable/tutorials/
init_code: |                    # run in a fresh kernel before each mission
  exec(open("{pack_dir}/helpers.py").read())
mission_prelude: curelab_set_mission("{mission_id}")
campaigns: [c1-basics]
debug:                          # regex -> explanation, shown for free
  - pattern: "NameError: name '(\\w+)' is not defined"
    help: A name is used before it exists…
```

## A mission

```yaml
id: c1-m03-filter
title: Triage the sample
points: 6                       # 85 points of missions + 15 of quizzes = 100 per campaign
source: {vignette: <file in source_pin.path>, section: <exact heading>, quote: <verbatim sentence>}
briefing: |                     # Markdown; {name}, {full_name}, {companion} are filled in
task: ["What the check verifies, one bullet each"]
starter_code: |                 # shown in the editor (may contain blanks)
setup: |                        # hidden, runs at mission start: usually loads the previous checkpoint
solution: |                     # the verbatim tutorial code (lines may end in "# curelab: adapted")
check: |                        # hidden; must print one @@CURELAB_RESULT@@{json} line
hints: [concept, "function + arguments", "```code```"]
debug: [{pattern: ..., help: ...}]
notebook_pages: [c1-nb02-qc]
state: [adata]                  # objects saved as the checkpoint for the next mission
expected: {n_cells: "adata.n_obs"}      # evaluated after the solution at build time
wrong_solutions: [{why: ..., code: ...}] # the check must reject these (tested at build)
```

The check protocol is one line on stdout:
`@@CURELAB_RESULT@@{"pass": true|false, "message": "..."}`. For R, see
`packs/seurat/r/helpers.R` (`curelab_check`, `curelab_obj`,
`expect_equal_ref`, `expect_param`, …). For Python, see `init_code` in the
fixture pack.

## An illness

```yaml
id: glioblastoma
name: Glioblastoma
short: GBM
patient: {id, name, first_name, pronouns: {subj, obj, poss}, age, sex, background,
          presenting, companion, baseline_vitals: {hr, rr, spo2, sbp, dbp, temp}, art}
admit_note / stage_notes / progression_note / cure_note / loss_note
traits:
  - id: headache
    name: Headache
    category: symptom            # symptom | complication | mutation | resistance | event
    tier: 1                      # 1-4; lower tiers are favoured early
    requires: []                 # prerequisites (a tree)
    excludes: []                 # mutually exclusive traits (e.g. driver mutations)
    severity: [1.0, 1.6]         # lethality gain range per evolution
    vitals: {hr: 4}              # offsets on the monitor
    overlay: wince               # art overlay key (see ART.md)
    note: "{name} has a pounding headache every morning."
    source: https://…            # where the clinical feature comes from
```

## Checklist

1. `pytest engine/tests`: content loads and the campaign totals 100 points
   (add a structural test like `test_seurat_pack.py`).
2. `python tools/verify_sources.py --pack packs/<tool>`: every quote and
   solution line is verbatim.
3. `python tools/simulate_balance.py --assert`: the illness keeps the balance
   targets.
4. Add a service to `docker-compose.yml`, and a CI job that builds the image
   (the build runs every reference solution and check).
