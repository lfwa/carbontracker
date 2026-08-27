import geocoder
import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pandas as pd
import sys

from carbontracker import constants
from carbontracker.emissions.intensity import intensity

from carbontracker.emissions.intensity.intensity import IntensityFetch, IntensityService 

class TestIntensity(unittest.TestCase):
    @patch("geocoder.ip")
    def test_get_default_intensity_success(self, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location
        logger = Mock()
        service = IntensityService(logger=logger)
        default_intensity_fetch = service.default_carbon_intensity

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
        expected_intensity = intensity_row["Carbon intensity of electricity (gCO2eq/kWh)"]

        self.assertEqual(default_intensity_fetch.carbon_intensity, expected_intensity)
        self.assertIsInstance(default_intensity_fetch.carbon_intensity, float)


        msg =     (f"No carbon intensity provider specified. "
                    f"Using average carbon intensity for {mock_location.country}: "
                    f"{expected_intensity:.2f} gCO2eq/kWh.")
        logger.err_warn.assert_called_with(msg)

        
    
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.fetch_carbon_intensity")
    @patch("geocoder.ip")
    def test_get_default_intensity_success_with_fetcher(self, mock_geocoder_ip, mock_fetcher):
        mock_location = MagicMock()
        mock_location.ok = True 
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location
        logger = Mock()
        service = IntensityService(logger=logger, intensity_fetcher=mock_fetcher)
        default_intensity_fetch = service.default_carbon_intensity

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
        expected_intensity = intensity_row["Carbon intensity of electricity (gCO2eq/kWh)"]

        self.assertEqual(default_intensity_fetch.carbon_intensity, expected_intensity)
        logger.err_warn.assert_not_called()
        logger.err_info.assert_called_with(
            "Using realtime localized carbon intensity based on location: Sample Address."
        )



    @patch("geocoder.ip")
    def test_get_default_intensity_location_failure_without_fetcher(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False
        logger = Mock()
        service = IntensityService(logger=logger, intensity_fetcher=None)
        default_intensity_fetch = service.default_carbon_intensity

        self.assertEqual(default_intensity_fetch.carbon_intensity, constants.WORLD_AVG_CARBON_INTENSITY)

        msg = (
                    f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
                )
        self.assertIsInstance(default_intensity_fetch.carbon_intensity, float)

        logger.err_warn.assert_called_with(msg)

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
        
        logger = MagicMock()
        intensity_service = IntensityService(logger) 
        default_intensity = intensity_service.default_carbon_intensity  
        msg =   (
                    f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
                )

        logger.err_warn.assert_called_with(msg)

        self.assertEqual(default_intensity.carbon_intensity,constants.WORLD_AVG_CARBON_INTENSITY)
        self.assertIsInstance(default_intensity.carbon_intensity, float)


    @patch("geocoder.ip")
    @patch("pandas.read_csv")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.fetch_carbon_intensity")
    def test_get_default_intensity_data_file_failure_with_fetcher(
            self, mock_electricity_map,mock_read_csv, mock_geocoder_ip
    ):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Sample Address"
        mock_location.country = "US"
        mock_geocoder_ip.return_value = mock_location

        mock_read_csv.side_effect = FileNotFoundError
        logger = MagicMock()
        intensity_service = IntensityService(logger,mock_electricity_map) 
        default_intensity = intensity_service.default_carbon_intensity  
        logger.err_warn.assert_not_called()
        self.assertEqual(default_intensity.carbon_intensity,constants.WORLD_AVG_CARBON_INTENSITY)
        self.assertIsInstance(default_intensity.carbon_intensity, float)


    @patch("geocoder.ip")
    def test_get_default_intensity_ip_location_failure(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False
        
        
        logger = MagicMock()
        intensity_service = IntensityService(logger) 
        default_intensity = intensity_service.default_carbon_intensity  

        self.assertEqual(default_intensity.carbon_intensity, constants.WORLD_AVG_CARBON_INTENSITY)
        self.assertIsInstance(default_intensity.carbon_intensity, float)
        msg =   (
                    f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
                )

        logger.err_warn.assert_called_with(msg)


    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_generate_logging_message_on_local_fallback(self, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = "Aarhus, Capital Region, DK"
        mock_location.country = "DK"
        mock_geocoder_ip.return_value = mock_location

        logger = Mock()
        service = IntensityService(logger=logger)
        default_fetch = service.default_carbon_intensity

        expected_message = (
                    f"No carbon intensity provider specified. "
                    f"Using average carbon intensity for {default_fetch.country}: "
                    f"{default_fetch.carbon_intensity:.2f} gCO2eq/kWh.")

        logger.err_warn.assert_called_once_with(expected_message)
 

    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_generate_logging_message_global_fallback(self, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = False
        mock_geocoder_ip.return_value = mock_location
        logger = Mock()
        service = IntensityService(logger=logger)

        expected_message = (f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{service.default_carbon_intensity.carbon_intensity:.2f} gCO2eq/kWh.")

        logger.err_warn.assert_called_once_with(expected_message)
        
        


    @patch("geocoder.ip")
    def test_default_ci_on_location_failure_without_fetcher(self, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False

        logger = Mock()

        intensity_service = IntensityService(logger) 
        default_intensity = intensity_service.default_carbon_intensity  
        self.assertEqual(default_intensity.carbon_intensity, constants.WORLD_AVG_CARBON_INTENSITY)
        self.assertEqual(default_intensity.address, "Unknown")
        self.assertEqual(default_intensity.is_fetched, False)
        self.assertEqual(default_intensity.is_localized, False)
        self.assertEqual(default_intensity.is_prediction, False)
        self.assertIsInstance(default_intensity.carbon_intensity, float)


        msg_err = (f"No carbon intensity provider specified and no location detected. "
                    f"Defaulting to global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                    f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh.")

        logger.err_warn.assert_called_with(msg_err)

    @patch("geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap.fetch_carbon_intensity")
    def test_default_ci_on_location_failure_with_fetcher(self, mock_electricity_map, mock_geocoder_ip):
        mock_geocoder_ip.return_value.ok = False
        logger = Mock()
        mock_electricity_map.return_value.carbon_intensity.return_value = 10

        intensity_service = IntensityService(logger, mock_electricity_map) 
        default_intensity = intensity_service.default_carbon_intensity  

        self.assertEqual(default_intensity.carbon_intensity, constants.WORLD_AVG_CARBON_INTENSITY)
        self.assertEqual(default_intensity.address, "Unknown")
        self.assertEqual(default_intensity.is_fetched, False)
        self.assertEqual(default_intensity.is_localized, False)
        self.assertEqual(default_intensity.is_prediction, False)
        self.assertIsInstance(default_intensity.carbon_intensity, float)

        msg = (
                f"Location could not be determined. "
                f"Using global average carbon intensity for {constants.WORLD_AVG_CARBON_INTENSITY_YEAR}: "
                f"{constants.WORLD_AVG_CARBON_INTENSITY:.2f} gCO2eq/kWh."
            )
        logger.err_warn.assert_called_with(msg)


    @patch("geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap")
    def test_carbon_intensity_address_assignment(self, mock_electricity_map, mock_geocoder_ip):
        mock_location = MagicMock()
        mock_location.ok = True
        mock_location.address = None
        mock_geocoder_ip.return_value = mock_location

        fetcher = mock_electricity_map.return_value
        fetcher.suitable.return_value = False

        
        logger = MagicMock()
        intensity_service = IntensityService(logger, intensity_fetcher=fetcher) 
        default_intensity = intensity_service.fetch_carbon_intensity("100")
 
        self.assertIsNone(default_intensity.address)
        fetcher.suitable.assert_called_once_with(mock_location)

    @patch("geocoder.ip")
    @patch("carbontracker.emissions.intensity.fetchers.electricitymaps.ElectricityMap")
    def test_carbon_intensity_failure_on_carbon_intensity_fetch(self, mock_electricity_map_carbon_intensity, mock_geocoder_ip):
        mock_location = Mock()
        mock_location.ok = True
        mock_geocoder_ip.return_value = mock_location

        fetcher = mock_electricity_map_carbon_intensity.return_value
        fetcher.suitable.return_value = True
        fetcher.fetch_carbon_intensity.side_effect = Exception("Test Exception")

        logger = Mock()
        intensity_service = IntensityService(logger,
                                             intensity_fetcher=fetcher)
        
        intensity_fetch = intensity_service.fetch_carbon_intensity() 


        self.assertIsInstance(intensity_fetch.carbon_intensity, float)
        self.assertFalse(intensity_fetch.is_fetched)
        self.assertTrue(intensity_fetch == intensity_service.default_carbon_intensity)

        msg = (
                f"Fetcher is unable to retrieve carbon intensity data for your detected location {intensity_service.address}. "
                f"Carbon emissions calculations will fall back to the average carbon intensity for {intensity_service.default_carbon_intensity.country}: {intensity_service.default_carbon_intensity.carbon_intensity:.2f} gCO2eq/kWh.")

        logger.err_warn.assert_called_with(msg)
        

    @patch("carbontracker.emissions.intensity.fetchers.carbonintensitygb.CarbonIntensityGB")
    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_carbon_intensity_exception_carbonintensitygb(self, mock_geocoder, mock_carbonintensitygb):
        mock_geocoder.return_value.address = "Sample Address"
        mock_geocoder.return_value.ok = True
        mock_carbonintensitygb.return_value.suitable.return_value = True
        fetcher = mock_carbonintensitygb.return_value
        fetcher.fetch_carbon_intensity.return_value = IntensityFetch(
            carbon_intensity=23.0,
            address=mock_geocoder.return_value.address,
            country=mock_geocoder.return_value.country,
            is_fetched=True,
            is_localized=True,
        )

        logger = MagicMock()

        intensity_service = IntensityService(logger, fetcher)

        intensity_fetch = intensity_service.fetch_carbon_intensity() 
        self.assertEqual(intensity_fetch.carbon_intensity, 23.0)
        self.assertIsInstance(intensity_fetch.carbon_intensity, float)
        self.assertTrue(intensity_fetch.is_fetched)

    @patch("carbontracker.emissions.intensity.fetchers.energidataservice.EnergiDataService")
    @patch("carbontracker.emissions.intensity.intensity.geocoder.ip")
    def test_carbon_intensity_energidataservice(self,mock_geocoder, mock_energidataservice):
        mock_geocoder.return_value.address = "Sample Address"
        mock_geocoder.return_value.country = "DK"
        mock_geocoder.return_value.ok = True
        mock_energidataservice.return_value.suitable.return_value = True
        mock_energidataservice.return_value.fetch_carbon_intensity.return_value = IntensityFetch(
            carbon_intensity=23.0,
            address=mock_geocoder.return_value.address,
            country=mock_geocoder.return_value.country,
            is_fetched=True,
            is_localized=True,
        )

        logger = MagicMock()
        intensity_service = IntensityService(logger, mock_energidataservice.return_value)
        intensity_fetch = intensity_service.fetch_carbon_intensity()
        self.assertIsInstance(intensity_fetch.carbon_intensity, float)
        self.assertEqual(intensity_fetch.carbon_intensity, 23.0)
        self.assertTrue(intensity_fetch.is_fetched)
