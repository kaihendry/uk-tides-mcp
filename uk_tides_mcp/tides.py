import logging
import os
import json
from typing import Any
from datetime import datetime
import httpx
from mcp.server.fastmcp import FastMCP
import zoneinfo
import math

logger = logging.getLogger(__name__)

mcp = FastMCP("UK tides")

# Constants
UKHO_API_BASE = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"
UKHO_API_KEY = os.getenv("UKHO_API_KEY")

if not UKHO_API_KEY:
    logger.error("UKHO_API_KEY environment variable not set")
    raise ValueError(
        "UKHO_API_KEY environment variable not set. Please subscribe to the UK Tidal API - Discovery from https://admiraltyapi.developer.azure-api.net/"
    )
else:
    logger.info("UKHO API key loaded successfully")


def lookup_station_id(query_name: str) -> str | None:
    """Lookup station ID by name from stations.json file.

    Args:
        query_name: The name of the location to search for

    Returns:
        The station ID if found, None otherwise
    """
    try:
        logger.debug(f"Looking up station ID for location: {query_name}")

        # Use importlib.resources to access the packaged stations.json file
        import importlib.resources as pkg_resources

        try:
            # Try to read from package resources first
            stations_data = (
                pkg_resources.files(__package__ or "uk_tides_mcp") / "stations.json"
            ).read_text()
        except (FileNotFoundError, TypeError):
            # Fallback to local file for development
            with open("stations.json", "r") as f:
                stations_data = f.read()

        data = json.loads(stations_data)

        # stations.json is an array of GeoJSON features
        if not isinstance(data, list):
            logger.error("stations.json should contain an array of features")
            return None

        # First try exact match (case insensitive)
        for feature in data:
            if feature.get("type") == "Feature" and "properties" in feature:
                properties = feature["properties"]
                name = properties.get("Name", "")
                if name.lower() == query_name.lower():
                    station_id = properties.get("Id")
                    logger.debug(f"Found exact match for {query_name}: {station_id}")
                    return station_id

        # Then try partial match (case insensitive)
        for feature in data:
            if feature.get("type") == "Feature" and "properties" in feature:
                properties = feature["properties"]
                name = properties.get("Name", "")
                if query_name.lower() in name.lower():
                    station_id = properties.get("Id")
                    logger.debug(
                        f"Found partial match for {query_name}: {station_id} ({name})"
                    )
                    return station_id

        logger.warning(f"No station found for location: {query_name}")
        return None

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error reading stations.json: {e}")
        return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth using Haversine formula.

    Args:
        lat1, lon1: Latitude and longitude of first point in decimal degrees
        lat2, lon2: Latitude and longitude of second point in decimal degrees

    Returns:
        Distance in kilometers
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Radius of Earth in kilometers
    r = 6371
    return c * r


def find_nearest_stations(
    lat: float, lon: float, limit: int = 5
) -> list[dict[str, Any]]:
    """Find the nearest tidal stations to given coordinates.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        limit: Maximum number of stations to return (default: 5)

    Returns:
        List of station dictionaries with distance information, sorted by distance
    """
    try:
        logger.debug(f"Finding nearest stations to coordinates: {lat}, {lon}")

        # Use importlib.resources to access the packaged stations.json file
        import importlib.resources as pkg_resources

        try:
            # Try to read from package resources first
            stations_data = (
                pkg_resources.files(__package__ or "uk_tides_mcp") / "stations.json"
            ).read_text()
        except (FileNotFoundError, TypeError):
            # Fallback to local file for development
            with open("stations.json", "r") as f:
                stations_data = f.read()

        data = json.loads(stations_data)

        # stations.json is an array of GeoJSON features
        if not isinstance(data, list):
            logger.error("stations.json should contain an array of features")
            return []

        stations_with_distance = []

        for feature in data:
            if (
                feature.get("type") == "Feature"
                and "geometry" in feature
                and "properties" in feature
            ):
                geometry = feature["geometry"]
                properties = feature["properties"]

                if geometry.get("type") == "Point" and "coordinates" in geometry:
                    coords = geometry["coordinates"]
                    if len(coords) >= 2:
                        station_lon, station_lat = (
                            coords[0],
                            coords[1],
                        )  # GeoJSON format: [lon, lat]

                        # Calculate distance
                        distance = haversine_distance(
                            lat, lon, station_lat, station_lon
                        )

                        station_info = {
                            "id": properties.get("Id"),
                            "name": properties.get("Name", "Unknown"),
                            "country": properties.get("Country", "Unknown"),
                            "latitude": station_lat,
                            "longitude": station_lon,
                            "distance_km": distance,
                        }
                        stations_with_distance.append(station_info)

        # Sort by distance and return top results
        stations_with_distance.sort(key=lambda x: x["distance_km"])
        result = stations_with_distance[:limit]

        logger.debug(f"Found {len(result)} nearest stations")
        return result

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error reading stations.json for nearest station search: {e}")
        return []


