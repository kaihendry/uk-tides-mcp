stations.json:
	curl https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations -H "Ocp-Apim-Subscription-Key: $(UKHO_API_KEY)" | jq .features > stations.json

clean:
	rm -f stations.json

.PHONY: debug
debug:
	npx @modelcontextprotocol/inspector -e UKHO_API_KEY=$(UKHO_API_KEY)