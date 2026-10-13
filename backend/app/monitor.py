import joblib
import math
import pandas as pd
from .config import settings


class Monitor:
    def __init__(self):
        self.bundle = None
        self.error = None
        self.reload()

    def reload(self):
        self.bundle = None
        self.error = None
        p = settings.path(settings.ml_model_path)
        if p.exists():
            try:
                b = joblib.load(p)
                if not isinstance(b, dict) or not all(k in b for k in ('model', 'features', 'class_map')):
                    raise ValueError('Export a bundle containing model, features, and class_map.')
                if not hasattr(b['model'], 'predict') or not b['features']:
                    raise ValueError('The model must implement predict and declare ordered input features.')
                if not isinstance(b['features'], list) or any(not isinstance(f, str) for f in b['features']) or len(set(b['features'])) != len(b['features']):
                    raise ValueError('Features must be a list of unique sensor channel names.')
                if any(f.lower() in {'labels', 'label', 'target', 'class', 'filename', 'recording_id', 'zone'} for f in b['features']):
                    raise ValueError('Ground truth and recording metadata are prohibited as model features.')
                if not isinstance(b['class_map'], dict) or not b['class_map'] or any(not isinstance(k, str) for k in b['class_map']):
                    raise ValueError('class_map must map string prediction labels to operational classes.')
                allowed = {'normal', 'leak', 'sensor_fault', 'review'}
                if any(v not in allowed for v in b['class_map'].values()):
                    raise ValueError('class_map must use normal, leak, sensor_fault, or review.')
                self.bundle = b
            except Exception as e:
                self.error = str(e)
        return self.status()

    def status(self):
        return {'connected': self.bundle is not None, 'version': self.bundle.get('version', 'unversioned') if self.bundle else None,
                'features': self.bundle['features'] if self.bundle else [], 'error': self.error,
                'path': settings.ml_model_path}

    def predict(self, values):
        if not self.bundle:
            return None
        b = self.bundle
        missing = [f for f in b['features'] if f not in values]
        if missing:
            return {'classification': 'review', 'score': None, 'error': f'Missing features: {", ".join(missing)}'}
        try:
            x = pd.DataFrame([[values[f] for f in b['features']]], columns=b['features'])
            raw = b['model'].predict(x)[0]
            label = b['class_map'].get(str(raw))
            if label is None:
                raise ValueError(f'No class_map entry for prediction {raw}')
            score = None
            if hasattr(b['model'], 'predict_proba'):
                probabilities = b['model'].predict_proba(x)[0]
                classes = list(b['model'].classes_)
                score = float(probabilities[classes.index(raw)])
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError('The model returned an invalid score.')
            return {'classification': label, 'score': score, 'model_version': b.get('version', 'unversioned')}
        except Exception as e:
            return {'classification': 'review', 'score': None, 'error': str(e)}


monitor = Monitor()

