from carbontracker.emissions.intensity.fetchers.energidataservice import EnergiDataService
import geocoder

test = EnergiDataService()
ci = test.carbon_intensity(g_location=geocoder.ip("me"), time_dur=3600)
print(ci.carbon_intensity)
print(ci.message)