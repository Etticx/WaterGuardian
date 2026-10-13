from functools import lru_cache
from math import isfinite
from openpyxl import load_workbook
from .config import settings


class Dataset:
    def __init__(self):
        root = settings.path(settings.dataset_dir)
        files = [p for p in root.rglob('*.xlsx') if '__MACOSX' not in p.parts and not p.name.startswith('._')]
        self.paths = {f'run-{i+1:02d}': p for i, p in enumerate(sorted(files))}
        if not self.paths:
            raise RuntimeError(f'No benchmark recordings found under {root}')

    @lru_cache(maxsize=12)
    def read(self, recording_id: str):
        if recording_id not in self.paths:
            raise KeyError('Unknown recording')
        w = load_workbook(self.paths[recording_id], read_only=True, data_only=True)
        try:
            rows = iter(w.active.values)
            headers = [str(v).strip() for v in next(rows)]
            # The target and event filenames never enter the operational telemetry.
            keep = [(i, h) for i, h in enumerate(headers) if h.lower() not in {'labels', 'label', 'target', 'class'}]
            out = []
            for row in rows:
                values = {}
                for i, h in keep:
                    v = row[i] if i < len(row) else None
                    if isinstance(v, (int, float)) and isfinite(float(v)):
                        values[h] = float(v)
                if values:
                    out.append(values)
            return out
        finally:
            w.close()

    def catalog(self):
        return [{'id': rid, 'name': f'Recording {rid[-2:]}', 'samples': len(self.read(rid)), 'channels': list(self.read(rid)[0])} for rid in self.paths]

    def default_runs(self):
        def find(stem):
            return next((k for k, p in self.paths.items() if p.stem == stem), next(iter(self.paths)))
        return [find('LeakEvent1'), find('CleanData'), find('SensorEvent1')]

