import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_launcher_loads_only_local_env_and_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / "run.sh", root / "run.sh")
            (root / ".venv/bin").mkdir(parents=True)
            python = root / ".venv/bin/python"
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$OPENAI_MODEL" "$OPENAI_API_KEY" "$OPENAI_BASE_URL" "$PWD" "$@"\n')
            python.chmod(0o700)
            (root / ".env").write_text("OPENAI_MODEL=gpt-5.4-mini\nOPENAI_API_KEY='local test value'\nOPENAI_BASE_URL=https://example.openai.azure.com/openai/v1/\n")
            result = subprocess.run(["/bin/sh", str(root / "run.sh"), "--port", "8765"],
                                    cwd="/", env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ["gpt-5.4-mini", "local test value",
                "https://example.openai.azure.com/openai/v1/", str(root), "-m", "misofish.server", "--port", "8765"])

    def test_launcher_preserves_environment_without_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / "run.sh", root / "run.sh")
            (root / ".venv/bin").mkdir(parents=True)
            python = root / ".venv/bin/python"
            python.write_text('#!/bin/sh\nprintf "%s" "$OPENAI_MODEL"\n')
            python.chmod(0o700)
            result = subprocess.run(["/bin/sh", str(root / "run.sh")],
                                    env={"PATH": os.environ["PATH"], "OPENAI_MODEL": "custom-model"},
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "custom-model")