def get_location_suggestions(query_name: str, limit: int = 5) -> list[str]:
    """Get suggested location names based on partial matches.

    Args:
        query_name: The name to search for
        limit: Maximum number of suggestions to return

    Returns:
        List of suggested location names
    """
    try:
        logger.debug(f"Getting location suggestions for: {query_name}")

        # Use importlib.resources to access the packaged stations.json file
        import importlib.resources as pkg_resources

        try:
            # Try to read from package resources first
            stations_data = (
                pkg_resources.files(__package__ or "uk_tides_mcp") / "stations.json"
            ).read_text()
        except (FileNotFoundError, TypeError):
            # Fallback to local file for development
            with open("stations.json", "r") as f:
                stations_data = f.read()

        data = json.loads(stations_data)

        if not isinstance(data, list):
            logger.error("stations.json should contain an array of features")
            return []

        suggestions = []
        query_lower = query_name.lower()

        # Find all partial matches
        for feature in data:
            if feature.get("type") == "Feature" and "properties" in feature:
                properties = feature["properties"]
                name = properties.get("Name", "")

                # Check if any word in the query appears in the station name
                if any(
                    word in name.lower()
                    for word in query_lower.split()
                    if len(word) > 2
                ):
                    suggestions.append(name)
                elif query_lower in name.lower():
                    suggestions.append(name)

        # Remove duplicates and limit results
        unique_suggestions = list(
            dict.fromkeys(suggestions)
        )  # Preserves order while removing duplicates
        return unique_suggestions[:limit]

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error reading stations.json for suggestions: {e}")
        return []


