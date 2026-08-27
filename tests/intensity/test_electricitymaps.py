
import os
import unittest
from unittest.mock import MagicMock, call, patch

from carbontracker import exceptions
from carbontracker.emissions.intensity.fetchers.electricitymaps import (
    API_URL,
    ElectricityMap,
)

"""
Test constants for doing the end 2 end test. Note, that if you have a free subscription on electricity maps, you must ensure that that the specific locations are supported by the settings on your account. 
"""
ZONE_NAME_FOR_END2END = "DK"
END2END_LON=12.5683,
END2END_LAT=55.6761,


class TestElectricityMap(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.electricity_map = ElectricityMap(logger=self.logger, api_key="test_key")
        self.g_location = MagicMock()
        self.g_location.lng = 0.0
        self.g_location.lat = 0.0
        self.g_location.country = "US"

    def test_set_api_key(self):
        self.assertEqual(self.electricity_map._api_key, "test_key")

    def test_suitable(self):
        self.assertTrue(self.electricity_map.suitable(self.g_location))

    @patch("requests.get")
    def test_carbon_intensity_by_location_with_lon_lat(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"carbonIntensity": 50.0}
        mock_get.return_value = mock_response

        result = self.electricity_map._carbon_intensity_by_location(
            lon=self.g_location.lng,
            lat=self.g_location.lat,
        )
        self.assertEqual(result, 50.0)
        mock_get.assert_called_once_with(
            API_URL,
            headers={"auth-token": "test_key"},
            params=(("lon", 0.0), ("lat", 0.0)),
        )

    @patch("requests.get")
    def test_carbon_intensity_by_location_with_zone(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"carbonIntensity": 75.0}
        mock_get.return_value = mock_response

        result = self.electricity_map._carbon_intensity_by_location(
            zone=self.g_location.country,
        )
        self.assertEqual(result, 75.0)
        mock_get.assert_called_once_with(
            API_URL,
            headers={"auth-token": "test_key"},
            params=(("zone", "US"),),
        )

    @patch("requests.get")
    def test_carbon_intensity_by_location_bad_json_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.json.return_value = ""
        mock_get.return_value = mock_response

        with self.assertRaises(exceptions.CarbonIntensityFetcherError):
            self.electricity_map._carbon_intensity_by_location(
                lon=self.g_location.lng,
                lat=self.g_location.lat,
            )

    @patch("requests.get")
    def test_carbon_intensity_by_location_json_response_not_ok(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.json.return_value = {"error": "some error"}
        mock_get.return_value = mock_response

        with self.assertRaises(exceptions.CarbonIntensityFetcherError):
            self.electricity_map._carbon_intensity_by_location(
                lon=self.g_location.lng,
                lat=self.g_location.lat,
            )

    @patch.object(ElectricityMap, "_carbon_intensity_by_location")
    def test_carbon_intensity(self, mock_carbon_intensity_by_location):
        mock_carbon_intensity_by_location.return_value = 100.0

        intensity_fetch = self.electricity_map.fetch_carbon_intensity(self.g_location)

        self.assertEqual(intensity_fetch.carbon_intensity, 100.0)
        self.assertIsInstance(intensity_fetch.carbon_intensity, float)
        self.assertEqual(intensity_fetch.address, self.g_location.address)
        self.assertEqual(intensity_fetch.country, "US")
        self.assertTrue(intensity_fetch.is_fetched)
        self.assertTrue(intensity_fetch.is_localized)
        self.assertFalse(intensity_fetch.is_prediction)

    @patch.object(ElectricityMap, "_carbon_intensity_by_location")
    def test_carbon_intensity_with_exception(self, mock_carbon_intensity_by_location):
        mock_carbon_intensity_by_location.side_effect = [Exception(), 25.0]

        intensity_fetch = self.electricity_map.fetch_carbon_intensity(self.g_location)

        mock_carbon_intensity_by_location.assert_called_with(zone=self.g_location.country)
        self.assertEqual(
            mock_carbon_intensity_by_location.call_args_list,
            [
                call(lon=self.g_location.lng, lat=self.g_location.lat),
                call(zone=self.g_location.country),
            ],
        )
        self.assertEqual(intensity_fetch.carbon_intensity, 25.0)


@unittest.skipUnless(
    os.getenv("ELECTRICITYMAPS_API_KEY"),
    "Set ELECTRICITYMAPS_API_KEY to run Electricity Maps live contract tests",
)
class TestElectricityMapLiveContract(unittest.TestCase):
    """Opt-in checks for the external API contract used by CarbonTracker."""

    def setUp(self):
        api_url = os.getenv("ELECTRICITYMAPS_API_URL", API_URL)
        api_url_patcher = patch(
            "carbontracker.emissions.intensity.fetchers.electricitymaps.API_URL",
            api_url,
        )
        api_url_patcher.start()
        self.addCleanup(api_url_patcher.stop)
        self.electricity_map = ElectricityMap(
            logger=MagicMock(),
            api_key=os.environ["ELECTRICITYMAPS_API_KEY"],
        )
        
    def test_latest_carbon_intensity_by_coordinates(self):
        """This will likely fail unless you """
        intensity = self.electricity_map._carbon_intensity_by_location(
            lon=12.5683,
            lat=55.6761,
        )

        self.assertIsInstance(intensity, (int, float))
        self.assertGreaterEqual(intensity, 0)

    def test_latest_carbon_intensity_by_zone(self):
        intensity = self.electricity_map._carbon_intensity_by_location(
            zone=ZONE_NAME_FOR_END2END,
        )

        self.assertIsInstance(intensity, (int, float))
        self.assertGreaterEqual(intensity, 0)


if __name__ == "__main__":
    unittest.main()
