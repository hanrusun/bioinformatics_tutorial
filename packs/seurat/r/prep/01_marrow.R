# Cell-cycle vignette set-up (cell_cycle_vignette.Rmd, chunks
# "initialize_object" and "justification"). Run once at image build time; the
# result is loaded by mission c2-m03-cellcycle via load_prep("marrow").
curelab_libraries()

# Read in the expression matrix
# The first row is a header row, the first column is rownames
exp.mat <- read.table(file = file.path(CURELAB_DATASETS, "cell_cycle", "nestorawa_forcellcycle_expressionMatrix.txt"), header = TRUE, as.is = TRUE, row.names = 1)

# Create our Seurat object and complete the initalization steps
marrow <- CreateSeuratObject(counts = Matrix::Matrix(as.matrix(exp.mat),sparse = T))
marrow <- NormalizeData(marrow)
marrow <- FindVariableFeatures(marrow, selection.method = 'vst')
marrow <- ScaleData(marrow, features = rownames(marrow))
marrow <- RunPCA(marrow, features = VariableFeatures(marrow), ndims.print = 6:10, nfeatures.print = 10)

save_checkpoint("prep-marrow", "marrow")
