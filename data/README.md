# Dataset

`online_retail_II.zip` contains `online_retail_II.csv` from the *Online Retail II* data set
(about 1.07 million transactions of a UK online retailer, 2009-12-01 to 2011-12-09, with an
`InvoiceDate` timestamp per row).

* Source: UCI Machine Learning Repository, *Online Retail II*; mirrored on Kaggle
  (<https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci>)
* Citation: Chen, D. (2012). Online Retail II. UCI Machine Learning Repository.
* License: CC BY 4.0 (attribution required, as given above)

The archive is committed unchanged so the project runs without a manual download.
The `seed` service reads it directly and writes the monthly slices to `data/slices/`
(git-ignored).
