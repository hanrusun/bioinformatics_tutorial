# Cure Lab

**Plague Inc. in reverse, for learning bioinformatics.** A patient is getting
sicker, and your code is the cure. Work through real single-cell analyses in
R. Every correct mission moves the cure forward, and every wrong answer lets
the disease evolve.

There are two tool packs, each in its own Docker image. The **Seurat 5.5.1**
pack has three campaigns, each with its own patient:

| Campaign | Patient | What you learn | Source vignettes |
|---|---|---|---|
| **Seurat Basics** | Walter Brandt, 64: non-small cell lung cancer | Raw 10x counts → QC → normalization → variable genes → scaling → PCA → dimensionality → clustering → UMAP → markers → annotation | `pbmc3k_tutorial` |
| **Seurat for the Multiome Lab** (unlocks after Basics) | Mia Okoye, 2: neuroblastoma | Seurat v5 object anatomy and layers, subsetting, cell-cycle scoring and regression, split layers + Harmony integration, conserved markers, pseudobulk DESeq2, label transfer, merging for co-embedding | `essential_commands`, `cell_cycle_vignette`, `integration_introduction`, `seurat5_integration`, `de_vignette`, `integration_mapping`, `seurat5_atacseq_integration_vignette` |
| **CRISPR Screens with Mixscape** (unlocks after Basics) | Anjali Rao, 38: acute myeloid leukemia | Pooled CRISPR screens read out in single cells (ECCITE-seq): CLR-normalized protein, confounders in RNA clustering, local perturbation signatures (`CalcPerturbSig`), knockout vs non-perturbed calls (`RunMixscape`), guide efficiency, PD-L1 validation, LDA of perturbation responses | `mixscape_vignette` |

The optional **Signac 1.17.1** pack is built on top of the Seurat image, so
you only download and build it if you want it:

| Campaign | Patient | What you learn | Source vignettes |
|---|---|---|---|
| **Chromatin and Regulators** | Tomás Ferreira, 19: Ewing sarcoma | Human 10x multiome (RNA + ATAC in the same cells): a Signac `ChromatinAssay` with hg38 annotations, ATAC QC (nucleosome signal, TSS enrichment), SCTransform and LSI, weighted nearest neighbors, cell-type annotation, coverage plots, peak-to-gene links, JASPAR motifs and chromVAR, ranking the transcription factors of each cell type | Signac `pbmc_multiomic`; Seurat `weighted_nearest_neighbor_analysis` (multiome half) |

