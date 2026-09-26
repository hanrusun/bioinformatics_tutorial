# Readiness for the NBL TRN pipeline

Target:
[`wbaopaul/NBL_scMultiomics_Paper/TRN-analysis`](https://github.com/wbaopaul/NBL_scMultiomics_Paper/tree/main/TRN-analysis),
the transcriptional regulatory network (TRN) analysis from *Longitudinal
single-cell multiomic atlas of high-risk neuroblastoma reveals
chemotherapy-induced tumor microenvironment rewiring* (Nature Genetics,
2025).

The TRN scripts start from objects built by the paper's upstream scripts
(`snRNA-seq-analysis/Integration/02_rna_integration_malignant_harmony.R`,
`DEGandSurvival/01_deg_analysis.R`,
`snATAC-seq-analysis/CellAnnotation/*.R`). The table maps every Seurat call
in those scripts to where Cure Lab teaches it. C1 is Campaign 1 (Seurat
Basics) and C2 is Campaign 2 (Seurat for the Multiome Lab); "nb" is a lab
notebook page.

## Seurat calls

| Call in the NBL scripts | Where it appears | Taught in |
|---|---|---|
| `CreateSeuratObject()` | co-embedding (per-sample ATAC and RNA objects) | C1 mission 1 |
| `subset(obj, biospecimen_id == …)`, `subset(obj, prediction.score.max > 0.6)` | nearly every script | C1 mission 3, C2 mission 2 |
| `AddMetaData()` | co-embedding, TRN, label transfer, DEG | C2 missions 1 and 10 |
| `obj[['RNA']]$counts`, `$data`; `@assays$ATAC@counts` (v3 style) | co-embedding, gene–peak regression, TRN | C2 mission 1, C2 nb "Inside a Seurat v5 object", quiz "GetAssayData / layer" |
| `options(Seurat.object.assay.version = "v3")` | co-embedding | C2 nb "Inside a Seurat v5 object" |
| `NormalizeData(normalization.method = 'LogNormalize', scale.factor = …)` | co-embedding, label transfer | C1 mission 4, C1 nb "Normalization" |
| `FindVariableFeatures(nfeatures = …)`, `VariableFeatures<-` | co-embedding, integration | C1 mission 5 |
| `ScaleData(features = …, vars.to.regress = …, do.scale = FALSE)` | co-embedding, integration | C1 mission 6, C2 mission 4, C2 nb "Merging, and RNA + ATAC co-embedding" |
| `RunPCA(npcs = …)` | co-embedding, integration | C1 mission 7 |
| `RunUMAP(reduction = 'pca', dims = …)` | co-embedding, integration | C1 mission 10, C2 mission 7 |
| `FindNeighbors(reduction = …, dims = …)`, `FindClusters(resolution = …)` | co-embedding, integration, cell states | C1 mission 9, C2 mission 7 |
| `CellCycleScoring()` | malignant integration | C2 mission 3 |
| `AddModuleScore()` | malignant integration | C2 nb "Cell-cycle scoring and regression" |
| `RunHarmony()` | malignant integration | C2 mission 6 (`IntegrateLayers(method = HarmonyIntegration)`, which calls `harmony::RunHarmony`), C2 nb "Splitting layers and integrating" |
| `FindMarkers()`, `FindAllMarkers()`, `Idents<-`, `DoHeatmap()` | DEG, cell states | C1 missions 11–12, C2 missions 8–9 |
| `DefaultAssay<-`, `CreateAssayObject()` | co-embedding, label transfer | C2 nb "Mapping a query onto a reference" (gene-activity assay) |
| `FindTransferAnchors(reduction = 'cca', query.assay = "ACTIVITY")`, `TransferData(weight.reduction = …)` | co-embedding, label transfer | C2 mission 10, C2 nb "Mapping a query onto a reference", quizzes on `cca` and LSI weighting |
| `merge(x = rna, y = atac)` | co-embedding | C2 mission 11, C2 nb "Merging, and RNA + ATAC co-embedding" |
| `DimPlot()`, `FeaturePlot()`, `VlnPlot()` | everywhere | throughout C1 |
| `RenameCells()` | co-embedding | not covered (one-line rename of cell barcodes) |

## Not Seurat: candidates for future packs

| Tool | Used for | Script |
|---|---|---|
| **Signac** (`RunTFIDF`, `RunSVD`, `GeneActivity`, `CollapseToLongestTranscript`) | scATAC processing, gene activity, TSS annotation | `snATAC-seq-analysis/*`, `regr_gene_peak_links_metacell_malignant.R` |
| **hdWGCNA** (`SetupForWGCNA`, `MetacellsByGroups`, `NormalizeMetacells`) | RNA+ATAC metacells on the co-embedding | `coembedding_perSample_metacell_malignant.R` |
| **motifmatchr / chromVARmotifs / BSgenome** (`matchMotifs`) | TF motif scan of peaks | `motif_scan.R` |
| **chromVAR** (deviation scores, consumed by the TRN script) | TF activity per cell state | upstream of `predict_tf_regulons_cellstate.R` |
| **data.table / GenomicRanges / base R regression** | enhancer–gene links, TRN assembly | `regr_gene_peak_links_metacell_malignant.R`, `predict_tf_regulons_cellstate.R` |
| **DoubletFinder, decontX (celda)** | doublets and ambient RNA | `snRNA-seq-analysis/PreProcess/*` |
| **enrichR, fgsea, edgeR/limma** | pathway enrichment, pseudobulk DAP/DEG | TRN, DEG, DAP scripts |

A **Signac pack** would be the natural next step: the NBL snATAC processing
and the gene-activity/co-embedding steps are its core vignettes. Following
the one-illness-per-campaign rule, it could reuse neuroblastoma, or bring a
new disease.
