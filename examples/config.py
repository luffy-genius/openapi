import os
import yaml
from pathlib import Path

config_name = os.getenv('OPENAPI_CONFIG', 'config.dev.yaml')
with open(Path(f'../{config_name}')) as fd:
    config = yaml.safe_load(fd.read())
