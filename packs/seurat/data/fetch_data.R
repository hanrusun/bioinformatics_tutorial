#!/usr/bin/env Rscript
# Download every dataset the Seurat pack needs, from the same sources the
# Seurat vignettes use. Run once at image build time.
#
#   Rscript packs/seurat/data/fetch_data.R        (honours $CURELAB_DATASETS)

dest <- Sys.getenv("CURELAB_DATASETS", "/opt/curelab/datasets")
dir.create(dest, recursive = TRUE, showWarnings = FALSE)
options(timeout = max(3600, getOption("timeout")))

fetch <- function(url, file) {
  if (file.exists(file) && file.size(file) > 0) return(invisible(file))
  message("Downloading ", url)
  for (attempt in 1:4) {
    ok <- tryCatch({
      utils::download.file(url, file, mode = "wb", quiet = TRUE)
      TRUE
    }, error = function(e) {
      message("  attempt ", attempt, " failed: ", conditionMessage(e))
      FALSE
    })
    if (ok && file.exists(file) && file.size(file) > 0) return(invisible(file))
    Sys.sleep(2^attempt)
  }
  stop("could not download ", url)
}

# 1. PBMC 3k, 10x Genomics (pbmc3k_tutorial.Rmd, "Set up the Seurat object")
pbmc_dir <- file.path(dest, "pbmc3k")
if (!file.exists(file.path(pbmc_dir, "filtered_gene_bc_matrices", "hg19", "matrix.mtx"))) {
  dir.create(pbmc_dir, showWarnings = FALSE)
  tgz <- file.path(tempdir(), "pbmc3k.tar.gz")
  fetch("https://cf.10xgenomics.com/samples/cell/pbmc3k/pbmc3k_filtered_gene_bc_matrices.tar.gz", tgz)
  utils::untar(tgz, exdir = pbmc_dir)
}
stopifnot(file.exists(file.path(pbmc_dir, "filtered_gene_bc_matrices", "hg19", "matrix.mtx")))

# 2. Cell-cycle vignette files, Nestorowa et al. (cell_cycle_vignette.Rmd)
cc_dir <- file.path(dest, "cell_cycle")
cc_file <- file.path(cc_dir, "nestorawa_forcellcycle_expressionMatrix.txt")
if (!file.exists(cc_file)) {
  dir.create(cc_dir, showWarnings = FALSE)
  zip <- file.path(tempdir(), "cell_cycle_vignette_files.zip")
  fetch("https://www.dropbox.com/s/3dby3bjsaf5arrw/cell_cycle_vignette_files.zip?dl=1", zip)
  unzipped <- file.path(tempdir(), "cell_cycle_unzipped")
  utils::unzip(zip, exdir = unzipped)
  found <- list.files(unzipped, pattern = "nestorawa_forcellcycle_expressionMatrix\\.txt$",
                      recursive = TRUE, full.names = TRUE)
  if (!length(found)) stop("the cell-cycle archive did not contain the expression matrix")
  file.copy(found[1], cc_file)
}

# 3. Donor assignments for the ifnb cells (de_vignette.Rmd, pseudobulk section)
dm_dir <- file.path(dest, "demuxlet")
dir.create(dm_dir, showWarnings = FALSE)
base <- "https://raw.githubusercontent.com/yelabucsf/demuxlet_paper_code/master/fig3/"
for (f in c("ye1.ctrl.8.10.sm.best", "ye2.stim.8.10.sm.best")) fetch(paste0(base, f), file.path(dm_dir, f))

# 4. SeuratData datasets (essential_commands, integration_introduction,
#    de_vignette and integration_mapping vignettes)
suppressPackageStartupMessages(library(SeuratData))
for (ds in c("pbmc3k", "ifnb", "panc8")) {
  suppressWarnings(InstallData(ds))
}
message("All datasets ready in ", dest)
