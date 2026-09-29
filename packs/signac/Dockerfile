# syntax=docker/dockerfile:1.7
#
# Cure Lab, Signac pack: single-cell chromatin and 10x multiome analysis
# with Signac and Seurat on human data (hg38). It is built on the R base of
# the Seurat image (R, Seurat and the game's Jupyter kernel), not on the
# finished Seurat image, so changes to the game engine or web UI only rebuild
# the last steps here. docker compose builds the R base first:
#   docker compose up --build signac          (then open http://localhost:8001)
# or by hand, from the repository root:
#   docker build -f packs/seurat/Dockerfile --target r-base -t curelab-r-base .
#   docker build -f packs/signac/Dockerfile -t curelab-signac .
ARG R_BASE=curelab-r-base

# ---------------------------------------------------------------- web UI
# (the same steps as in the Seurat image, so Docker reuses that build)
FROM node:22-bookworm-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------------------------------------------------------------- game
FROM ${R_BASE}

RUN useradd --create-home --uid 1001 curelab \
 && mkdir -p /data && chown curelab:curelab /data

# Signac, pinned to the release whose vignettes the pack is verified against,
# and the Bioconductor packages used by the Signac multiome vignette and the
# multiome half of Seurat's WNN vignette (hg38 genome and gene annotations,
# chromVAR motif analysis), hdf5r to read 10x .h5 files, and two packages
# Signac only suggests: biovizBase (GetGRangesFromEnsDb) and ggforce (peak-gene
# links in coverage plots). presto is already in the Seurat image.
# chromVAR (and motifmatchr) ask for C++11, but the RcppArmadillo in the base
# image needs C++14 or later, so those builds use C++17 instead.
RUN mkdir -p /root/.R \
 && printf 'CXX11STD = -std=gnu++17\nCXX11FLAGS += -std=gnu++17\n' > /root/.R/Makevars \
 && Rscript -e "pak::pkg_install(c('stuart-lab/signac@1.17.1', 'hdf5r', 'bioc::GenomeInfoDb', 'bioc::EnsDb.Hsapiens.v86', 'bioc::BSgenome.Hsapiens.UCSC.hg38', 'bioc::chromVAR', 'bioc::JASPAR2020', 'bioc::TFBSTools', 'bioc::motifmatchr', 'bioc::glmGamPoi', 'bioc::biovizBase', 'ggforce'))" \
 && rm -rf /root/.R /root/.cache/R /tmp/*

ENV CURELAB_PACK_DIR=/opt/curelab/app/packs/signac \
    CURELAB_REFERENCE_DIR=/opt/curelab/reference-signac

# Data (its own layer: only re-downloaded if this script changes)
COPY packs/signac/data/fetch_data.R /opt/curelab/app/packs/signac/data/fetch_data.R
RUN Rscript /opt/curelab/app/packs/signac/data/fetch_data.R && rm -rf /tmp/*

# Pack content, then build + self-test the reference checkpoints with the
# Seurat pack's builder (the Signac pack reuses its helpers)
COPY illnesses/ /opt/curelab/app/illnesses/
COPY packs/seurat/r/ /opt/curelab/app/packs/seurat/r/
COPY packs/seurat/reference/build_reference.R /opt/curelab/app/packs/seurat/reference/build_reference.R
COPY packs/signac/ /opt/curelab/app/packs/signac/
RUN Rscript /opt/curelab/app/packs/seurat/reference/build_reference.R --pack /opt/curelab/app/packs/signac \
 && rm -rf /tmp/*

# Engine + built web UI
COPY engine/ /opt/curelab/app/engine/
RUN /opt/curelab/venv/bin/pip install --no-cache-dir /opt/curelab/app/engine
COPY --from=web /src/web/dist /opt/curelab/app/web/dist

USER curelab
WORKDIR /home/curelab
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
CMD ["curelab", "--host", "0.0.0.0", "--port", "8000"]
