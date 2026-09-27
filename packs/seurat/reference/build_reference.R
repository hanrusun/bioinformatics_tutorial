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
# Each prep script and each mission runs in its own R process, like the
# fresh kernel the game starts for every mission. Memory is then released
# between missions, and each process's peak (written to
# reference/memory.tsv) is the RAM that mission needs.
#
# Usage:
#   Rscript build_reference.R                 build everything, then test
#   Rscript build_reference.R --verify-only   re-test against existing files
#   Rscript build_reference.R --campaign c1-basics --skip-wrong
#   Rscript build_reference.R --mission <mission file>   one mission only
#   Rscript build_reference.R --in-process    everything in this R process
#                                             (also CURELAB_BUILD_IN_PROCESS=1)
#
# Exits non-zero if any check misbehaves, so a broken mission fails the
# Docker build instead of reaching a learner.
#
# All builder state lives inside local() below, never in the global
# environment: every mission starts from an empty globalenv (as in a fresh
# kernel), and vignette code must not be able to clobber the builder.

local({
  args <- commandArgs(trailingOnly = TRUE)
  arg_value <- function(flag) if (flag %in% args) args[which(args == flag) + 1] else NULL
  verify_only <- "--verify-only" %in% args
  skip_wrong <- "--skip-wrong" %in% args
  only_campaign <- arg_value("--campaign")
  one_mission <- arg_value("--mission")
  one_prep <- arg_value("--prep")

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
  memory_log <- file.path(ref_dir, "memory.tsv")
  dir.create(file.path(ref_dir, "checkpoints"), recursive = TRUE, showWarnings = FALSE)
  grDevices::pdf(NULL) # swallow any plots drawn while building
  set.seed(42)

  rscript <- file.path(R.home("bin"), "Rscript")
  in_process <- "--in-process" %in% args || nzchar(Sys.getenv("CURELAB_BUILD_IN_PROCESS")) || !file.exists(rscript)

  # ------------------------------------------------------------------ helpers

  clear_env <- function() {
    rm(list = ls(globalenv(), all.names = TRUE), envir = globalenv())
    # collect now: otherwise the last mission's objects can still be held
    # while the next checkpoint loads, doubling the peak memory
    invisible(gc())
    set.seed(42) # the wipe also removed .Random.seed; keep builds reproducible
  }

  # Resident memory of this R process, now and at its peak (Linux only).
  memory <- function() {
    status <- if (file.exists("/proc/self/status")) readLines("/proc/self/status") else character()
    kb <- function(field) {
      line <- grep(paste0("^", field, ":"), status, value = TRUE)
      if (length(line)) as.numeric(gsub("[^0-9]", "", line)) / 1024^2 else NA
    }
    c(now = kb("VmRSS"), peak = kb("VmHWM"))
  }
  memory_note <- function() {
    m <- memory()
    if (is.na(m[["now"]])) "" else sprintf(", %.1f GB in use, peak %.1f GB", m[["now"]], m[["peak"]])
  }
  record_memory <- function(step) {
    peak <- memory()[["peak"]]
    if (!is.na(peak)) cat(sprintf("%s\t%.2f\n", step, peak), file = memory_log, append = TRUE)
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

  prep_files <- function() {
    sort(list.files(file.path(pack_dir, "r", "prep"), pattern = "\\.R$", full.names = TRUE), method = "radix")
  }

  elapsed <- function(t0) sprintf("%.1fs", as.numeric(difftime(Sys.time(), t0, units = "secs")))

  failures <- character()
  fail <- function(...) {
    msg <- paste0(...)
    failures <<- c(failures, msg)
    message("  FAIL: ", msg)
  }

  finish <- function() {
    if (length(failures)) {
      message("\n", length(failures), " problem(s):\n", paste0(" - ", failures, collapse = "\n"))
      quit(status = 1)
    }
  }

  # ------------------------------------------------------------------ one step

  run_prep <- function(prep) {
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
    if (ok) message("   done in ", elapsed(t0), memory_note())
    record_memory(paste0("prep ", basename(prep)))
  }

  run_mission <- function(file) {
    m <- yaml::read_yaml(file)
    t0 <- Sys.time()
    message("== ", m$id, " (", basename(file), ")")
    on.exit(record_memory(m$id), add = TRUE)

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
    if (!ok) return(invisible(FALSE))

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
      # re-read: with one process per mission, earlier missions wrote this file
      expected_all <- if (file.exists(expected_path)) jsonlite::read_json(expected_path, simplifyVector = TRUE) else list()
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
    else message("   reference solution passes (", elapsed(t0), memory_note(), ")")

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
    invisible(TRUE)
  }

  # Run one step in a fresh R process (or here, in in-process mode).
  step <- function(flag, file, label) {
    if (in_process) {
      if (flag == "--prep") run_prep(file) else run_mission(file)
      return(invisible())
    }
    passthrough <- c(if (verify_only) "--verify-only", if (skip_wrong) "--skip-wrong")
    status <- system2(rscript, c(shQuote(script_path), flag, shQuote(file), passthrough))
    if (!identical(as.integer(status), 0L)) fail(label, " failed (details above)")
  }

  # ------------------------------------------------------------------ main

  if (!is.null(one_prep)) {
    run_prep(one_prep)
    finish()
  } else if (!is.null(one_mission)) {
    run_mission(one_mission)
    finish()
  } else {
    if (!verify_only) unlink(memory_log)
    if (!verify_only) {
      for (prep in prep_files()) step("--prep", prep, paste0("prep ", basename(prep)))
    }
    pack <- yaml::read_yaml(file.path(pack_dir, "pack.yaml"))
    for (campaign_id in unlist(pack$campaigns)) {
      if (!is.null(only_campaign) && campaign_id != only_campaign) next
      message("\n#### campaign ", campaign_id)
      for (file in mission_files(file.path(pack_dir, "campaigns", campaign_id))) {
        step("--mission", file, basename(file))
      }
    }

    if (file.exists(memory_log) && !in_process) {
      mem <- utils::read.delim(memory_log, header = FALSE, col.names = c("step", "peak_gb"), stringsAsFactors = FALSE)
      group <- ifelse(startsWith(mem$step, "prep"), "prep", sub("-.*", "", mem$step))
      message("\nPeak memory, each step in a fresh R session (as in the game):")
      for (g in unique(group)) {
        rows <- mem[group == g, ]
        top <- rows[which.max(rows$peak_gb), ]
        message(sprintf("  %-5s up to %.1f GB (%s)", g, top$peak_gb, top$step))
      }
      message(sprintf("Peak memory of the reference build: %.1f GB", max(mem$peak_gb)))
    } else {
      peak <- memory()[["peak"]]
      if (!is.na(peak)) message(sprintf("\nPeak memory of the reference build: %.1f GB", peak))
    }
    finish()
    message("\nAll missions verified.")
  }
})
