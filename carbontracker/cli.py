import argparse
import subprocess
from carbontracker.tracker import CarbonTracker
from carbontracker import parser
from carbontracker.report import generate_report_from_log
import ast
import os


def parse_logs(log_dir):
    parser.print_aggregate(log_dir=log_dir)


def generate_report(log_file, output_pdf):
    """Generate a PDF report from a log file"""
    if not os.path.exists(log_file):
        print(f"Error: Log file {log_file} does not exist")
        return
    generate_report_from_log(log_file, output_pdf)
    print(f"Report generated: {output_pdf}")


def main():
    """
    The **carbontracker** CLI allows the user to track the energy consumption and carbon intensity of any program.
    [Make sure that you have relevant permissions before running this.](/#permissions)

    Args:
        --log_dir (path, optional): Log directory. Defaults to `./logs`.
        --api_keys (str, optional): API keys in a dictionary-like format, e.g. `\'{"electricitymaps": "YOUR_KEY"}\'`
        --parse (path, optional): Directory containing the log files to parse.
        --report (path, optional): Generate a PDF report from a log file.
        --output (path, optional): Output path for the generated report. Defaults to 'carbon_report.pdf'

    Example:
        Tracking the carbon intensity of `script.py`.

            $ carbontracker python script.py

        With example options

            $ carbontracker --log_dir='./logs' --api_keys='{"electricitymaps": "API_KEY_EXAMPLE"}' python script.py

        Parsing logs:

            $ carbontracker --parse ./internal_logs

        Generating a report:

            $ carbontracker --report ./logs/carbontracker.log --output report.pdf
    """

    # Create a parser for the known arguments
    cli_parser = argparse.ArgumentParser(description="CarbonTracker CLI", add_help=True)
    cli_parser.add_argument("--log_dir", type=str, default="./logs", help="Log directory")
    cli_parser.add_argument(
        "--api_keys",
        type=str,
        help="API keys in a dictionary-like format, e.g., "
             '\'{"electricitymaps": "YOUR_KEY"}\'',
        default=None,
    )
    cli_parser.add_argument("--parse", type=str, help="Directory containing the log files to parse.")
    cli_parser.add_argument("--report", type=str, help="Generate a PDF report from a log file.")
    cli_parser.add_argument("--output", type=str, default="carbon_report.pdf", 
                          help="Output path for the generated report.")

    # Parse known arguments only
    known_args, remaining_args = cli_parser.parse_known_args()

    # Check if the --parse argument is provided
    if known_args.parse:
        parse_logs(known_args.parse)
        return

    # Check if the --report argument is provided
    if known_args.report:
        generate_report(known_args.report, known_args.output)
        return

    # Parse the API keys string into a dictionary
    api_keys = ast.literal_eval(known_args.api_keys) if known_args.api_keys else None

    tracker = CarbonTracker(
        epochs=1, log_dir=known_args.log_dir, epochs_before_pred=0, api_keys=api_keys
    )
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