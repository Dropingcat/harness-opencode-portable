"""Keep all writable runtime locations inside the pilot, including child processes."""
from pathlib import Path
import json
import os
import sys
import tempfile


HOME = Path(__file__).resolve().parents[1]


def configure():
    from .paths import output_dir
    locations = {"TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp",
                 "PIP_CACHE_DIR": "cache/pip", "UV_CACHE_DIR": "cache/uv",
                 "XDG_CACHE_HOME": "cache", "XDG_DATA_HOME": "state/xdg-data",
                 "XDG_STATE_HOME": "state/xdg-state", "XDG_CONFIG_HOME": "state/xdg-config",
                 "MPLCONFIGDIR": "cache/matplotlib", "HF_HOME": "cache/huggingface",
                 "TORCH_HOME": "cache/torch", "PYTHONUSERBASE": "state/python-user"}
    for key, relative in locations.items():
        path = output_dir(HOME / relative, HOME)
        os.environ[key] = str(path)
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                      PIP_DISABLE_PIP_VERSION_CHECK="1", GRAPHIFY_NO_AUTO_REFRESH="1",
                      GIT_OPTIONAL_LOCKS="0")
    tempfile.tempdir = str(HOME / "tmp")
    vendor = str(HOME / "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    os.environ["GRAPHIFY_OUT"] = str(HOME / "graphify-out")


def config():
    return json.loads((HOME / "pilot_config.json").read_text(encoding="utf-8"))


def catalog():
    from .catalog import Catalog
    data = config()
    return Catalog(HOME, data["roots"], exclude_dirs=data["exclude_dirs"],
                   max_file_bytes=data["max_file_bytes"], max_text_chars=data["max_text_chars"],
                   max_pdf_pages=data["max_pdf_pages"])
