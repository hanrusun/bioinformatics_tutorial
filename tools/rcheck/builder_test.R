# End-to-end test of packs/seurat/reference/build_reference.R, run in webR by
# check.mjs. webR ships base R only, so yaml and jsonlite are swapped for tiny
# stand-ins and the "vignette code" is plain base R. This exercises the
# builder's own control flow (prep scripts, an empty globalenv per mission,
# expected values, checkpoints, wrong solutions, failure reporting), which the
# Docker build otherwise only reaches after several minutes of downloads.

stubs <- new.env()
evalq({
  # test state lives here: the builder empties globalenv before every mission
  quit_status <- NA
  log <- character()
  curelab_test_quit <- function(status) quit_status <<- status
  curelab_test_quit_status <- function() quit_status
  curelab_test_log <- function(line) log <<- c(log, line)
  curelab_test_lines <- function() log

  MOCK <- list(
    "pack.yaml" = list(campaigns = list("demo")),
    "01_sum.yaml" = list(
      id = "demo-01-sum",
      setup = 'load_prep("numbers")',
      # the solution also tramples names the builder itself uses
      solution = paste(
        "total <- sum(numbers)",
        'm <- "trampled"; w <- 0; file <- 1; pack <- NULL; failures <- "trampled"; fail <- NULL',
        sep = "\n"
      ),
      expected = list(total = "total"),
      state = list("numbers", "total"),
      check = 'curelab_check({ curelab_obj("total"); expect_equal_ref(total, "total", "`total` is not the sum.") })',
      wrong_solutions = list(
        list(why = "drops the first value", code = "total <- sum(numbers[-1])"),
        list(why = "typo", code = "total <- sum(numberz)")
      )
    ),
    "02_sort.yaml" = list(
      id = "demo-02-sort",
      setup = 'load_checkpoint("demo-01-sum")',
      solution = "ranked <- sort(numbers)",
      expected = list(ranked = "ranked"),
      state = list("ranked"),
      check = paste0(
        "curelab_check({\n",
        '  expect_true(!exists("m", envir = globalenv(), inherits = FALSE), "the previous mission leaked into this one")\n',
        '  expect_true(exists("total", envir = globalenv(), inherits = FALSE), "the checkpoint did not carry `total`")\n',
        '  expect_equal_ref(ranked, "ranked", "`ranked` is not sorted.")\n',
        "})"
      ),
      wrong_solutions = list(list(why = "descending", code = "ranked <- sort(numbers, decreasing = TRUE)"))
    ),
    "03_lenient.yaml" = list(
      id = "demo-03-lenient",
      setup = 'load_checkpoint("demo-02-sort")',
      solution = "top <- max(ranked)",
      check = "curelab_check({ expect_true(TRUE, 'never fails') })",
      wrong_solutions = list(list(why = "minimum instead", code = "top <- min(ranked)"))
    ),
    "04_broken.yaml" = list(
      id = "demo-04-broken",
      setup = 'load_checkpoint("demo-02-sort")',
      solution = "stop('the vignette moved on')",
      check = "curelab_check({ expect_true(TRUE, 'x') })"
    )
  )

  fake_read_yaml <- function(path) {
    x <- MOCK[[basename(path)]]
    if (is.null(x)) stop("no mock for ", path)
    x
  }
  fake_write_json <- function(x, path, ...) dput(x, file = path)
  fake_read_json <- function(path, ...) dget(path)
  fake_toJSON <- function(x, auto_unbox = TRUE) {
    paste0('{"pass":', tolower(as.character(x$pass)), ',"message":"', gsub('"', '\\\\"', x$message), '"}')
  }
  fake_fromJSON <- function(txt) {
    list(pass = grepl('"pass":true', txt, fixed = TRUE), message = sub('^.*"message":"(.*)"\\}\\s*$', "\\1", txt))
  }
}, stubs)
attach(stubs, name = "curelab_stubs", warn.conflicts = FALSE)

