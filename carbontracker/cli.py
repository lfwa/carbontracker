import argparse
import subprocess
from carbontracker.tracker import CarbonTracker


def main():
    parser = argparse.ArgumentParser(description="CarbonTracker CLI")
    parser.add_argument("--script", type=str, required=True, help="Python file to execute")
    parser.add_argument("--log_dir", type=str, help="Log directory", default="./logs")
    # Add more arguments as needed

    args = parser.parse_args()

    tracker = CarbonTracker(epochs=1, log_dir=args.log_dir, epochs_before_pred=0)
    tracker.epoch_start()

    # Execute script with python
    try:
        subprocess.run(["python", args.script], check=True)
    except subprocess.CalledProcessError:
        print(f"Error executing script: {args.script}")
        # Handle errors or exceptions if needed

    tracker.epoch_end()
    tracker.stop()


if __name__ == "__main__":
    main()
