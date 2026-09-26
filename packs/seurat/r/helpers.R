# Cure Lab helpers for the Seurat pack.
#
# Sourced into a fresh R kernel before every mission (pack.yaml `init_code`)
# and by reference/build_reference.R at image build time. Everything is
# defined in an environment attached to the search path as "curelab", so the
# helpers work from learner code and hidden checks without cluttering ls().

local({
  if ("curelab" %in% search()) detach("curelab", character.only = TRUE)
  env <- new.env()
  evalq({
    .curelab_state <- new.env()
    .curelab_state$mission <- NA_character_
    .curelab_state$expected <- NULL

    CURELAB_REFERENCE_DIR <- Sys.getenv("CURELAB_REFERENCE_DIR", "/opt/curelab/reference")
    CURELAB_DATASETS <- Sys.getenv("CURELAB_DATASETS", "/opt/curelab/datasets")

    # ------------------------------------------------------------------ setup

    curelab_set_mission <- function(id) {
      .curelab_state$mission <- id
      invisible(id)
    }

    curelab_libraries <- function(extra = character()) {
      for (pkg in c("dplyr", "Seurat", "patchwork", extra)) {
        suppressPackageStartupMessages(library(pkg, character.only = TRUE))
      }
      invisible(TRUE)
    }

    curelab_checkpoint_path <- function(id) {
      file.path(CURELAB_REFERENCE_DIR, "checkpoints", paste0(id, ".rds"))
    }

    # The most recent logged Seurat command whose name is `prefix` or starts
    # with `prefix.` (e.g. "FindNeighbors" matches "FindNeighbors.RNA.pca").
    curelab_command <- function(obj, prefix) {
      cmds <- names(obj@commands)
      hits <- cmds[cmds == prefix | startsWith(cmds, paste0(prefix, "."))]
      if (!length(hits)) return(NULL)
      stamps <- vapply(hits, function(h) as.numeric(obj@commands[[h]]@time.stamp), numeric(1))
      obj@commands[[hits[which.max(stamps)]]]
    }

    command_param <- function(obj, prefix, param) {
      cmd <- curelab_command(obj, prefix)
      if (is.null(cmd)) return(NULL)
      cmd@params[[param]]
    }

    ran_after <- function(obj, first, second) {
      a <- curelab_command(obj, first)
      b <- curelab_command(obj, second)
      !is.null(a) && !is.null(b) && as.numeric(b@time.stamp) >= as.numeric(a@time.stamp)
    }

    # Checkpoints store Seurat objects without their scale.data layers (they
    # are large and cheap to recompute) plus what is needed to rebuild them.
    strip_scale_data <- function(obj) {
      info <- list()
      for (assay in SeuratObject::Assays(obj)) {
        layers <- SeuratObject::Layers(obj[[assay]])
        scale_layers <- layers[startsWith(layers, "scale.data")]
        if (!length(scale_layers)) next
        cmd <- curelab_command(obj, paste0("ScaleData.", assay))
        params <- if (is.null(cmd)) list() else cmd@params
        info[[assay]] <- list(
          features = rownames(SeuratObject::LayerData(obj, assay = assay, layer = scale_layers[1])),
          vars.to.regress = params$vars.to.regress,
          do.scale = if (is.null(params$do.scale)) TRUE else params$do.scale,
          do.center = if (is.null(params$do.center)) TRUE else params$do.center
        )
        for (l in scale_layers) {
          obj <- suppressWarnings(SeuratObject::`LayerData<-`(obj, assay = assay, layer = l, value = NULL))
        }
      }
      list(object = obj, info = info)
    }

    restore_scale_data <- function(obj, info) {
      commands <- obj@commands
      for (assay in names(info)) {
        i <- info[[assay]]
        obj <- suppressWarnings(suppressMessages(Seurat::ScaleData(
          obj,
          assay = assay,
          features = i$features,
          vars.to.regress = i$vars.to.regress,
          do.scale = i$do.scale,
          do.center = i$do.center,
          verbose = FALSE
        )))
      }
      # keep the learner-visible command log exactly as it was saved
      obj@commands <- commands
      obj
    }

    save_checkpoint <- function(id, names, envir = globalenv()) {
      objects <- mget(names, envir = envir)
      scale <- list()
      for (nm in names) {
        if (inherits(objects[[nm]], "Seurat")) {
          stripped <- strip_scale_data(objects[[nm]])
          objects[[nm]] <- stripped$object
          if (length(stripped$info)) scale[[nm]] <- stripped$info
        }
      }
      path <- curelab_checkpoint_path(id)
      dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
      saveRDS(list(objects = objects, scale = scale), path)
      invisible(path)
    }

    load_checkpoint <- function(id, envir = globalenv()) {
      path <- curelab_checkpoint_path(id)
      if (!file.exists(path)) {
        stop("Checkpoint '", id, "' is missing. Rebuild the image (packs/seurat/reference/build_reference.R).")
      }
      cp <- readRDS(path)
      for (nm in names(cp$objects)) {
        obj <- cp$objects[[nm]]
        if (!is.null(cp$scale[[nm]])) obj <- restore_scale_data(obj, cp$scale[[nm]])
        assign(nm, obj, envir = envir)
      }
      invisible(names(cp$objects))
    }

    load_prep <- function(name, envir = globalenv()) load_checkpoint(paste0("prep-", name), envir)

    # ----------------------------------------------------------------- checks

    curelab_fail <- function(message) {
      stop(structure(class = c("curelab_fail", "error", "condition"),
                     list(message = message, call = NULL)))
    }

    # Evaluate a block of expectations in a scratch environment whose parent
    # is the learner's global environment, then report the result as one JSON
    # line that the game engine parses.
    curelab_check <- function(expr) {
      code <- substitute(expr)
      scratch <- new.env(parent = globalenv())
      result <- tryCatch(
        {
          suppressWarnings(suppressMessages(eval(code, envir = scratch)))
          list(pass = TRUE, message = "All checks passed.")
        },
        curelab_fail = function(e) list(pass = FALSE, message = conditionMessage(e)),
        error = function(e) list(pass = FALSE, message = paste("The checker hit an error:", conditionMessage(e)))
      )
      cat("@@CURELAB_RESULT@@", as.character(jsonlite::toJSON(result, auto_unbox = TRUE)), "\n", sep = "")
      invisible(result$pass)
    }

    expect_true <- function(condition, message) {
      if (!isTRUE(condition)) curelab_fail(message)
      invisible(TRUE)
    }

    curelab_obj <- function(name, class = NULL, hint = NULL) {
      if (!exists(name, envir = globalenv(), inherits = FALSE)) {
        curelab_fail(paste0("There is no object called `", name, "` yet.", if (!is.null(hint)) paste0(" ", hint) else ""))
      }
      obj <- get(name, envir = globalenv(), inherits = FALSE)
      if (!is.null(class) && !inherits(obj, class)) {
        curelab_fail(sprintf("`%s` should be a %s object, but it is a %s.", name, class, paste(class(obj), collapse = "/")))
      }
      obj
    }

    expect_columns <- function(df, columns, what) {
      missing <- setdiff(columns, colnames(df))
      if (length(missing)) {
        curelab_fail(sprintf("%s is missing the column(s) %s.", what, paste(sQuote(missing, FALSE), collapse = ", ")))
      }
      invisible(TRUE)
    }

    expected <- function(key, mission = .curelab_state$mission) {
      if (is.null(.curelab_state$expected)) {
        path <- file.path(CURELAB_REFERENCE_DIR, "expected.json")
        if (!file.exists(path)) stop("reference values are missing (", path, "); rebuild the image")
        .curelab_state$expected <- jsonlite::read_json(path, simplifyVector = TRUE)
      }
      value <- .curelab_state$expected[[mission]][[key]]
      if (is.null(value)) stop("no reference value '", key, "' for mission ", mission)
      value
    }

    curelab_reset_expected <- function() {
      .curelab_state$expected <- NULL
      invisible(NULL)
    }

    .fmt <- function(x) {
      if (!length(x)) return("nothing")
      if (is.numeric(x)) x <- format(x, big.mark = ",", scientific = FALSE, trim = TRUE)
      paste(x, collapse = ", ")
    }

    expect_equal_ref <- function(actual, key, message, tolerance = 1e-6, show = TRUE) {
      target <- expected(key)
      ok <- length(actual) == length(target) && if (is.numeric(target) && is.numeric(actual)) {
        isTRUE(all.equal(as.numeric(actual), as.numeric(target), tolerance = tolerance, check.attributes = FALSE))
      } else {
        all(as.character(actual) == as.character(target))
      }
      if (!isTRUE(ok)) {
        detail <- if (show && length(target) <= 6 && length(actual) <= 6) {
          sprintf(" (expected %s; found %s)", .fmt(target), .fmt(actual))
        } else ""
        curelab_fail(paste0(message, detail))
      }
      invisible(TRUE)
    }

    expect_command <- function(obj, prefix, message) {
      if (is.null(curelab_command(obj, prefix))) curelab_fail(message)
      invisible(TRUE)
    }

    expect_param <- function(obj, prefix, param, value, message) {
      got <- command_param(obj, prefix, param)
      if (is.null(got)) curelab_fail(message)
      same <- if (is.numeric(value)) {
        is.numeric(got) && length(got) == length(value) && isTRUE(all.equal(as.numeric(got), as.numeric(value)))
      } else {
        length(got) == length(value) && setequal(as.character(got), as.character(value))
      }
      if (!same) curelab_fail(sprintf("%s (you used %s)", message, .fmt(got)))
      invisible(TRUE)
    }

    expect_reduction <- function(obj, name, message) {
      if (!name %in% SeuratObject::Reductions(obj)) curelab_fail(message)
      invisible(TRUE)
    }
  }, envir = env)
  attach(env, name = "curelab", warn.conflicts = FALSE)
})

# Plot defaults for the in-game console (IRkernel renders ggplot objects).
if (isNamespaceLoaded("IRkernel") || "IRkernel" %in% loadedNamespaces()) {
  options(
    jupyter.plot_mimetypes = "image/png",
    repr.plot.width = 9,
    repr.plot.height = 5.5,
    repr.plot.res = 110
  )
}
options(Seurat.object.assay.version = "v5", warn = 1)
