# UK tide times MCP

Signup for $UKHO_API_KEY here: https://admiraltyapi.developer.azure-api.net/

UK Tidal API - Discovery is free for a year

    claude mcp add uktides -s project -e UKHO_API_KEY=$UKHO_API_KEY -- uv run -m uk_tides_mcp.tides