# https://admiraltyapi.developer.azure-api.net/api-details#api=uk-tidal-api
async def make_UKHO_request(url: str) -> dict[str, Any] | None:
    """Make a request to the UKHO API with proper error handling."""

    headers = {
        "Ocp-Apim-Subscription-Key": UKHO_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Making request to UKHO API: {url}")
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            logger.debug("Successfully received response from UKHO API")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None


@mcp.tool()
async def get_tidal_times(name: str, suggest_alternatives: bool = True) -> str:
    """Returns tidal times for a specific location.

    Args:
        name: Name of the location (e.g., "FOWEY")
        suggest_alternatives: If True, suggest nearby stations when location not found (default: True)
    """
    # Lookup station ID from name
    stationId = lookup_station_id(name)
    if not stationId:
        if suggest_alternatives:
            # Try to suggest alternatives based on partial matches in the stations data
            suggestions = get_location_suggestions(name)
            if suggestions:
                suggestions_text = "\n".join(
                    [f"- {suggestion}" for suggestion in suggestions[:5]]
                )
                return f"Location '{name}' not found. Did you mean one of these?\n{suggestions_text}"
            else:
                return f"Location '{name}' not found. Please check the spelling or try a different location name."
        else:
            return f"Location '{name}' not found. Please check the spelling or try a different location name."

    # log the lookup
    logger.info(f"Looking up station ID for location: {name} -> {stationId}")

    url = f"{UKHO_API_BASE}/Stations/{stationId}/TidalEvents"
    data = await make_UKHO_request(url)

    if not data:
        logger.error(
            f"Failed to fetch tidal data for location: {name} (ID: {stationId})"
        )
        return "Unable to fetch tidal data for this location."

    try:
        # Parse the UKHO tidal response structure
        if not isinstance(data, list):
            logger.error("Expected tidal data to be a list of events")
            return "Invalid tidal data format received."

        tidal_events = [f"Tidal times for {name}:"]

        # Group events by UK local date
        events_by_date = {}
        for event in data:
            date_time = event.get("DateTime", "")
            if date_time:
                try:
                    # Parse the ISO datetime (assuming UTC) and convert to UK time
                    clean_datetime = (
                        date_time.split(".")[0] if "." in date_time else date_time
                    )
                    if clean_datetime.endswith("Z"):
                        clean_datetime = clean_datetime[:-1]

                    utc_dt = datetime.fromisoformat(clean_datetime)
                    utc_dt = utc_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                    uk_dt = utc_dt.astimezone(zoneinfo.ZoneInfo("Europe/London"))

                    # Group by UK local date
                    date_part = uk_dt.strftime("%Y-%m-%d")
                    if date_part not in events_by_date:
                        events_by_date[date_part] = []

                    # Store the event with converted datetime for sorting
                    event_with_uk_time = event.copy()
                    event_with_uk_time["UK_DateTime"] = uk_dt
                    events_by_date[date_part].append(event_with_uk_time)

                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse datetime {date_time}: {e}")
                    # Fallback to original date extraction
                    date_part = date_time.split("T")[0]
                    if date_part not in events_by_date:
                        events_by_date[date_part] = []
                    events_by_date[date_part].append(event)

        # Process each day's tidal events
        for date in sorted(events_by_date.keys()):
            tidal_events.append(f"\n=== {date} ===")

            day_events = events_by_date[date]
            # Sort events by UK time within the day
            day_events.sort(key=lambda x: x.get("UK_DateTime") or x.get("DateTime", ""))

            for event in day_events:
                event_type = event.get("EventType", "Unknown")
                height = event.get("Height", 0)

                # Use pre-calculated UK time if available, otherwise fallback to parsing
                if "UK_DateTime" in event:
                    uk_dt = event["UK_DateTime"]
                    time_str = uk_dt.strftime("%H:%M")
                else:
                    # Fallback parsing for events that couldn't be converted
                    date_time = event.get("DateTime", "")
                    if "T" in date_time:
                        time_part = date_time.split("T")[1]
                        if ":" in time_part:
                            time_parts = time_part.split(":")
                            time_str = f"{time_parts[0]}:{time_parts[1]}"
                        else:
                            time_str = time_part
                    else:
                        time_str = "Unknown"

                # Format height to 2 decimal places
                height_str = (
                    f"{height:.2f}m" if isinstance(height, (int, float)) else "Unknown"
                )

                # Create readable event description
                if event_type == "HighWater":
                    event_desc = "High Tide"
                elif event_type == "LowWater":
                    event_desc = "Low Tide"
                else:
                    event_desc = event_type

                tidal_event = f"{time_str} - {event_desc}: {height_str}"
                tidal_events.append(tidal_event)

        return "\n".join(tidal_events)

    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Failed to parse tidal data for {name}: {str(e)}")
        return f"Failed to parse the tidal data: {str(e)}. The structure might have changed or the location is invalid."


@mcp.tool()
async def find_nearby_tidal_stations(
    latitude: float, longitude: float, max_stations: int = 5
) -> str:
    """Find tidal stations near specified coordinates.

    Args:
        latitude: Latitude in decimal degrees (e.g., 50.3673 for Cornwall)
        longitude: Longitude in decimal degrees (e.g., -4.1424 for Cornwall, negative for West)
        max_stations: Maximum number of stations to return (default: 5, max: 20)
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        return "Invalid latitude. Must be between -90 and 90 degrees."

    if not (-180 <= longitude <= 180):
        return "Invalid longitude. Must be between -180 and 180 degrees."

    if not (1 <= max_stations <= 20):
        max_stations = min(max(max_stations, 1), 20)  # Clamp between 1 and 20

    # Find nearest stations
    nearest_stations = find_nearest_stations(latitude, longitude, max_stations)

    if not nearest_stations:
        return f"No tidal stations found near coordinates {latitude}, {longitude}."

    result_lines = [f"Tidal stations near {latitude}, {longitude}:"]

    for i, station in enumerate(nearest_stations, 1):
        distance_str = f"{station['distance_km']:.1f}km"
        station_info = (
            f"{i}. {station['name']} ({station['country']}) - {distance_str} away"
        )
        result_lines.append(station_info)

    result_lines.append(
        "\nUse the station name with get_tidal_times() to get tide information."
    )
    return "\n".join(result_lines)


@mcp.tool()
async def get_tidal_times_by_coordinates(latitude: float, longitude: float) -> str:
    """Get tidal times for the nearest station to specified coordinates.

    Args:
        latitude: Latitude in decimal degrees (e.g., 50.3673 for Cornwall)
        longitude: Longitude in decimal degrees (e.g., -4.1424 for Cornwall, negative for West)
    """
    # Validate inputs
    if not (-90 <= latitude <= 90):
        return "Invalid latitude. Must be between -90 and 90 degrees."

    if not (-180 <= longitude <= 180):
        return "Invalid longitude. Must be between -180 and 180 degrees."

    # Find the nearest station
    nearest_stations = find_nearest_stations(latitude, longitude, 1)

    if not nearest_stations:
        return f"No tidal stations found near coordinates {latitude}, {longitude}."

    nearest_station = nearest_stations[0]
    station_name = nearest_station["name"]
    distance = nearest_station["distance_km"]

    # Get tidal times for the nearest station
    tidal_data = await get_tidal_times(station_name, suggest_alternatives=False)

    # Prepend location information
    location_info = f"Nearest tidal station to {latitude}, {longitude}:\n"
    location_info += (
        f"{station_name} ({nearest_station['country']}) - {distance:.1f}km away\n\n"
    )

    return location_info + tidal_data


def main():
    """Main entry point for the MCP server."""
    logger.info("Starting UK Tides MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    # Initialize and run the server
    main()
