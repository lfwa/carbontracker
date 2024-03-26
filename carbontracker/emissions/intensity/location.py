class Location:
    # geocoder has no type hints, so this class represents the "location" object
    def __init__(self, ok: bool, address: str, country: str):
        self.ok = ok
        self.address = address
        self.country = country
