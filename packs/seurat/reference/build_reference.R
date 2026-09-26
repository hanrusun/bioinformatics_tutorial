#!/usr/bin/env Rscript
# Build and self-test the Seurat pack's reference data.
#
# For every campaign, mission by mission (in file-name order), exactly as the
# game runs them:
#   1. start from an empty global environment
#   2. run the mission `setup` (loads the previous mission's checkpoint)
#   3. run the verbatim vignette `solution`
#   4. evaluate the `expected` expressions      -> reference/expected.json
#   5. save the `state` objects                 -> reference/checkpoints/<id>.rds
#   6. run the hidden `check`: it MUST pass
#   7. for every `wrong_solutions` entry: empty env + setup + wrong code;
#      the check MUST fail
# Prep scripts in r/prep/ run first and build shared starting points.
#
# Usage:
#   Rscript build_reference.R                 build everything, then test
#   Rscript build_reference.R --verify-only   re-test against existing files
#   Rscript build_reference.R --campaign c1-basics --skip-wrong
#
# Exits non-zero if any check misbehaves, so a broken mission fails the
# Docker build instead of reaching a learner.

args <- commandArgs(trailingOnly = TRUE)
verify_only <- "--verify-only" %in% args
skip_wrong <- "--skip-wrong" %in% args
only_campaign <- if ("--campaign" %in% args) args[which(args == "--campaign") + 1] else NULL

script_path <- local({
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg)) normalizePath(sub("^--file=", "", file_arg[1])) else normalizePath("build_reference.R")
})
pack_dir <- normalizePath(file.path(dirname(script_path), ".."))
if (!nzchar(Sys.getenv("CURELAB_REFERENCE_DIR"))) {
  Sys.setenv(CURELAB_REFERENCE_DIR = file.path(pack_dir, "reference"))
}
source(file.path(pack_dir, "r", "helpers.R"))
if (!requireNamespace("yaml", quietly = TRUE)) install.packages("yaml", repos = "https://cloud.r-project.org")

ref_dir <- Sys.getenv("CURELAB_REFERENCE_DIR")
expected_path <- file.path(ref_dir, "expected.json")
dir.create(file.path(ref_dir, "checkpoints"), recursive = TRUE, showWarnings = FALSE)
grDevices::pdf(NULL) # swallow any plots drawn while building
set.seed(42)

# ------------------------------------------------------------------ helpers

clear_env <- function() {
  rm(list = ls(globalenv(), all.names = TRUE), envir = globalenv())
}

run_code <- function(code) {
  if (is.null(code) || !nzchar(trimws(code))) return(invisible(NULL))
  for (expr in parse(text = code, keep.source = FALSE)) {
    eval(expr, envir = globalenv())
  }
  invisible(NULL)
}

run_check <- function(mission) {
  curelab_reset_expected()
  curelab_set_mission(mission$id)
  out <- utils::capture.output(run_code(mission$check))
  line <- grep("@@CURELAB_RESULT@@", out, value = TRUE, fixed = TRUE)
  if (!length(line)) return(list(pass = FALSE, message = "the check printed no result"))
  jsonlite::fromJSON(sub(".*@@CURELAB_RESULT@@", "", line[length(line)]))
}

as_json_value <- function(x) {
  if (is.factor(x)) x <- as.character(x)
  if (inherits(x, "table")) x <- as.vector(x)
  if (is.list(x)) stop("expected values must be atomic vectors")
  unname(x)
}

mission_files <- function(campaign_dir) {
  files <- list.files(file.path(campaign_dir, "missions"), pattern = "\\.ya?ml$", full.names = TRUE)
  files[order(basename(files), method = "radix")]
}

elapsed <- function(t0) sprintf("%.1fs", as.numeric(difftime(Sys.time(), t0, units = "secs")))

failures <- character()
fail <- function(...) {
  msg <- paste0(...)
  failures <<- c(failures, msg)
  message("  FAIL: ", msg)
}

# ------------------------------------------------------------------ prep

if (!verify_only) {
  for (prep in sort(list.files(file.path(pack_dir, "r", "prep"), pattern = "\\.R$", full.names = TRUE), method = "radix")) {
    t0 <- Sys.time()
    message("== prep ", basename(prep))
    clear_env()
    ok <- tryCatch({
      source(prep, local = globalenv())
      TRUE
    }, error = function(e) {
      fail("prep ", basename(prep), ": ", conditionMessage(e))
      FALSE
    })
    if (ok) message("   done in ", elapsed(t0))
  }
}

# ------------------------------------------------------------------ missions

pack <- yaml::read_yaml(file.path(pack_dir, "pack.yaml"))
expected_all <- if (file.exists(expected_path)) jsonlite::read_json(expected_path, simplifyVector = TRUE) else list()

for (campaign_id in unlist(pack$campaigns)) {
  if (!is.null(only_campaign) && campaign_id != only_campaign) next
  campaign_dir <- file.path(pack_dir, "campaigns", campaign_id)
  message("\n#### campaign ", campaign_id)
  for (file in mission_files(campaign_dir)) {
    m <- yaml::read_yaml(file)
    t0 <- Sys.time()
    message("== ", m$id, " (", basename(file), ")")

    # 1-3: setup + reference solution
    clear_env()
    curelab_set_mission(m$id)
    ok <- tryCatch({
      run_code(m$setup)
      run_code(m$solution)
      TRUE
    }, error = function(e) {
      fail(m$id, ": reference solution errored: ", conditionMessage(e))
      FALSE
    })
    if (!ok) next

    # 4: expected values
    if (!verify_only && length(m$expected)) {
      values <- list()
      for (key in names(m$expected)) {
        values[[key]] <- tryCatch(
          as_json_value(eval(parse(text = m$expected[[key]]), envir = globalenv())),
          error = function(e) {
            fail(m$id, ": expected '", key, "' errored: ", conditionMessage(e))
            NULL
          }
        )
      }
      expected_all[[m$id]] <- values
      jsonlite::write_json(expected_all, expected_path, auto_unbox = TRUE, digits = NA, pretty = TRUE)
    }

    # 5: checkpoint for the next mission
    if (!verify_only && length(m$state)) {
      tryCatch(
        save_checkpoint(m$id, unlist(m$state)),
        error = function(e) fail(m$id, ": could not save checkpoint: ", conditionMessage(e))
      )
    }

    # 6: the check must accept the reference solution
    res <- run_check(m)
    if (!isTRUE(res$pass)) fail(m$id, ": check rejected the reference solution: ", res$message)
    else message("   reference solution passes (", elapsed(t0), ")")

    # 7: the check must reject each wrong solution
    if (!skip_wrong) {
      for (w in m$wrong_solutions) {
        clear_env()
        curelab_set_mission(m$id)
        errored <- tryCatch({
          run_code(m$setup)
          run_code(w$code)
          FALSE
        }, error = function(e) TRUE)
        if (errored) {
          # an error is also a failed attempt in the game; still note it
          message("   wrong solution '", w$why, "' errors (counts as a failed attempt)")
          next
        }
        res <- run_check(m)
        if (isTRUE(res$pass)) fail(m$id, ": check ACCEPTED the wrong solution '", w$why, "'")
        else message("   rejects '", w$why, "': ", res$message)
      }
    }
  }
}

if (length(failures)) {
  message("\n", length(failures), " problem(s):\n", paste0(" - ", failures, collapse = "\n"))
  quit(status = 1)
}
message("\nAll missions verified.")
