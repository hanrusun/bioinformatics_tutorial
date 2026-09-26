# DE vignette set-up (de_vignette.Rmd, "Load in the data" and "Add sample
# information to the dataset"). The donor assignment files are downloaded at
# image build time (data/fetch_data.R) instead of from GitHub at run time.
# Loaded by mission c2-m09-pseudobulk via load_prep("ifnb_donors").
curelab_libraries("SeuratData")
ifnb <- LoadData("ifnb")
ifnb <- NormalizeData(ifnb)

# load the inferred sample IDs of each cell
ctrl <- read.table(file.path(CURELAB_DATASETS, "demuxlet", "ye1.ctrl.8.10.sm.best"), head = T, stringsAsFactors = F)
stim <- read.table(file.path(CURELAB_DATASETS, "demuxlet", "ye2.stim.8.10.sm.best"), head = T, stringsAsFactors = F)
info <- rbind(ctrl, stim)

# rename the cell IDs by substituting the '-' into '.'
info$BARCODE <- gsub(pattern = "\\-", replacement = "\\.", info$BARCODE)

# only keep the cells with high-confidence sample ID
info <- info[grep(pattern = "SNG", x = info$BEST), ]

# remove cells with duplicated IDs in both ctrl and stim groups
info <- info[!duplicated(info$BARCODE) & !duplicated(info$BARCODE, fromLast = T), ]

# now add the sample IDs to ifnb
rownames(info) <- info$BARCODE
info <- info[, c("BEST"), drop = F]
names(info) <- c("donor_id")
ifnb <- AddMetaData(ifnb, metadata = info)

# remove cells without donor IDs
ifnb$donor_id[is.na(ifnb$donor_id)] <- "unknown"
ifnb <- subset(ifnb, subset = donor_id != "unknown")

save_checkpoint("prep-ifnb_donors", "ifnb")
