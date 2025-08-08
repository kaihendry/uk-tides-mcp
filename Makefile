stations.json:
	curl https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations -H "Ocp-Apim-Subscription-Key: $(PRIMARY)" | jq .features > stations.json

clean:
	rm -f stations.json

.PHONY: debug
debug:
    npx @modelcontextprotocol/inspector uv run tides.py