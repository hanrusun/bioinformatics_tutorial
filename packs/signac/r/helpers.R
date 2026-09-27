# Cure Lab helpers for the Signac pack.
#
# The Signac pack builds on the Seurat pack: pack.yaml's init_code sources the
# Seurat pack's checker and checkpoint helpers (packs/seurat/r/helpers.R)
# first, then this file, which adds a few for the 10x multiome data baked
# into the image.

# SCTransform sends the whole count matrix to its workers through the future
# package, which refuses more than 500 MB by default; this dataset needs more.
options(future.globals.maxSize = 8 * 1024^3)

local({
  if ("curelab_signac" %in% search()) detach("curelab_signac", character.only = TRUE)
  env <- new.env()
  evalq({
    # The 10x multiome PBMC files used by both the Signac and the Seurat
    # WNN vignettes (pbmc_granulocyte_sorted_10k).
    curelab_multiome <- function(file = c("h5", "fragments")) {
      file <- match.arg(file)
      dir <- file.path(Sys.getenv("CURELAB_DATASETS", "/opt/curelab/datasets"), "pbmc_multiome_10k")
      switch(file,
        h5 = file.path(dir, "pbmc_granulocyte_sorted_10k_filtered_feature_bc_matrix.h5"),
        fragments = file.path(dir, "pbmc_granulocyte_sorted_10k_atac_fragments.tsv.gz")
      )
    }

    # Use every core for the slow chromatin steps (chromVAR, TSS enrichment).
    curelab_parallel <- function() {
      workers <- max(1L, parallel::detectCores(logical = FALSE) %||% 1L)
      if (requireNamespace("BiocParallel", quietly = TRUE)) {
        BiocParallel::register(BiocParallel::MulticoreParam(workers = workers, progressbar = FALSE))
      }
      invisible(workers)
    }
  }, envir = env)
  attach(env, name = "curelab_signac", warn.conflicts = FALSE)
})
