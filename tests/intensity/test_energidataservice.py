import unittest
from unittest import mock
import datetime
from carbontracker.emissions.intensity.fetchers import energidataservice
from carbontracker import exceptions


class TestEnergiDataService(unittest.TestCase):
    def setUp(self):
        self.fetcher = energidataservice.EnergiDataService()
        self.geocoder = mock.MagicMock()
        self.geocoder.country = "DK"

    def test_suitable(self):
        self.assertTrue(self.fetcher.suitable(self.geocoder))
        self.geocoder.country = "US"
        self.assertFalse(self.fetcher.suitable(self.geocoder))

    @mock.patch("requests.get")
    def test_carbon_intensity_no_time_dur(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "records": [{"CO2Emission": 1.0}, {"CO2Emission": 2.0}]
        }
        mock_get.return_value = mock_response
        result = self.fetcher.carbon_intensity(self.geocoder)

        self.assertEqual(result.carbon_intensity, 1.0)
        self.assertFalse(result.is_prediction)

    @mock.patch("requests.get")
    def test_carbon_intensity_with_time_dur(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "records": [
                {"CO2Emission": 1.0},
                {"CO2Emission": 2.0},
                {"CO2Emission": 3.0},
                {"CO2Emission": 4.0},
            ]
        }
        mock_get.return_value = mock_response

        result = self.fetcher.carbon_intensity(self.geocoder, time_dur=1800)

        self.assertEqual(result.carbon_intensity, 2.5)
        self.assertTrue(result.is_prediction)

    @mock.patch("requests.get")
    def test_nearest_5_min(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "records": [
                {"CO2Emission": 1.0},
                {"CO2Emission": 2.0},
                {"CO2Emission": 3.0},
                {"CO2Emission": 4.0},
            ]
        }
        mock_get.return_value = mock_response

        _result = self.fetcher.carbon_intensity(self.geocoder, time_dur=1800)

        now = datetime.datetime.now(datetime.timezone.utc)

        from_time = now - datetime.timedelta(
            minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond
        )
        to_time = from_time + datetime.timedelta(seconds=1800)

        # Format the from_time and to_time to strings
        date_format = "%Y-%m-%dT%H:%M"
        expected_from_time = from_time.strftime(date_format)
        expected_to_time = to_time.strftime(date_format)

        # Check that the mocked requests.get was called with the expected URL
        expected_url = f"https://api.energidataservice.dk/dataset/CO2Emis?start={expected_from_time}&end={expected_to_time}&limit=4"
        mock_get.assert_called_once_with(expected_url)

    @mock.patch("requests.get")
    def test_emission_current_response_not_ok(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.ok = False
        mock_response.json.return_value = {"error": "some error"}
        mock_get.return_value = mock_response

        with self.assertRaises(exceptions.CarbonIntensityFetcherError):
            self.fetcher._emission_current()

    @mock.patch("requests.get")
    def test_emission_prognosis_response_not_ok(self, mock_get):
        mock_response = mock.MagicMock()
        mock_response.ok = False
        mock_response.json.return_value = {"error": "some error"}
        mock_get.return_value = mock_response

        with self.assertRaises(exceptions.CarbonIntensityFetcherError):
            self.fetcher._emission_prognosis(time_dur=1800)
