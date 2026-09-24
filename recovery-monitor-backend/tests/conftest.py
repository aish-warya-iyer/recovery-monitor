import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated app data for tests; must be set before the app is imported.
_TMP = tempfile.mkdtemp(prefix="rm-test-")
os.environ["RM_APP_DATA"] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend (app)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root (model)


@pytest.fixture(scope="session")
def tiny_video(tmp_path_factory) -> Path:
    """A 3-second synthetic MP4 made with the bundled ffmpeg (no dataset needed)."""
    import imageio_ffmpeg

    out = tmp_path_factory.mktemp("vid") / "tiny.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=duration=3:size=320x240:rate=30", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out
