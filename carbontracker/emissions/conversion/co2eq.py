import pandas as pd

CONVERSION_FILE = "./carbontracker/emissions/conversion/co2eq.csv"
CONVERSION_DF = pd.read_csv(CONVERSION_FILE)

def convert(g_co2eq):
    """Converts gCO2eq to all units in range specified by CONVERSION_FILE."""
    conversions = []
    df = CONVERSION_DF
    converters = df.loc[(df["lowerbound"] <= g_co2eq) 
                        & (df["upperbound"] >= g_co2eq)]
    for _, converter in converters.iterrows():
        units = g_co2eq / converter["gCO2eq_per_unit"]
        conversions.append((units, converter["unit"]))
    return conversions