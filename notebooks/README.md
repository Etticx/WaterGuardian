# Colab ML training

Open `Water_Guardian_ML_Colab.ipynb` in Google Colab through **File → Upload
notebook**, choose a CPU runtime, and run all cells. When setup installs packages,
it stops and asks you to choose **Runtime → Restart session**. Restart, then run
all cells again; setup skips reinstalling when the pinned versions and imports
are healthy. This prevents old NumPy components in memory from mixing with newly
installed files. If an older notebook already failed with a NumPy `_slice` import
error, upload this updated notebook and run its setup cell first.
In Colab the notebook
downloads the authors' public WDSEventDB ZIP automatically. API keys are not
required. Local execution can use the existing project dataset.

## Combining the files

There are three selected **folders**, containing eight Excel files:

- Clean: one workbook.
- Leakage: three workbooks.
- Sensor Failure: four workbooks.

The notebook stacks rows from those files into one pandas DataFrame, preserving
the recording ID and original sample index. It exports `combined_cleaned.csv`
for inspection; a merged Excel workbook is unnecessary. Original files stay
unchanged. The eight pressure/flow columns are features. Original labels and
event-folder information create the target, but never become features.

Original label 0 maps to normal in every selected folder. Original label 1 maps
to leak in Leakage and sensor_fault in Sensor Failure. Cyberattack is excluded.

## The requested experiments

Logistic Regression and Random Forest each run 70/30, 80/20, CV 5, CV 10,
70/30 + CV 5, 70/30 + CV 10, 80/20 + CV 5, and 80/20 + CV 10.

These are explicitly labelled stratified **sample-level development** experiments.
For split + CV, hyperparameters are tuned only within the training portion;
the development test portion is not used by CV. CV-only rows report out-of-fold
performance. Different score bases remain separate in the output table.

Before those experiments, LeakEvent3.xlsx and SensorEvent67.xlsx are reserved as
an untouched final recording test. All requested comparisons therefore use the
other six files. The chosen model is selected by a shared development-CV search
before opening final-test predictions. Final recording scores are reported
separately from the exploratory sample-level scores.

## Cleaning and exports

The notebook audits every workbook and reports its actual cleaning actions.
Negative pressure/fault signatures, real zeros and repeated measurements are
preserved. Missing/malformed sensor values are imputed inside training pipelines.

The last cells produce a ZIP containing both model bundles, the selected
`models/monitor.joblib`, `models/evaluation.json`, package versions, a source
manifest, and measured comparison/test reports. Evaluation describes the selected
model's final recording test. The exported model remains fitted only on the six
development recordings. Copy the selected bundle and evaluation JSON to the
project's `models` folder and use **Settings → Reload model** after reviewing
the results. Exporting from the notebook does not automatically change the app.

The verified baseline run found a substantial gap between sample CV and unseen
recordings. Random Forest scored approximately 0.981 macro F1 in development
selection CV, but 0.272 on the final recording test, with zero leak recall.
Logistic Regression detected the held-out leak but recognised only seven of 122
sensor-fault samples and generated many false sensor-fault classifications.
These are baseline findings to improve on before enabling automatic detection.
Both exports are explicitly marked experimental, and the ZIP includes a
`READ_ME_FIRST.txt` with the selected model's final-test recall values.
