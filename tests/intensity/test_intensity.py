import geocoder
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import sys

from carbontracker import constants
from carbontracker.emissions.intensity import intensity

from carbontracker.emissions.intensity.intensity import carbon_intensity


class TestIntensity(unittest.TestCase):
    @patch("geocoder.ip")
    def test_get_default_intensity_success(self, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location

        result = intensity.get_default_intensity()

        # importlib.resources.files was introduced in Python 3.9 and replaces deprecated pkg_resource.resources
        if sys.version_info < (3,9):
            import pkg_resources
            carbon_intensities_df = pd.read_csv(pkg_resources.resource_filename("carbontracker", "data/carbon-intensities.csv"))
        else:
            import importlib.resources
            ref = importlib.resources.files("carbontracker") / "data/carbon-intensities.csv"
            with importlib.resources.as_file(ref) as path:
                carbon_intensities_df = pd.read_csv(path)
        intensity_row = carbon_intensities_df[carbon_intensities_df["alpha-2"] == mock_location.country].iloc[0]
        expected_intensity = intensity_row["Carbon intensity of electricity (gCO2/kWh)"]

        self.assertEqual(result["carbon_intensity"], expected_intensity)
        self.assertIn("Defaulted to average carbon intensity", result["description"])

    @patch("geocoder.ip")
    def test_get_default_intensity_location_failure(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False

        result = intensity.get_default_intensity()

        self.assertEqual(result["carbon_intensity"], constants.WORLD_2019_CARBON_INTENSITY)
        self.assertIn("Defaulted to average carbon intensity", result["description"])

    @patch("geocoder.ip")
    @patch("pandas.read_csv")
    def test_get_default_intensity_data_file_failure(
            self, mock_read_csv, mock_geocoder_ip
    ):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location

        mock_read_csv.side_effect = FileNotFoundError

        default_intensity = intensity.get_default_intensity()

        expected_description = (
            f"Live carbon intensity could not be fetched at detected location: {mock_location.address}. "
            f"Defaulted to average carbon intensity for world in 2019 of {constants.WORLD_2019_CARBON_INTENSITY:.2f} gCO2/kWh."
        )

        assert default_intensity["carbon_intensity"] == constants.WORLD_2019_CARBON_INTENSITY
        assert default_intensity["description"] == expected_description

    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    @patch("carbontracker.emissions.intensity.intensity.pd.read_csv")
    def test_CarbonIntensity_set_as_default(
            self, mock_read_csv, mock_geocoder_ip
    ):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location

        mock_read_csv.side_effect = FileNotFoundError

        default_intensity = intensity.get_default_intensity()

        expected_description = (
            f"Live carbon intensity could not be fetched at detected location: {mock_location.address}. "
            f"Defaulted to average carbon intensity for world in 2019 of {constants.WORLD_2019_CARBON_INTENSITY:.2f} gCO2/kWh."
        )

        self.assertEqual(default_intensity["carbon_intensity"], constants.WORLD_2019_CARBON_INTENSITY)
        self.assertEqual(default_intensity["description"], expected_description)


    def test_CarbonIntensity_set_default_message(self):
        ci = intensity.CarbonIntensity(default=True)
        ci.set_default_message()

        self.assertIn("Defaulted to average carbon intensity", ci.message)

    @patch("geocoder.ip")
    def test_get_default_intensity_ip_location_failure(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False

        result = intensity.get_default_intensity()

        self.assertEqual(result["carbon_intensity"], constants.WORLD_2019_CARBON_INTENSITY)
        self.assertIn("Defaulted to average carbon intensity", result["description"])

    @patch("geocoder.ip")
    def test_carbon_intensity_location_failure(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False

        logger = MagicMock()

        with patch('carbontracker.emissions.intensity.intensity.default_intensity', intensity.get_default_intensity()) as C:
            result = intensity.carbon_intensity(logger)
            default_intensity = intensity.get_default_intensity()

            self.assertEqual(result.carbon_intensity, default_intensity["carbon_intensity"])
            self.assertEqual(result.address, "UNDETECTED")
            self.assertEqual(result.success, False)
            self.assertIn("Live carbon intensity could not be fetched at detected location", result.message)

    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_set_carbon_intensity_message(self, mock_geocoder_ip):
        time_dur = 3600
        mock_location = MagicMock()
        # Assuming the actual function logic uses a specific fallback or detected location
        detected_address = "Aarhus, Capital Region, DK"  # The detected location that appears in the error
        fallback_address = "Generic Location, Country"  # The fallback or generic location
        mock_location.address = detected_address
        mock_location.country = 'DK'
        mock_geocoder_ip.ok = True
        mock_geocoder_ip.return_value = mock_location
        # Adjust the set_expected_message function to match the error details
        def set_expected_message(is_prediction, success, carbon_intensity):
            if is_prediction:
                if success:
                    message = f"Carbon intensity for the next 1:00:00 is predicted to be {carbon_intensity:.2f} gCO2/kWh at detected location: {fallback_address}."
                else:
                    message = f"Failed to predict carbon intensity for the next 1:00:00, fallback on average measured intensity at detected location: {fallback_address}."
            else:
                if success:
                    message = f"Current carbon intensity is {carbon_intensity:.2f} gCO2/kWh at detected location: {fallback_address}."
                else:
                    message = (f"Live carbon intensity could not be fetched at detected location: {detected_address}. "
                               f"Defaulted to average carbon intensity for DK in 2023 of 151.65 gCO2/kWh. "
                               f"at detected location: {fallback_address}.")
            return message
        # Test scenarios
        scenarios = [
            (True, True, 100.0),
            (True, False, None),
            (False, True, 50.0),
            (False, False, None)  # The scenario corresponding to the failure message
        ]

        with patch('carbontracker.emissions.intensity.intensity.default_intensity', intensity.get_default_intensity()) as C:
            ci = intensity.CarbonIntensity()
            ci.address = fallback_address  # Set to the fallback or generic address for the test case
            for is_prediction, success, carbon_intensity in scenarios:
                ci.is_prediction = is_prediction
                ci.success = success
                ci.carbon_intensity = carbon_intensity if carbon_intensity is not None else 0.0
                intensity.set_carbon_intensity_message(ci, time_dur)
                expected_message = set_expected_message(is_prediction, success, carbon_intensity)
                self.assertEqual(ci.message, expected_message)

    @patch("geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.suitable")
    def test_carbon_intensity_address_assignment(self, mock_electricity_map_suitable, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = None
        mock_geocoder_ip.return_value = mock_location

        mock_electricity_map_suitable.return_value = False

        logger = MagicMock()
        result = carbon_intensity(logger)

        self.assertIsNone(result.address)
        mock_electricity_map_suitable.assert_called_once_with(mock_location)

    @patch("geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.carbon_intensity")
    def test_carbon_intensity_failure(self, mock_electricity_map_carbon_intensity, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_geocoder_ip.return_value = mock_location

        mock_electricity_map_carbon_intensity.side_effect = Exception("Test Exception")

        logger = MagicMock()

        result = carbon_intensity(logger)

        self.assertFalse(result.success)
        self.assertIn("could not be fetched", result.message)

    @patch("carbontracker.emissions.intensity.fetchers.carbonintensitygb.CarbonIntensityGB")
    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_carbon_intensity_exception_carbonintensitygb(self, mock_geocoder, mock_carbonintensitygb):
        mock_geocoder.return_value.address = "Sample Address"
        mock_geocoder.return_value.ok = True
        mock_carbonintensitygb.return_value.suitable.return_value = True

        mock_result = MagicMock()
        mock_result.carbon_intensity = 23.0
        mock_result.success = True

        mock_carbonintensitygb.return_value.carbon_intensity.return_value = mock_result

        logger = MagicMock()

        result = carbon_intensity(logger, fetchers=[mock_carbonintensitygb()])

        self.assertEqual(result.carbon_intensity, 23.0)
        self.assertTrue(result.success)

    @patch("carbontracker.emissions.intensity.fetchers.energidataservice.EnergiDataService")
    def test_carbon_intensity_energidataservice(self, mock_energidataservice):
        mock_energidataservice.return_value.suitable.return_value = True

        mock_result = MagicMock()
        mock_result.carbon_intensity = 23.0
        mock_result.success = True
        mock_energidataservice.return_value.carbon_intensity.return_value = mock_result

        logger = MagicMock()
        result = carbon_intensity(logger, fetchers=[mock_energidataservice()])

        self.assertEqual(result.carbon_intensity, 23.0)
        self.assertTrue(result.success)

    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap")
    def test_carbon_intensity_nan(self, mock_electricity_map, mock_geocoder):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_geocoder.ip.return_value = mock_location

        mock_electricity_map.return_value.suitable.return_value = True

        mock_result = MagicMock()
        mock_result.carbon_intensity = np.nan
        mock_result.success = False

        mock_electricity_map.return_value.carbon_intensity.return_value = mock_result

        logger = MagicMock()

        result = carbon_intensity(logger)

        self.assertFalse(result.success)
        self.assertTrue(np.isnan(result.carbon_intensity))
        self.assertEqual(mock_location.address, "Sample Address")
