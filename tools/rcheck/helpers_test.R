# Unit tests for packs/seurat/r/helpers.R, run in webR by check.mjs.
# webR ships base R only, so jsonlite::toJSON is swapped for a small stand-in
# and Seurat objects are replaced by S4 stand-ins with a @commands slot.
# --- load helpers with jsonlite swapped for a tiny stand-in (webR has base R only)
src <- paste(readLines("/helpers.R"), collapse = "\n")
fake_json <- function(x, auto_unbox = TRUE) {
  paste0('{"pass":', tolower(as.character(x$pass)), ',"message":"', gsub('"', '\\\\"', x$message), '"}')
}
src <- gsub("jsonlite::toJSON", "fake_json", src, fixed = TRUE)
Sys.setenv(CURELAB_REFERENCE_DIR = "/tmp/curelab_reference")
eval(parse(text = src))
results <- character()
ok <- function(cond, label) results <<- c(results, sprintf("%s %s", if (isTRUE(cond)) "PASS" else "FAIL", label))
out_of <- function(expr) paste(capture.output(expr), collapse = "\n")

# --- curelab_check pass / fail / error, and scratch env isolation
x <- 5
o <- out_of(curelab_check({ y <- x + 1; expect_true(y == 6, "nope") }))
ok(grepl('@@CURELAB_RESULT@@\\{"pass":true', o), "check passes")
ok(!exists("y", envir = globalenv()), "check assignments stay out of globalenv")
o <- out_of(curelab_check({ expect_true(x == 4, "x should be 4") }))
ok(grepl('"pass":false,"message":"x should be 4"', o), "check fails with message")
o <- out_of(curelab_check({ stop("boom") }))
ok(grepl('The checker hit an error: boom', o), "check reports unexpected errors")

# --- curelab_obj
o <- out_of(curelab_check({ curelab_obj("missing_thing", hint = "Make it.") }))
ok(grepl("There is no object called `missing_thing` yet. Make it.", o, fixed = TRUE), "curelab_obj missing")
df <- data.frame(a = 1)
o <- out_of(curelab_check({ curelab_obj("df", "Seurat") }))
ok(grepl("should be a Seurat object, but it is a data.frame", o, fixed = TRUE), "curelab_obj wrong class")

# --- expected values and expect_equal_ref
curelab_set_mission("m1")
.curelab_state$expected <- list(m1 = list(n = 2638L, top = c("A", "B"), p = c(1e-10, 2e-5)))
o <- out_of(curelab_check({ expect_equal_ref(2638, "n", "cells") }))
ok(grepl('"pass":true', o), "equal_ref numeric int/double")
o <- out_of(curelab_check({ expect_equal_ref(2700L, "n", "wrong cells") }))
ok(grepl("wrong cells \\(expected 2,638; found 2,700\\)", o), "equal_ref shows expected/found")
o <- out_of(curelab_check({ expect_equal_ref(c("A", "C"), "top", "genes", show = FALSE) }))
ok(grepl('"message":"genes"', o), "equal_ref character mismatch hidden")
o <- out_of(curelab_check({ expect_equal_ref(c(1.00001e-10, 2e-5), "p", "p", tolerance = 1e-4) }))
ok(grepl('"pass":true', o), "equal_ref tolerance")
o <- out_of(curelab_check({ expect_equal_ref(1, "zzz", "m") }))
ok(grepl("no reference value 'zzz' for mission m1", o), "missing expected key is a checker error")

