"""Script to create a short csv file with carbon intensity data.

Uses csv from https://ourworldindata.org/grapher/carbon-intensity-electricity.
"""
import argparse

import pycountry
import pandas as pd


def country_to_alpha2(name):
    try:
        return pycountry.countries.get(name=name).alpha_2
    except Exception as err:
        return None


def main(args):
    intensity_df = pd.read_csv(args.input_csv)
    intensity_df.sort_values(by="Year", inplace=True, ascending=False)

    # Add ISO 3166-1 alpha-2 country codes.
    intensity_df["alpha-2"] = intensity_df["Entity"].apply(country_to_alpha2)

    # Drop rows with None or NaN.
    intensity_df.dropna(subset=["alpha-2"], inplace=True)

    # Only keep most recent year from every country.
    # Note that no country shares alpha-2 code, so should not lose any info.
    intensity_df = intensity_df.groupby("alpha-2").first()

    # Save to csv.
    intensity_df.to_csv(args.output_csv)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", help="Path to input csv.", required=True)
    parser.add_argument("--output_csv", help="Path to output csv.", required=True)
    args = parser.parse_args()
    main(args)
