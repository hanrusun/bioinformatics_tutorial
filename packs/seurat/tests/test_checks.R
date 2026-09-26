#!/usr/bin/env Rscript
# Re-run every mission's reference solution and wrong solutions against the
# hidden checks, using the checkpoints and expected values already built by
# reference/build_reference.R. Fails (exit 1) if any check accepts a wrong
# answer or rejects the reference answer.
#
#   Rscript packs/seurat/tests/test_checks.R [--campaign ID]

file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
here <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1]))) else getwd()
builder <- normalizePath(file.path(here, "..", "reference", "build_reference.R"))
args <- c("--verify-only", commandArgs(trailingOnly = TRUE))
status <- system2(file.path(R.home("bin"), "Rscript"), c(shQuote(builder), args))
quit(status = status)
