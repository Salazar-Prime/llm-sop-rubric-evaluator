import json
import os

_config = None


def load_config(path="config.json"):
    global _config
    if _config is not None:
        return _config
    if os.path.exists(path):
        with open(path, "r") as f:
            _config = json.load(f)
    else:
        _config = {}
    return _config


def get(key, default=None):
    return load_config().get(key, default)
