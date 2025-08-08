import logging
import os
import json
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

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
        with open("stations.json", "r") as f:
            data = json.load(f)

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
async def get_tidal_times(name: str) -> str:
    """Returns tidal times for a specific location.

    Args:
        name: Name of the location (e.g., "FOWEY")
    """
    # Lookup station ID from name
    stationId = lookup_station_id(name)
    if not stationId:
        return f"Location '{name}' not found. Please check the spelling or try a different location name."

    # log the lookup
    logger.info(f"Looking up station ID for location: {name} -> {stationId}")

    url = f"{UKHO_API_BASE}Stations/{stationId}/TidalEvents"
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

        # Group events by date
        events_by_date = {}
        for event in data:
            date_time = event.get("DateTime", "")
            if date_time:
                # Extract date part (YYYY-MM-DD)
                date_part = date_time.split("T")[0]
                if date_part not in events_by_date:
                    events_by_date[date_part] = []
                events_by_date[date_part].append(event)

        # Process each day's tidal events
        for date in sorted(events_by_date.keys()):
            tidal_events.append(f"\n=== {date} ===")

            day_events = events_by_date[date]
            # Sort events by time within the day
            day_events.sort(key=lambda x: x.get("DateTime", ""))

            for event in day_events:
                event_type = event.get("EventType", "Unknown")
                date_time = event.get("DateTime", "")
                height = event.get("Height", 0)

                # Extract time from DateTime (format: 2025-08-08T04:42:52.5)
                if "T" in date_time:
                    time_part = date_time.split("T")[1]
                    # Remove seconds and fractional seconds for cleaner display
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


if __name__ == "__main__":
    # Initialize and run the server
    logger.info("Starting UK Weather MCP Server")
    mcp.run(transport="stdio")
