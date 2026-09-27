#!/usr/bin/env Rscript
# Download the data the Signac pack needs: the 10x Genomics multiome PBMC
# dataset (pbmc_granulocyte_sorted_10k) used by both the Signac multiome
# vignette and the multiome half of Seurat's WNN vignette, from the URLs the
# Signac vignette gives. Run once at image build time.
#
#   Rscript packs/signac/data/fetch_data.R        (honours $CURELAB_DATASETS)

dest <- file.path(Sys.getenv("CURELAB_DATASETS", "/opt/curelab/datasets"), "pbmc_multiome_10k")
dir.create(dest, recursive = TRUE, showWarnings = FALSE)
options(timeout = max(7200, getOption("timeout")))

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
    unlink(file)
    Sys.sleep(2^attempt)
  }
  stop("could not download ", url)
}

# Signac vignettes/pbmc_multiomic.Rmd, "View data download code"
base <- "https://cf.10xgenomics.com/samples/cell-arc/1.0.0/pbmc_granulocyte_sorted_10k/"
for (f in c(
  "pbmc_granulocyte_sorted_10k_filtered_feature_bc_matrix.h5",
  "pbmc_granulocyte_sorted_10k_atac_fragments.tsv.gz",
  "pbmc_granulocyte_sorted_10k_atac_fragments.tsv.gz.tbi"
)) {
  fetch(paste0(base, f), file.path(dest, f))
}

sizes <- file.size(list.files(dest, full.names = TRUE))
message(sprintf("Multiome data ready in %s (%.2f GB)", dest, sum(sizes) / 1024^3))
