# Reference-mapping vignette set-up (integration_mapping.Rmd, chunks
# "preprocessing1" and "preprocessing3"): build the integrated pancreas
# reference. Loaded by mission c2-m10-mapping via load_prep("panc8_ref").
curelab_libraries("SeuratData")
panc8 <- LoadData('panc8')

# we will use data from 2 technologies for the reference
pancreas.ref <- subset(panc8, tech %in% c("celseq2", "smartseq2"))
pancreas.ref[["RNA"]] <- split(pancreas.ref[["RNA"]], f = pancreas.ref$tech)

# pre-process dataset (without integration)
pancreas.ref <- NormalizeData(pancreas.ref)
pancreas.ref <- FindVariableFeatures(pancreas.ref)
pancreas.ref <- ScaleData(pancreas.ref)
pancreas.ref <- RunPCA(pancreas.ref)
pancreas.ref <- FindNeighbors(pancreas.ref, dims=1:30)
pancreas.ref <- FindClusters(pancreas.ref)
pancreas.ref <- RunUMAP(pancreas.ref, dims = 1:30)

pancreas.ref <- IntegrateLayers(
  object = pancreas.ref, method = CCAIntegration,
  orig.reduction = "pca", new.reduction = 'integrated.cca',
  verbose = FALSE)
pancreas.ref <- FindNeighbors(pancreas.ref,reduction='integrated.cca',dims=1:30)
pancreas.ref <- FindClusters(pancreas.ref)
pancreas.ref <- RunUMAP(pancreas.ref,reduction='integrated.cca',dims=1:30)

save_checkpoint("prep-panc8_ref", c("panc8", "pancreas.ref"))