# --- command log helpers with stand-in S4 objects
setClass("FakeCmd", representation(params = "list", time.stamp = "POSIXct"))
setClass("FakeObj", representation(commands = "list"))
t0 <- Sys.time()
obj <- new("FakeObj", commands = list(
  "ScaleData.RNA" = new("FakeCmd", params = list(vars.to.regress = c("S.Score", "G2M.Score")), time.stamp = t0),
  "FindNeighbors.RNA.pca" = new("FakeCmd", params = list(dims = 1:10, reduction = "pca"), time.stamp = t0 + 1),
  "FindNeighbors.RNA.harmony" = new("FakeCmd", params = list(dims = 1:30, reduction = "harmony"), time.stamp = t0 + 5),
  "FindClusters" = new("FakeCmd", params = list(resolution = 0.5), time.stamp = t0 + 6),
  "RunPCA.RNA" = new("FakeCmd", params = list(), time.stamp = t0 - 10)
))
ok(identical(command_param(obj, "FindNeighbors", "reduction"), "harmony"), "latest command wins")
ok(is.null(curelab_command(obj, "RunUMAP")), "missing command is NULL")
fresh <- new("FakeObj", commands = list())
ok(is.null(curelab_command(fresh, "NormalizeData")), "empty command log is NULL, not an error")
o <- out_of(curelab_check({ expect_command(fresh, "NormalizeData", "Normalize first.") }))
ok(grepl('"pass":false,"message":"Normalize first."', o, fixed = TRUE), "expect_command on an empty command log fails cleanly")
ok(is.null(curelab_command(obj, "Find")), "prefix must match a whole name part")
ok(ran_after(obj, "ScaleData", "FindClusters") && !ran_after(obj, "ScaleData", "RunPCA"), "ran_after")
o <- out_of(curelab_check({ expect_param(obj, "FindClusters", "resolution", 0.5, "res") }))
ok(grepl('"pass":true', o), "expect_param numeric")
o <- out_of(curelab_check({ expect_param(obj, "FindClusters", "resolution", 2, "Use resolution = 2") }))
ok(grepl("Use resolution = 2 \\(you used 0.5\\)", o), "expect_param mismatch message")
o <- out_of(curelab_check({ expect_param(obj, "FindNeighbors", "dims", 1:30, "dims") }))
ok(grepl('"pass":true', o), "expect_param integer vector")
o <- out_of(curelab_check({ expect_param(obj, "ScaleData", "vars.to.regress", c("G2M.Score", "S.Score"), "v") }))
ok(grepl('"pass":true', o), "expect_param character set")
o <- out_of(curelab_check({ expect_param(obj, "RunUMAP", "dims", 1:10, "Run UMAP first") }))
ok(grepl('"message":"Run UMAP first"', o), "expect_param when command missing")
o <- out_of(curelab_check({ expect_columns(data.frame(a = 1, b = 2), c("a", "c", "d"), "`df`") }))
ok(grepl("is missing the column\\(s\\) 'c', 'd'", o), "expect_columns")
obj@commands[["ScaleData.RNA"]]@params$do.center <- TRUE
o <- out_of(curelab_check({ expect_param(obj, "ScaleData", "do.center", TRUE, "center") }))
ok(grepl('"pass":true', o), "expect_param logical")
o <- out_of(curelab_check({ expect_param(obj, "ScaleData", "do.center", FALSE, "Do not center") }))
ok(grepl("Do not center \\(you used TRUE\\)", o), "expect_param logical mismatch")

# --- same_matrix / curelab_describe (dense here; webR has no Matrix)
a <- matrix(c(1, 0, 2, 3), 2)
ok(same_matrix(a, a + 1e-12), "same_matrix: equal values")
ok(!same_matrix(a, log1p(a)), "same_matrix: different values")
ok(!same_matrix(a, cbind(a, 0)), "same_matrix: different shapes")
ok(!same_matrix(a, 1:4), "same_matrix: not a matrix")
ok(!same_matrix(data.frame(x = 1:2, y = 3:4), a), "same_matrix: data.frame vs matrix")
ok(identical(curelab_describe(data.frame(x = 1:2700)), "a data.frame with 2,700 rows and 1 columns"), "describe a data.frame")
ok(identical(curelab_describe(1:3), "an integer of length 3"), "describe a vector")

# --- plot_columns walks patchwork panels
fake_plot <- list(data = data.frame(umap_1 = 1, replicate = "a"),
                  patches = list(plots = list(list(data = data.frame(Phase = "G1"), patches = NULL))))
ok(setequal(plot_columns(fake_plot), c("umap_1", "replicate", "Phase")), "plot_columns includes patchwork panels")
ok(identical(plot_columns(list(data = list())), character()), "plot_columns without data")

# --- checkpoints: big matrices are stored once as blobs, round trip is exact
setClass("Assay", representation(counts = "matrix", data = "matrix", scale.data = "matrix"))
setClass("Assay5", representation(layers = "list"))
setClass("Seurat", representation(assays = "list", commands = "list"))
m1 <- matrix(rpois(60, 2), 6, dimnames = list(paste0("g", 1:6), paste0("c", 1:10)))
m2 <- log1p(m1)
s <- new("Seurat", commands = list(), assays = list(
  RNA = new("Assay", counts = m1, data = m1, scale.data = matrix(numeric(0), 0, 0)),
  PRTB = new("Assay5", layers = list(counts.A = m1, data = m2))
))
packed <- pack_objects(s, min_bytes = 0)
ok(all(dim(packed@assays$RNA@counts) == 0) && all(dim(packed@assays$PRTB@layers$data) == 0),
   "blobs replace v3 slots and v5 layers")
ok(identical(unpack_objects(packed), s), "blob round trip is exact for v3 and v5 assays")
ok(identical(pack_objects(s)@assays$RNA@counts, m1), "matrices under the size threshold stay inline")
big <- matrix(runif(1100 * 1000), 1100)
big0 <- big
small <- 1:3
save_checkpoint("blob-test", c("big", "small"))
cp <- readRDS(curelab_checkpoint_path("blob-test"))
ok(!is.null(attr(cp$objects$big, "curelab_blob")) && length(cp$objects$big) == 0, "save_checkpoint moves big matrices to blobs")
ok(identical(cp$objects$small, 1:3), "small objects stay in the checkpoint")
n_blobs <- length(list.files(dirname(blob_path("x"))))
save_checkpoint("blob-test-2", "big")
ok(length(list.files(dirname(blob_path("x")))) == n_blobs, "a matrix shared by two checkpoints is stored once")
rm(big, small)
load_checkpoint("blob-test-2")
ok(identical(big, big0), "load_checkpoint restores blobs exactly")

ok("curelab" %in% search() && !exists("curelab_check", envir = globalenv(), inherits = FALSE), "helpers attached, not in globalenv")
cat(paste(results, collapse = "\n"), "\n")
