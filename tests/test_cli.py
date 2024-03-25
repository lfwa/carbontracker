import subprocess
import unittest
from unittest import skipIf
from time import sleep
from unittest.mock import patch
from io import StringIO
import sys
from carbontracker import cli
import os

def mock_password_input(prompt):
    # Simulate password entry based on the prompt
    if "Password:" in prompt:
        return "your_password"
    else:
        # Handle other prompts or return None for unexpected prompts
        return None

@skipIf(os.environ.get('CI') == 'true', 'Skipped due to CI')
class TestCLI(unittest.TestCase):

    @patch("builtins.input", side_effect=mock_password_input)
    @patch("sys.argv", ["python -c 'print('Test')'", "--log_dir", "./test_logs"])
    def test_main_with_args(self, mock_input):
        sleep(2)
        captured_output = StringIO()
        sys.stdout = captured_output

        cli.main()
        self.assertIn("CarbonTracker: The following components", captured_output.getvalue())


    @patch("builtins.input", side_effect=mock_password_input)
    @patch("sys.argv", ["python -c 'print('Test')'"])
    def test_main_without_args(self, mock_input):
        sleep(2)
        captured_output = StringIO()
        sys.stdout = captured_output

        cli.main()
        self.assertIn("CarbonTracker: The following components", captured_output.getvalue())

    @patch("builtins.input", side_effect=mock_password_input)
    @patch("subprocess.run", autospec=True)
    @patch.object(sys, "argv", ["cli.py", "--log_dir", "./logs", "echo 'test'"])
    def test_main_with_remaining_args(self, mock_subprocess, mock_input):
        sleep(2)
        mock_subprocess.return_value.returncode = 0  # Simulate a successful command execution

        cli.main()
        mock_subprocess.assert_called_once_with(["echo 'test'"], check=True)

    @patch("builtins.input", side_effect=mock_password_input)
    @patch("subprocess.run", autospec=True)
    @patch.object(sys, "argv", ["cli.py", "--log_dir", "./logs", "echo 'test'"])
    def test_main_with_remaining_args_failure(self, mock_subprocess, mock_input):
        sleep(2)
        mock_subprocess.side_effect = subprocess.CalledProcessError(0, ["echo 'test'"])

        cli.main()
        mock_subprocess.assert_called_once_with(["echo 'test'"], check=True)

if __name__ == "__main__":
    unittest.main()
