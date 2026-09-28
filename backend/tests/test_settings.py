import os
from pathlib import Path
import subprocess
import sys
import unittest


class SettingsTests(unittest.TestCase):
    def test_process_environment_overrides_loaded_dotenv_values(self) -> None:
        backend_dir = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PURPOS_ASSESSMENT_REPOSITORY"] = "memory"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.config.settings import settings; "
                "print(settings.assessment_repository)",
            ],
            cwd=backend_dir,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "memory")


if __name__ == "__main__":
    unittest.main()