Campaign 2 covers the Seurat side of the
[NBL scMultiomics TRN pipeline](https://github.com/wbaopaul/NBL_scMultiomics_Paper/tree/main/TRN-analysis).
[docs/NBL_TRN_READINESS.md](docs/NBL_TRN_READINESS.md) maps each call in those
scripts to the mission that teaches it, and what the Signac pack adds
(chromatin processing, peak-to-gene links, motifs and chromVAR).

## Quick start

You need Docker (with Compose).

```bash
git clone https://github.com/hanrusun/bioinformatics_tutorial.git
cd bioinformatics_tutorial
docker compose up --build seurat
```

Then open <http://localhost:8000>.

The first build downloads the datasets and runs every mission's reference
solution once. On a 4-core machine it takes about 40 minutes and produces an
image of about 9 GB (measured in CI). Later starts are instant. Your progress and lab notebook are kept in a
Docker volume (`curelab-seurat-data`).

For the Signac pack:

```bash
docker compose up --build signac
```

Then open <http://localhost:8001>. Compose builds the Seurat image first if
you don't have it yet; the Signac image reuses all of its layers and only adds
Signac, the hg38 genome and annotations, the 10x multiome data and its own
reference checkpoints. It keeps its progress in its own volume
(`curelab-signac-data`), so both games can run side by side.

The port is bound to `127.0.0.1` on purpose: the game executes the code you
type, so only your own machine can reach it. To skip the Campaign 1
requirement, set `CURELAB_UNLOCK_ALL: "1"` in `docker-compose.yml`.

### System requirements

Measured in CI on a 4-core Linux machine:

| | Needs |
|---|---|
| Disk | about 9 GB for the image, plus a few GB of scratch space while it builds |
| Build time | about 40 minutes the first time (one Campaign 2 step alone takes 15) |
| RAM to build | about 10 GB: the heaviest mission (the build runs one mission at a time) |
| RAM to play Campaign 1 | about 2 GB for R, plus about 1 GB for the game |
| RAM to play Campaign 2 | about 4 GB for R, plus about 1 GB |
| RAM to play Campaign 3 (Mixscape) | about 9.5 GB for R, plus about 1 GB: the 20,729-cell CRISPR screen |

On Linux, Docker can use all of your RAM. On macOS and Windows, Docker Desktop
runs in a virtual machine with its own memory limit: set **Settings →
Resources → Memory** to at least 12 GB to build the image and play Campaign 3
(6 GB is enough for Campaigns 1 and 2 once the image is built).

The Signac image needs more; see
[Signac pack requirements](#signac-pack-requirements) below.

### Signac pack requirements

Measured in the same CI run, building the Signac image on top of the Seurat
one:

| | Needs |
|---|---|
| Disk | a 14.8 GB image, but 8.9 GB of it are the Seurat image's layers, so about 6 GB more: Signac and the hg38 genome and annotations (1.3 GB), the 10x multiome data (2.2 GB) and the reference checkpoints (2.3 GB) |
| Build time | about 50 minutes after the Seurat image; the chromVAR mission alone takes 20 |
| RAM to build and play | about 12.7 GB for R at the heaviest mission (SCTransform on 10,412 cells), plus about 1 GB for the game. ATAC quality control peaks at 9.6 GB; the other missions at 5 to 8 GB |

The chromVAR mission runs on every CPU core, and its worker processes (not
included above) share most of their memory with the main R process. Give
Docker Desktop at least 14 GB of memory for the Signac pack, which in
practice means a machine with 16 GB of RAM or more (32 GB is comfortable).

## How to play

![Walter's room, the lab and the cure/lethality/health bars](docs/img/game.png)

<sub>Screenshots are from the built-in Python demo pack, which exercises the
same engine and UI without needing the R image.</sub>

| Mia's symptoms evolve with every mistake | Anjali, sixteen mistakes in | Tomás (Signac pack) | Cure found |
|---|---|---|---|
| ![Mia](docs/img/mia.png) | ![Anjali](docs/img/anjali.png) | ![Tomás](docs/img/tomas.png) | ![Win screen](docs/img/won.png) |

- **Cure research**: each coding mission adds 5–11% by complexity, and each
  journal-club question adds 1%. Each campaign totals exactly 100%. Reach it
  while the patient is alive to win.
- **Lethality**: the disease worsens slowly on its own. Every wrong **Submit**
  and every wrong quiz answer makes it evolve a real symptom or mutation from
  the illness's trait tree (a persistent cough, then a pleural effusion, then
  T790M resistance…). The patient's picture, vitals and chart change with
  each one. About one mistake in four instead triggers a random **ward
  event**: Walter starts smoking again, Mia swallows a crayon. Most events
  make things worse; a few (under a quarter) are harmless. You lose if the
  patient's health reaches 0. The **Disease** tab lists what has evolved so
  far; traits that haven't happened yet stay hidden unless you press
  **Reveal the whole disease tree**.
- **Journal club**: finishing a mission unlocks its quiz questions; the
  mission list shows how many ("1 quiz") until you answer them.
- **Run is free, Submit is graded.** Explore as much as you like. The clock
  pauses while your code runs and while the tab is hidden, so reading the docs
  in another tab never costs the patient anything.
- **Research points (RP)** pay for hints, at 1 RP per hint tier. The tiers
  are: concept, then function and arguments, then the verbatim vignette code.
  You earn RP in the **lab notebook**:
  - reading a preloaded page (scroll to the end, then ✓ Read) gives +1 or
    +2 RP;
  - writing your own page of 40+ words gives +1 RP, up to one page per
    mission you have attempted.
- **🩺 Explain error** is always free. It matches your error against common
  R/Seurat mistakes and explains them without giving the answer away.
- **Export** your notebook at any time, or from the end screen: copy your
  notes to the clipboard, or download your notes or the whole notebook
  (reference pages with citations, your notes, the mission log and the
  patient chart) as Markdown.
- **Difficulty**: Casual, Normal or Brutal. This changes how fast the disease
  creeps and how hard each mistake hits.

## Grounded in the official vignettes

Every mission, quiz and notebook page cites a vignette pinned to the exact
version installed in the image: `satijalab/seurat@v5.5.1` for the Seurat pack
([docs/SOURCES.md](docs/SOURCES.md)), and `stuart-lab/signac@1.17.1` plus the
Seurat WNN vignette for the Signac pack
([docs/SOURCES-signac.md](docs/SOURCES-signac.md)).
`tools/verify_sources.py` checks, and CI enforces, that:

- every quoted sentence appears **verbatim** in the cited vignette,
- every cited section is a real heading, and
- every line of each mission's reference solution is vignette code.

Five lines in the Seurat pack are marked as adapted, and the verifier
reports them: the local data path, the learner's own PC choice, and the
`obj → ifnb` / `harmony` names in the Harmony missions. The Signac pack
adapts five: the paths to the multiome files in the image, and three cluster
numbers in the annotation mission. In this build, clusters 8, 9 and 11 come
out in a different order than in the vignette's own run, so its labels
would call monocytes "CD8 Naive". The annotation check therefore also tests
every cluster's label against its marker genes.

The hidden checks never hard-code answers. When an image is built,
`packs/seurat/reference/build_reference.R` (which also builds the Signac pack):

1. runs each verbatim solution,
2. records the expected values,
3. saves the checkpoint the next mission starts from, and
4. asserts that the check accepts the reference solution and rejects a set of
   deliberately wrong ones.

If any check misbehaves, the Docker build fails.

## Architecture

```
engine/            tool-agnostic game server (Python/FastAPI + jupyter_client)
web/               Preact + CodeMirror front end, patient art, vitals monitor
illnesses/         illness + patient definitions (trait trees), one per campaign
packs/seurat/      the Seurat tool pack: missions, quizzes, notebook pages,
                   R helpers, dataset fetcher, reference builder, Dockerfile
packs/signac/      the Signac tool pack (image built FROM the Seurat one;
                   reuses its helpers and reference builder)
tools/             verify_sources.py, simulate_balance.py, rcheck (R code in webR)
docs/              SOURCES (generated), NBL_TRN_READINESS, ADDING_A_TOOL, ART
```

The engine never knows it is running R. It runs learner code in a Jupyter
kernel (IRkernel here), so a future Scanpy pack swaps in a different kernel
and brings its own illness and patient. A pack can cite several pinned
source repositories (the Signac pack cites Signac's and Seurat's vignettes). See
[docs/ADDING_A_TOOL.md](docs/ADDING_A_TOOL.md).

## Development

You can run everything except the R pack without R or Docker, using the small
Python demo pack at `engine/tests/fixtures/pack_py`:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e "engine[test]"
(cd web && npm ci && npm run build)
python -m curelab --pack engine/tests/fixtures/pack_py --unlock-all   # http://127.0.0.1:8000
```

For UI work, run `cd web && npm run dev`. It serves on :5173 and proxies
`/api` to :8000.

| Check | Command |
|---|---|
| Engine unit + API tests (real Jupyter kernel) | `pytest engine/tests` |
| Balance targets | `python tools/simulate_balance.py --assert` |
| Vignette grounding (+ regenerates docs/SOURCES.md) | `python tools/verify_sources.py` |
| Same for the Signac pack (+ docs/SOURCES-signac.md) | `python tools/verify_sources.py --pack packs/signac` |
| R code parses; checker helpers and the reference builder tested on a mock pack (webR, no R install needed) | `cd tools/rcheck && npm install && npm test` |
| Web typecheck, unit tests, build | `cd web && npm run typecheck && npm test && npm run build` |
| End-to-end (Playwright, demo pack) | `cd web && npx playwright install chromium && npm run e2e` |
| Everything R, for real | `docker compose build seurat` (runs every solution and check) |
| Everything R for the Signac pack | `docker compose --profile signac build signac` |

## Balance

All numbers live in [`engine/curelab/balance.yaml`](engine/curelab/balance.yaml).
`simulate_balance.py` plays hundreds of simulated players against the real
engine and illness trees. They are made-up profiles, not measurements of real
learners. Health declines at twice the original rate (`h_max_per_hour: 300`).
On Normal:

- A patient with no mistakes survives about 5.5 hours of counted play (the
  clock only runs while the tab is visible and no code is running).
- The simulated "typical" player (about 30 wrong submissions and quiz
  answers over 2.5 hours of counted play) wins about 40–60% of games.
- The simulated reckless player (about 50 mistakes) always loses.

Real sessions are usually shorter and gentler than that. Health falls with
the square of lethality, so early mistakes barely show: an hour of counted
play with 10 mistakes leaves the patient at about 96% health (98% before
the decline was doubled).

## Art

The patient art is original flat-vector SVG in `web/src/art/`. It includes
breathing, blinking, an ECG and stage-dependent pallor and lighting, plus
overlays for each symptom. You can swap in your own images per patient, per
stage and per symptom, without code changes; see [docs/ART.md](docs/ART.md).

## Credits

Tutorial text and code are quoted from the
[Seurat vignettes](https://satijalab.org/seurat/) (© Satija Lab and
collaborators), pinned to v5.5.1, and the
[Signac vignettes](https://stuartlab.org/signac/) (© Stuart Lab), pinned to
1.17.1. The datasets come from 10x Genomics, SeuratData, Nestorowa et al.
(2016), Kang et al. (2018) and Papalexi et al. (2021), fetched from the URLs
the vignettes use; motifs come from JASPAR 2020. The patients are fictional, and the symptom trees
paraphrase public clinical descriptions (NCI PDQ); they are game flavor, not
medical advice. The game mechanics are inspired by *Plague Inc.* (Ndemic
Creations); this project is not affiliated with it.
