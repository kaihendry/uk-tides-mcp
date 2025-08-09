uk_tides_mcp/stations.json:
	curl https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations -H "Ocp-Apim-Subscription-Key: $(UKHO_API_KEY)" | jq .features > uk_tides_mcp/stations.json

clean:
	rm -f uk_tides_mcp/stations.json

.PHONY: debug
debug:
	npx @modelcontextprotocol/inspector -e UKHO_API_KEY=$(UKHO_API_KEY)

# https://docs.astral.sh/uv/guides/package/#publishing-your-package
release: # relies on UV_PUBLISH_TOKEN being set 
	rm -rf dist
	uv version --bump minor
	uv build
	uv publish