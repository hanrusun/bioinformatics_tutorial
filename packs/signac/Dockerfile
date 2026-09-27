# syntax=docker/dockerfile:1.7
#
# Cure Lab, Signac pack: single-cell chromatin and 10x multiome analysis
# with Signac and Seurat on human data (hg38). It is built on top of the
# Seurat image, so it only adds what Signac needs. docker compose builds both
# in the right order:
#   docker compose up --build signac          (then open http://localhost:8001)
# or by hand, from the repository root:
#   docker build -f packs/seurat/Dockerfile -t curelab-seurat .
#   docker build -f packs/signac/Dockerfile \
#     --build-arg SEURAT_IMAGE=curelab-seurat -t curelab-signac .
# ("seurat" is the named build context docker-compose.yml passes in.)
ARG SEURAT_IMAGE=seurat
FROM ${SEURAT_IMAGE}

USER root

# Signac, pinned to the release whose vignettes the pack is verified against,
# and the Bioconductor packages used by the Signac multiome vignette and the
# multiome half of Seurat's WNN vignette (hg38 genome and gene annotations,
# chromVAR motif analysis), and hdf5r to read 10x .h5 files. presto is
# already in the Seurat image.
RUN Rscript -e "pak::pkg_install(c('stuart-lab/signac@1.17.1', 'hdf5r', 'bioc::GenomeInfoDb', 'bioc::EnsDb.Hsapiens.v86', 'bioc::BSgenome.Hsapiens.UCSC.hg38', 'bioc::chromVAR', 'bioc::JASPAR2020', 'bioc::TFBSTools', 'bioc::motifmatchr', 'bioc::glmGamPoi'))" \
 && rm -rf /root/.cache/R /tmp/*

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

COPY engine/ /opt/curelab/app/engine/
RUN /opt/curelab/venv/bin/pip install --no-cache-dir /opt/curelab/app/engine

USER curelab