local({
  swap <- function(src, pairs) {
    for (from in names(pairs)) src <- gsub(from, pairs[[from]], src, fixed = TRUE)
    src
  }
  for (d in c("/mock/r/prep", "/mock/reference", "/mock/campaigns/demo/missions")) dir.create(d, recursive = TRUE)
  writeLines(swap(readLines("/src/helpers.R"), c(
    "jsonlite::toJSON" = "fake_toJSON",
    "jsonlite::read_json" = "fake_read_json"
  )), "/mock/r/helpers.R")
  builder <- swap(readLines("/src/build_reference.R"), c(
    "yaml::read_yaml" = "fake_read_yaml",
    "jsonlite::read_json" = "fake_read_json",
    "jsonlite::write_json" = "fake_write_json",
    "jsonlite::fromJSON" = "fake_fromJSON",
    'requireNamespace("yaml", quietly = TRUE)' = "TRUE",
    "grDevices::pdf(NULL)" = "invisible(NULL)",
    "quit(status = 1)" = "curelab_test_quit(1)"
  ))
  writeLines(builder, "/mock/reference/build_reference.R")
  writeLines(c("numbers <- c(3, 1, 4, 1, 5)", 'save_checkpoint("prep-numbers", "numbers")'), "/mock/r/prep/01_numbers.R")
  file.create("/mock/pack.yaml")
  for (f in c("01_sum.yaml", "02_sort.yaml", "03_lenient.yaml", "04_broken.yaml")) {
    file.create(file.path("/mock/campaigns/demo/missions", f))
  }
})

setwd("/mock/reference")
# the builder defaults to <pack>/reference only when this is unset
Sys.unsetenv("CURELAB_REFERENCE_DIR")
# webR cannot start child R processes, so run every mission in this one
Sys.setenv(CURELAB_BUILD_IN_PROCESS = "1")
withCallingHandlers(
  source("/mock/reference/build_reference.R"),
  message = function(m) {
    curelab_test_log(sub("\n$", "", conditionMessage(m)))
    invokeRestart("muffleMessage")
  }
)
local({
  builder_log <- curelab_test_lines()
  log <- paste(builder_log, collapse = "\n")
  fails <- grep("^  FAIL: ", builder_log, value = TRUE)
  expected <- dget("/mock/reference/expected.json")
  results <- character()
  ok <- function(cond, label) results <<- c(results, sprintf("%s builder: %s", if (isTRUE(cond)) "PASS" else "FAIL", label))

  ok(grepl("== prep 01_numbers.R", log, fixed = TRUE) && file.exists("/mock/reference/checkpoints/prep-numbers.rds"), "runs prep scripts")
  ok(identical(expected[["demo-01-sum"]][["total"]], 14), "records expected values")
  ok(identical(expected[["demo-02-sort"]][["ranked"]], c(1, 1, 3, 4, 5)), "records vector expected values")
  ok(setequal(names(readRDS("/mock/reference/checkpoints/demo-01-sum.rds")$objects), c("numbers", "total")), "saves the mission state")
  ok(grepl("demo-01-sum", log) && !any(grepl("demo-01-sum", fails)), "solution that tramples builder names is harmless")
  ok(grepl("rejects 'drops the first value'", log, fixed = TRUE), "check rejects a wrong solution")
  ok(grepl("wrong solution 'typo' errors", log, fixed = TRUE), "erroring wrong solution is noted")
  ok(!any(grepl("demo-02-sort", fails)), "each mission starts from an empty globalenv plus its checkpoint")
  ok(any(grepl("demo-03-lenient: check ACCEPTED the wrong solution 'minimum instead'", fails, fixed = TRUE)), "reports a check that accepts a wrong solution")
  ok(any(grepl("demo-04-broken: reference solution errored: the vignette moved on", fails, fixed = TRUE)), "reports a failing reference solution")
  ok(length(fails) == 2, paste("exactly two problems reported, got", length(fails)))
  ok(identical(curelab_test_quit_status(), 1), "exits with status 1 when anything failed")
  writeLines(results)
  if (any(startsWith(results, "FAIL"))) writeLines(c("--- builder log", builder_log))
})
