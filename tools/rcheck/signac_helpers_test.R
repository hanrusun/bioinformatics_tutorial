# Unit tests for packs/signac/r/helpers.R, run in webR by check.mjs.
# The label-fit check is exercised on synthetic clusters shaped like the
# Signac reference build's (sizes and marker profiles from its build report).
source("/signac_helpers.R")
results <- character()
ok <- function(cond, label) results <<- c(results, sprintf("%s signac: %s", if (isTRUE(cond)) "PASS" else "FAIL", label))

genes <- c("LYZ", "CD14", "MS4A1", "IGHD", "CD3E", "IL7R", "NKG7", "GNLY", "LILRA4", "CLEC4C", "JCHAIN", "MZB1", "CD34")
profiles <- list(
  cd14mono = c(LYZ = 4, CD14 = 2, NKG7 = 0.1),
  cd16mono = c(LYZ = 2.5, CD14 = 0.4, NKG7 = 0.2),
  cdc = c(LYZ = 3, CD14 = 0.2),
  pdc = c(LILRA4 = 2, CLEC4C = 1.5, JCHAIN = 1, MZB1 = 1.5),
  naiveB = c(MS4A1 = 2, IGHD = 1.5),
  memB = c(MS4A1 = 2, IGHD = 0.5, MZB1 = 0.2),
  cd4naive = c(CD3E = 1.8, IL7R = 1.5),
  cd8naive = c(CD3E = 1.8, IL7R = 0.8, NKG7 = 0.2),
  cd4mem = c(CD3E = 1.8, IL7R = 1.8, NKG7 = 0.3),
  cytoT = c(CD3E = 1.5, NKG7 = 3, GNLY = 2.5, IL7R = 0.3),
  nk = c(NKG7 = 3, GNLY = 3.5, CD3E = 0.3),
  mait = c(CD3E = 1.7, IL7R = 1.5, NKG7 = 1.5),
  hspc = c(CD34 = 2),
  plasma = c(JCHAIN = 3, MZB1 = 3)
)
# cluster -> (cells in the build, profile, vignette label, label after adapting 8/9/11)
clusters <- read.table(header = TRUE, stringsAsFactors = FALSE, text = "
cluster cells profile vignette adapted
0 2376 cd14mono CD14_Mono CD14_Mono
1 1160 cd4naive CD4_Naive CD4_Naive
2 981 cd8naive CD8_Naive CD8_Naive
3 704 cd4mem CD4_TCM CD4_TCM
4 547 cd4mem CD4_TCM CD4_TCM
5 514 cd16mono CD16_Mono CD16_Mono
6_0 174 cytoT CD8_TEM_2 CD8_TEM_2
6_1 140 cytoT CD8_TEM_2 CD8_TEM_2
6_2 120 cytoT gdT gdT
6_3 45 cytoT gdT gdT
6_4 20 nk CD8_TEM_2 CD8_TEM_2
7 468 nk NK NK
8 442 cd14mono CD8_Naive CD14_Mono
9 372 naiveB CD14_Mono Intermediate_B
10 351 naiveB Naive_B Naive_B
11 345 cd8naive Intermediate_B CD8_Naive
12 327 cytoT CD8_TEM_1 CD8_TEM_1
13 289 cd4mem CD4_TEM CD4_TEM
14 224 cd4naive CD4_Naive CD4_Naive
15 194 cdc cDC cDC
16 189 cd4mem Treg Treg
17 142 memB Memory_B Memory_B
18 136 mait MAIT MAIT
19 108 pdc pDC pDC
20 26 hspc HSPC HSPC
21 18 plasma Plasma Plasma
")
clusters$vignette <- gsub("_", " ", clusters$vignette)
clusters$adapted <- gsub("_", " ", clusters$adapted)
clusters$vignette[clusters$vignette == "CD8 TEM 2"] <- "CD8 TEM_2"
clusters$adapted[clusters$adapted == "CD8 TEM 2"] <- "CD8 TEM_2"
clusters$vignette[clusters$vignette == "CD8 TEM 1"] <- "CD8 TEM_1"
clusters$adapted[clusters$adapted == "CD8 TEM 1"] <- "CD8 TEM_1"

set.seed(1)
n <- ifelse(clusters$cells >= 50, 60L, clusters$cells) # fewer cells, same big/small split
cell_cluster <- rep(clusters$cluster, n)
expr <- do.call(cbind, lapply(seq_len(nrow(clusters)), function(k) {
  mu <- setNames(rep(0.02, length(genes)), genes)
  p <- profiles[[clusters$profile[k]]]
  mu[names(p)] <- p
  matrix(pmax(0, rnorm(length(genes) * n[k], mean = mu, sd = 0.3 * mu + 0.05)), nrow = length(genes))
}))
rownames(expr) <- genes
expr["CD34", cell_cluster == "6_1"] <- expr["CD34", cell_cluster == "6_1"] + 0.05 # noise in an absent marker

lineages <- list(
  myeloid = list(labels = c("CD14 Mono", "CD16 Mono", "cDC"), genes = c("LYZ", "CD14")),
  B = list(labels = c("Naive B", "Intermediate B", "Memory B"), genes = c("MS4A1", "IGHD")),
  "T or NK" = list(labels = c("CD4 Naive", "CD4 TCM", "CD4 TEM", "Treg", "CD8 Naive", "CD8 TEM_1",
    "CD8 TEM_2", "MAIT", "gdT", "NK"), genes = c("CD3E", "IL7R", "NKG7", "GNLY")),
  pDC = list(labels = "pDC", genes = c("LILRA4", "CLEC4C")),
  plasma = list(labels = "Plasma", genes = c("JCHAIN", "MZB1")),
  HSPC = list(labels = "HSPC", genes = "CD34")
)
label_cells <- function(col) rep(clusters[[col]], n)

fit <- curelab_label_fit(expr, cell_cluster, label_cells("adapted"), lineages)
ok(nrow(fit) == 0, paste0("adapted labels all fit (misfits: ", paste(fit$cluster, collapse = ", "), ")"))
fit <- curelab_label_fit(expr, cell_cluster, label_cells("vignette"), lineages)
ok(setequal(fit$cluster, c("8", "9", "11")), paste0("the vignette's numbering misfits clusters 8, 9 and 11 (got ", paste(fit$cluster, collapse = ", "), ")"))
ok(identical(fit$looks_like[fit$cluster == "8"], "myeloid"), "cluster 8 is recognised as myeloid")
ok(!any(c("20", "21", "6_3", "6_4") %in% fit$cluster), "clusters under 50 cells are not judged")
lab <- label_cells("adapted"); lab[cell_cluster == "7"] <- "Macrophage"
fit <- curelab_label_fit(expr, cell_cluster, lab, lineages)
ok(identical(fit$cluster, "7") && is.na(fit$label) == FALSE, "an unknown label is reported")
ok(identical(getOption("future.globals.maxSize"), 8 * 1024^3), "raises the future globals limit for SCTransform")
cat(results, sep = "\n")
