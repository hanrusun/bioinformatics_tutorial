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

    # Which clusters carry a cell-type name that doesn't fit what they
    # express? `expr` is genes x cells (log-normalized), `clusters` and
    # `labels` have one entry per cell, and `lineages` is a named list of
    # list(labels = <cell-type names>, genes = <marker genes>). Each cluster
    # with at least `min_cells` cells scores every lineage by its strongest
    # marker (z-score of the cluster means across clusters); only lineages
    # that name one of those clusters compete, so markers of an absent
    # population can't win on noise. Returns the misfits as a data frame.
    curelab_label_fit <- function(expr, clusters, labels, lineages, min_cells = 50) {
      clusters <- as.character(clusters)
      label_of <- tapply(as.character(labels), clusters, function(v) v[1])
      groups <- split(seq_along(clusters), clusters)
      groups <- groups[lengths(groups) >= min_cells]
      lineage_of <- function(lab) {
        hit <- names(Filter(function(l) lab %in% l$labels, lineages))
        if (length(hit)) hit[1] else NA_character_
      }
      named <- vapply(names(groups), function(g) lineage_of(label_of[[g]]), character(1))
      used <- lineages[names(lineages) %in% named]
      genes <- intersect(unique(unlist(lapply(used, `[[`, "genes"))), rownames(expr))
      means <- matrix(vapply(groups, function(i) {
        sub <- expr[genes, i, drop = FALSE]
        if (inherits(sub, "Matrix")) Matrix::rowMeans(sub) else rowMeans(sub)
      }, numeric(length(genes))), nrow = length(genes), dimnames = list(genes, names(groups)))
      z <- t(scale(t(means)))
      z[is.na(z)] <- 0
      score <- matrix(vapply(used, function(l) {
        apply(z[intersect(l$genes, genes), , drop = FALSE], 2, max)
      }, numeric(length(groups))), nrow = length(groups), dimnames = list(names(groups), names(used)))
      fits <- colnames(score)[max.col(score, ties.method = "first")]
      bad <- is.na(named) | named != fits
      data.frame(cluster = names(groups)[bad], label = unname(label_of[names(groups)[bad]]),
        looks_like = fits[bad], stringsAsFactors = FALSE)
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
