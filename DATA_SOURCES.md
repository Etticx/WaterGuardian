# Dataset provenance

Source: [Moazeni's CONCISE Lab — WDSEventDB](https://github.com/Moazeni-s-Concise-Lab/WDSEventDB).
The source repository describes measurements from a sensor-instrumented water
distribution testbed at the CONCISE Research Lab, Lehigh University, covering
normal operation, leaks, sensor failures and cyberattack scenarios.

Repository licence: [CC0 1.0](https://github.com/Moazeni-s-Concise-Lab/WDSEventDB/blob/main/LICENSE).
The source requests acknowledgement of its WDSEventDB conference article; use
the current citation on the repository's README when preparing the submission.

The local dataset contains nine usable Excel recordings. macOS resource-fork
files are ignored. Spreadsheet ground-truth columns remain in the original files
for separate training and evaluation but never enter telemetry or agent prompts.
Operational recording IDs are anonymous (`run-01`, etc.) so an agent cannot infer
the event type from the file name.

Township zone assignments, crew names and manual task statuses are demonstration
context. The measured values are retained from the recordings. This is laboratory
benchmark replay, not a field validation in an SDP township.
