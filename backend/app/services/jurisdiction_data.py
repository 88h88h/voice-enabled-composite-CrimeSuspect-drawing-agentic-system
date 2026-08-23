"""
Static stand-in for a real government-data lookup (police jurisdiction by
location). Satisfies "retrieval of relevant service information" for the
demo without the scope cost of a real integration -- documented in the
README as exactly that: a stand-in, not a claim of real government-data
access.
"""

_JURISDICTIONS: dict[str, tuple[str, str]] = {
    "sector 62 noida": ("Sector 58 Police Station, Noida", "+91-120-2400100"),
    "sector 18 noida": ("Sector 20 Police Station, Noida", "+91-120-2510100"),
    "connaught place": ("Connaught Place Police Station, Delhi", "+91-11-23361234"),
    "paytm office noida": ("Sector 58 Police Station, Noida", "+91-120-2400100"),
}

_DEFAULT = ("Local Police Station (jurisdiction lookup unavailable for this location)", "112")


def lookup_jurisdiction(incident_location: str) -> tuple[str, str]:
    key = incident_location.strip().lower()
    return _JURISDICTIONS.get(key, _DEFAULT)
