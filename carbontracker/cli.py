import argparse
import subprocess
from carbontracker.tracker import CarbonTracker
from carbontracker import parser
import ast
import carbontracker.loggerutil as loggerutil
from carbontracker.emissions.conversion import co2eq


def parse_logs(log_dir):
    parser.print_aggregate(log_dir=log_dir)


def main():
    """
    The **carbontracker** CLI allows the user to track the energy consumption and carbon intensity of any program.
    [Make sure that you have relevant permissions before running this.](/#permissions)

    Args:
        --log_dir (path, optional): Log directory. Defaults to `./logs`.
        --api_keys (str, optional): API keys in a dictionary-like format, e.g. `\'{"electricitymaps": "YOUR_KEY"}\'`
        --parse (path, optional): Directory containing the log files to parse.

    Example:
        Tracking the carbon intensity of `script.py`.

            $ carbontracker python script.py

        With example options

            $ carbontracker --log_dir='./logs' --api_keys='{"electricitymaps": "API_KEY_EXAMPLE"}' python script.py

        Parsing logs:

            $ carbontracker --parse ./internal_logs
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
    cli_parser.add_argument("--simpipe", type=str, help="Path to simpipe JSON file to parse and simulate log.")

    # Parse known arguments only
    known_args, remaining_args = cli_parser.parse_known_args()

    # Check if the --parse argument is provided
    if known_args.parse:
        parse_logs(known_args.parse)
        return

    # Check if the --simpipe argument is provided
    if hasattr(known_args, 'simpipe') and known_args.simpipe:
        import json
        from carbontracker.components.cpu.generic import GenericCPU
        from carbontracker.loggerutil import Logger
        from carbontracker.emissions.intensity import intensity
        import time

        # Load simpipe file
        with open(known_args.simpipe, 'r') as f:
            sim_data = json.load(f)

        # Extract CPU usage seconds and timestamps
        cpu_usage = sim_data['data']['dryRun']['node']['metrics']['cpuUsageSecondsTotal']
        if not cpu_usage:
            print("No CPU usage data found in simpipe file.")
            return

        # For a single data point, assume 1 second duration
        if len(cpu_usage) == 1:
            duration = 1.0
            cpu_seconds = float(cpu_usage[0]['value'])
        else:
            timestamps = [entry['timestamp'] for entry in cpu_usage]
            values = [float(entry['value']) for entry in cpu_usage]
            duration = timestamps[-1] - timestamps[0]  # seconds
            cpu_seconds = values[-1] - values[0]

        # Get CPU info and TDP
        cpu = GenericCPU(pids=[], devices_by_pid=False)
        cpu.init()
        cpu_name = cpu.cpu_brand
        avg_tdp = cpu.tdp  # Already adjusted for 50% utilization
        matched = cpu.tdp != cpu.average_tdp  # If TDP is not the average, we found a match

        # Estimate energy (Joules): Power (W) * time (s)
        energy_joules = avg_tdp * cpu_seconds
        energy_kwh = energy_joules / 3600 / 1000

        # Fetch location and carbon intensity
        logger = Logger(log_dir=known_args.log_dir)
        ci = intensity.carbon_intensity(logger)
        carbon_intensity = ci.carbon_intensity if hasattr(ci, 'carbon_intensity') else None
        location = getattr(ci, 'address', 'Unknown')

        # Calculate CO2eq (g)
        co2eq_val = energy_kwh * carbon_intensity if carbon_intensity is not None else None
        equivalents = co2eq.convert(co2eq_val) if co2eq_val is not None else None

        # Print header
        print("\n=== CarbonTracker Simulation Results ===")
        print(f"Source: {known_args.simpipe}")
        print("=" * 40)

        # Print simulation details
        print("\nSimulation Details:")
        print(f"+ Duration: {loggerutil.convert_to_timestring(duration, True)}")
        print(f"+ CPU Model: {cpu_name}")
        print(f"+ CPU Power Data: {'Available' if matched else 'Not available (using average TDP)'}")
        print(f"+ Average Power Usage: {avg_tdp:.2f} W")
        print(f"+ Energy Usage: {energy_joules:.2f} J")
        print(f"+ Location: {location}")
        print(f"+ Carbon Intensity: {carbon_intensity:.2f} gCO2/kWh" if carbon_intensity is not None else "+ Carbon Intensity: N/A")

        # Print consumption summary
        print("\nConsumption Summary:")
        print(f"+ Energy: {energy_kwh:.6f} kWh")
        if co2eq_val is not None:
            print(f"+ CO2eq: {co2eq_val:.3f} g")
            if equivalents:
                print("\nEnvironmental Impact Equivalents:")
                for units, unit in equivalents:
                    print(f"+ {units:.6f} {unit}")
        else:
            print("+ CO2eq: N/A")

        # Log all output
        logger.info("=== CarbonTracker Simulation Results ===")
        logger.info(f"Source: {known_args.simpipe}")
        logger.info("=" * 40)
        logger.info("\nSimulation Details:")
        logger.info(f"Duration: {loggerutil.convert_to_timestring(duration, True)}")
        logger.info(f"CPU Model: {cpu_name}")
        logger.info(f"CPU Power Data: {'Available' if matched else 'Not available (using average TDP)'}")
        logger.info(f"Average Power Usage: {avg_tdp:.2f} W")
        logger.info(f"Energy Usage: {energy_joules:.2f} J")
        logger.info(f"Location: {location}")
        logger.info(f"Carbon Intensity: {carbon_intensity:.2f} gCO2/kWh" if carbon_intensity is not None else "• Carbon Intensity: N/A")
        logger.info("\nConsumption Summary:")
        logger.info(f"Energy: {energy_kwh:.6f} kWh")
        if co2eq_val is not None:
            logger.info(f"CO2eq: {co2eq_val:.3f} g")
            if equivalents:
                logger.info("\nEnvironmental Impact Equivalents:")
                for units, unit in equivalents:
                    logger.info(f"{units:.6f} {unit}")
        else:
            logger.info("CO2eq: N/A")

        print(f"\nSimulation log written to {known_args.log_dir}")
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