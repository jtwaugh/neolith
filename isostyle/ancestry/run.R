# qpAdm per individual with ADMIXTOOLS 2. Called by isostyle/ancestry.py:
#   Rscript run.R <model.json>
# model.json: prefix (PACKEDANCESTRYMAP subset whose .ind labels reference
# individuals by population and each target by its own genetic id), left
# (source populations, in order), right (outgroups, base first), targets,
# p_min, z_bound, max_sources, rotate, cache (directory), out (csv).
#
# Per target: f2 blocks over the SNPs covered in the target and every
# reference population (maxmiss = 0), then models of 1..max_sources sources,
# smallest first. A model is accepted when p >= p_min and every weight lies in
# [0, 1] within z_bound standard errors; among accepted models of the smallest
# size the highest p wins. With rotate, sources outside the model join the
# outgroups. Results are cached per target, so a rerun resumes.
suppressPackageStartupMessages({
  library(admixtools)
  library(jsonlite)
  library(parallel)
})

args <- commandArgs(trailingOnly = TRUE)
m <- fromJSON(args[1])
dir.create(m$cache, showWarnings = FALSE, recursive = TRUE)
ind <- read.table(paste0(m$prefix, ".ind"), col.names = c("id", "sex", "pop"), stringsAsFactors = FALSE)
refpops <- c(m$left, m$right)
ref <- ind[ind$pop %in% refpops, ]
cols <- c("gid", "status", "model", "p", "snps_used", paste0("w_", m$left), paste0("se_", m$left))

blank <- function(gid, status) {
  r <- as.list(setNames(rep(NA, length(cols)), cols))
  r$gid <- gid
  r$status <- status
  r$model <- ""
  as.data.frame(r, stringsAsFactors = FALSE)
}

one <- function(gid) {
  f <- file.path(m$cache, paste0(gsub("[^A-Za-z0-9_.-]", "_", gid), ".csv"))
  if (file.exists(f)) return(read.csv(f, stringsAsFactors = FALSE, na.strings = "NA"))
  res <- tryCatch({
    f2 <- suppressWarnings(suppressMessages(f2_from_geno(
      m$prefix, inds = c(ref$id, gid), pops = c(ref$pop, gid),
      maxmiss = 0, adjust_pseudohaploid = TRUE, auto_only = TRUE, verbose = FALSE)))
    out <- blank(gid, "no_fit")
    out$snps_used <- sum(attr(f2, "block_lengths") %||% NA)
    done <- FALSE
    for (k in seq_len(m$max_sources)) {
      best <- NULL
      for (left in combn(m$left, k, simplify = FALSE)) {
        right <- if (m$rotate) c(m$right, setdiff(m$left, left)) else m$right
        q <- tryCatch(suppressWarnings(suppressMessages(
          qpadm(f2, left, right, gid, verbose = FALSE))), error = function(e) NULL)
        if (is.null(q)) next
        w <- q$weights
        p <- q$rankdrop$p[1]
        if (is.na(p) || p < m$p_min) next
        if (k > 1 && any(is.na(w$se))) next
        se <- ifelse(is.na(w$se), 0, w$se)
        if (any(w$weight < -m$z_bound * se) || any(w$weight > 1 + m$z_bound * se)) next
        if (is.null(best) || p > best$p) best <- list(p = p, w = w, left = left)
      }
      if (!is.null(best)) {
        out$status <- "fit"
        out$model <- paste(best$left, collapse = "+")
        out$p <- best$p
        # Weights inside the bounds within error are clipped to [0, 1] and renormalised.
        wt <- pmin(pmax(best$w$weight, 0), 1)
        wt <- wt / sum(wt)
        for (i in seq_along(best$left)) {
          out[[paste0("w_", best$left[i])]] <- wt[i]
          out[[paste0("se_", best$left[i])]] <- if (k == 1) 0 else best$w$se[i]
        }
        done <- TRUE
      }
      if (done) break
    }
    out
  }, error = function(e) {
    r <- blank(gid, "no_fit")
    r$model <- paste("error:", substr(conditionMessage(e), 1, 120))
    r
  })
  write.csv(res[, cols], f, row.names = FALSE)
  res[, cols]
}

`%||%` <- function(a, b) if (is.null(a)) b else a
cores <- max(1, min(detectCores() - 1, as.integer(Sys.getenv("ANCESTRY_CORES", "6"))))
t0 <- Sys.time()
res <- mclapply(m$targets, one, mc.cores = cores, mc.preschedule = FALSE)
bad <- vapply(res, function(r) !is.data.frame(r), TRUE)
if (any(bad)) stop("qpAdm workers failed for: ", paste(m$targets[bad][1:min(5, sum(bad))], collapse = ", "))
res <- do.call(rbind, res)
write.csv(res, m$out, row.names = FALSE)
cat(sprintf("qpadm: %d targets, %d fit, %.1f min on %d cores\n", nrow(res), sum(res$status == "fit"),
            as.numeric(difftime(Sys.time(), t0, units = "mins")), cores))
