# syntax=docker/dockerfile:1.7
#
# Cure Lab, Seurat pack. Build from the repository root:
#   docker compose build seurat        (or)
#   docker build -f packs/seurat/Dockerfile -t curelab-seurat .
#
# The first build downloads the datasets and runs every mission's reference
# solution (and its hidden checks) once; expect ~40 minutes and a ~9 GB image
# (measured in CI on 4 cores). The build fails if any mission check misbehaves.

# ---------------------------------------------------------------- web UI
FROM node:22-bookworm-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------------------------------------------------------------- game
# Official Seurat image: Seurat 5.5.1 + SeuratObject 5.4.0 on R 4.5.2
# (rocker/tidyverse), with harmony, presto, DESeq2, metap and SeuratData.
FROM satijalab/seurat:5.5.1

ENV CURELAB_HOME=/opt/curelab \
    CURELAB_DATASETS=/opt/curelab/datasets \
    CURELAB_REFERENCE_DIR=/opt/curelab/reference \
    CURELAB_PACK_DIR=/opt/curelab/app/packs/seurat \
    CURELAB_ILLNESS_DIR=/opt/curelab/app/illnesses \
    CURELAB_WEB_DIR=/opt/curelab/app/web/dist \
    CURELAB_DATA_DIR=/data \
    PATH=/opt/curelab/venv/bin:$PATH

# Python for the game engine + the Jupyter R kernel (IRkernel)
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-venv libzmq3-dev curl \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/curelab/venv \
 && /opt/curelab/venv/bin/pip install --no-cache-dir "jupyter_client>=8.6" "jupyter_core>=5" \
 && Rscript -e "pak::pkg_install(c('IRkernel', 'yaml', 'mixtools', 'reshape2'))" \
 && Rscript -e "IRkernel::installspec(name = 'ir', displayname = 'R', user = FALSE, prefix = '/opt/curelab/venv')" \
 && rm -rf /root/.cache/R /tmp/*

# Datasets (cached as their own layer: only re-downloaded if this script changes)
COPY packs/seurat/data/fetch_data.R /opt/curelab/app/packs/seurat/data/fetch_data.R
RUN Rscript /opt/curelab/app/packs/seurat/data/fetch_data.R && rm -rf /tmp/*

# Pack content, then build + self-test the reference checkpoints
COPY illnesses/ /opt/curelab/app/illnesses/
COPY packs/seurat/ /opt/curelab/app/packs/seurat/
RUN Rscript /opt/curelab/app/packs/seurat/reference/build_reference.R && rm -rf /tmp/*

# Engine + built web UI
COPY engine/ /opt/curelab/app/engine/
RUN /opt/curelab/venv/bin/pip install --no-cache-dir /opt/curelab/app/engine
COPY --from=web /src/web/dist /opt/curelab/app/web/dist

RUN useradd --create-home --uid 1001 curelab \
 && mkdir -p /data && chown curelab:curelab /data
USER curelab
WORKDIR /home/curelab
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1
CMD ["curelab", "--host", "0.0.0.0", "--port", "8000"]
