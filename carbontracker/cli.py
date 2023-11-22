import argparse
import subprocess
from carbontracker.tracker import CarbonTracker
import ast
import sys


def main():
    # Create a parser for the known arguments
    parser = argparse.ArgumentParser(description="CarbonTracker CLI", add_help=True)
    parser.add_argument("--log_dir", type=str, default="./logs", help="Log directory")
    parser.add_argument("--api_keys", type=str, help="API keys in a dictionary-like format, e.g., "
                                                 "'{\"electricitymaps\": \"YOUR_KEY\"}'", default=None)

    # Parse known arguments only
    known_args, remaining_args = parser.parse_known_args()

    # Parse the API keys string into a dictionary
    api_keys = ast.literal_eval(known_args.api_keys) if known_args.api_keys else None

    tracker = CarbonTracker(epochs=1, log_dir=known_args.log_dir, epochs_before_pred=0, api_keys=api_keys)
    tracker.epoch_start()

    # The remaining_args are considered as the command to execute
    if remaining_args:
        try:
            # Execute the command
            subprocess.run(remaining_args, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {' '.join(remaining_args)}")
            print(f"Subprocess error: {e}")

    tracker.epoch_end()
    tracker.stop()


if __name__ == "__main__":
    main()

