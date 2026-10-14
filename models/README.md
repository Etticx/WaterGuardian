The Monitor model is trained separately from the application. Use
`notebooks/Water_Guardian_ML_Colab.ipynb` for the Logistic Regression and Random
Forest training workflow. Its downloaded package contains a compatible bundle
and an evaluation JSON measured on reserved recordings.

Export one joblib bundle to `models/monitor.joblib`:

```python
joblib.dump({
    "model": fitted_sklearn_pipeline,
    "features": ordered_feature_names,
    "class_map": {"0": "normal", "1": "leak", "2": "sensor_fault"},
    "version": "your-version"
}, "models/monitor.joblib")
```

The class map must describe YOUR trained labels. Do not assume the binary Labels
column in each WDSEventDB recording is a three-class target. Establish the target
from the event documentation before training. Labels, filenames and scenario
categories must not be input features. Split by recording, not adjacent rows.

The pipeline receives a pandas DataFrame with the named features in the saved
order. Supported outputs are `normal`, `leak`, `sensor_fault`, or `review`.
Restart the backend or use Reload model in Settings after exporting the file.
Until then the UI displays Model not connected and offers manual investigation.

Optional evaluation file: `models/evaluation.json`, with actual measured metrics:
`model_version`, `split_description`, `samples`, `accuracy`, `macro_f1`,
`class_names`, and `confusion_matrix`. Do not enter demonstration scores.

