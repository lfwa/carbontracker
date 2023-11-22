import argparse
import subprocess
import ast
from carbontracker.tracker import CarbonTracker
import shlex

def main():
    # Create the parser for the script's own arguments
    parser = argparse.ArgumentParser(description="CarbonTracker CLI")
    parser.add_argument("--log_dir", type=str, help="Log directory", default="./logs")
    parser.add_argument("--api_keys", type=str, help="API keys in a dictionary-like format, e.g., "
                                                     "'{\"electricitymaps\": \"YOUR_KEY\"}'", default=None)

    # Parse known arguments and remaining arguments
    args, remaining_args = parser.parse_known_args()

    # Parse the API keys string into a dictionary
    api_keys = ast.literal_eval(args.api_keys) if args.api_keys else None

    tracker = CarbonTracker(epochs=1, log_dir=args.log_dir, epochs_before_pred=0, api_keys=api_keys)
    tracker.epoch_start()

    # Handle the command
    if remaining_args:
        if '--cmd' in remaining_args:
            cmd_index = remaining_args.index('--cmd')
            command_args = remaining_args[cmd_index + 1:]
        else:
            command_args = remaining_args

        # Execute the command
        try:
            subprocess.run(command_args, check=True)
        except subprocess.CalledProcessError:
            print(f"Error executing command: {' '.join(map(shlex.quote, command_args))}")

    tracker.epoch_end()
    tracker.stop()

if __name__ == "__main__":
    main()
