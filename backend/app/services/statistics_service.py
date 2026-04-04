"""Statistics data service — pulls data from public APIs.

Sources:
- Singapore: data.gov.sg
- World Bank: api.worldbank.org
- WHO: Global Health Observatory
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("tuesday.statistics")

TIMEOUT = 15.0


async def query_statistics(inp: dict) -> str:
    """Query statistics from public data sources."""
    source = inp.get("source", "singapore").lower()
    query = inp.get("query", "")
    indicator = inp.get("indicator", "")

    if source == "singapore":
        return await _query_singapore(query, indicator, inp)
    elif source == "world_bank":
        return await _query_world_bank(query, indicator, inp)
    elif source == "who":
        return await _query_who(query, indicator, inp)
    else:
        return f"Unknown source: {source}. Available: singapore, world_bank, who"


async def _query_singapore(query: str, indicator: str, inp: dict) -> str:
    """Query data.gov.sg datasets."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if indicator:
            # Direct dataset fetch
            resp = await client.get(
                f"https://data.gov.sg/api/action/datastore_search",
                params={"resource_id": indicator, "limit": 20},
            )
        else:
            # Search for datasets
            resp = await client.get(
                f"https://data.gov.sg/api/action/package_search",
                params={"q": query, "rows": 10},
            )

        if resp.status_code != 200:
            return f"data.gov.sg returned {resp.status_code}"

        data = resp.json()

        if "result" not in data:
            return "No results from data.gov.sg"

        result = data["result"]

        if indicator:
            # Dataset records
            records = result.get("records", [])
            if not records:
                return f"No records found for dataset {indicator}"
            # Format first few records
            fields = list(records[0].keys()) if records else []
            lines = [f"Dataset: {indicator} ({len(records)} records, fields: {', '.join(fields[:8])})"]
            for r in records[:10]:
                vals = [f"{k}: {v}" for k, v in list(r.items())[:6]]
                lines.append("  " + " | ".join(vals))
            if len(records) > 10:
                lines.append(f"  ... and {len(records) - 10} more records")
            return "\n".join(lines)
        else:
            # Search results
            results = result.get("results", [])
            if not results:
                return f"No datasets found for '{query}' on data.gov.sg"
            lines = [f"Found {result.get('count', len(results))} datasets for '{query}':"]
            for ds in results[:10]:
                name = ds.get("title", "Untitled")
                org = ds.get("organization", {}).get("title", "")
                resources = ds.get("resources", [])
                res_id = resources[0]["id"] if resources else "N/A"
                lines.append(f"- {name} (org: {org}, resource_id: {res_id})")
            return "\n".join(lines)


async def _query_world_bank(query: str, indicator: str, inp: dict) -> str:
    """Query World Bank Open Data API."""
    country = inp.get("country", "SGP")  # Default to Singapore
    year_from = inp.get("year_from", "2010")
    year_to = inp.get("year_to", "2024")

    if not indicator:
        # Search for indicators
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"https://api.worldbank.org/v2/indicator",
                params={"format": "json", "per_page": 10, "search": query or "population"},
            )
            if resp.status_code != 200:
                return f"World Bank API returned {resp.status_code}"
            data = resp.json()
            if len(data) < 2:
                return "No indicators found."
            indicators = data[1]
            lines = ["World Bank indicators:"]
            for ind in indicators:
                lines.append(f"- {ind['id']}: {ind['name']}")
            lines.append("\nUse an indicator ID to fetch data (e.g., SP.POP.TOTL for population)")
            return "\n".join(lines)

    # Fetch indicator data
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
            params={
                "format": "json",
                "per_page": 50,
                "date": f"{year_from}:{year_to}",
            },
        )

    if resp.status_code != 200:
        return f"World Bank API returned {resp.status_code}"

    data = resp.json()
    if len(data) < 2 or not data[1]:
        return f"No data for indicator {indicator} in {country}"

    records = data[1]
    lines = [f"{records[0]['indicator']['value']} — {records[0]['country']['value']}:"]
    for r in records:
        if r["value"] is not None:
            lines.append(f"  {r['date']}: {r['value']:,.2f}" if isinstance(r['value'], float)
                        else f"  {r['date']}: {r['value']}")

    return "\n".join(lines)


async def _query_who(query: str, indicator: str, inp: dict) -> str:
    """Query WHO Global Health Observatory API."""
    country = inp.get("country", "SGP")

    if not indicator:
        # Search indicators
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                "https://ghoapi.azureedge.net/api/Indicator",
                params={"$filter": f"contains(IndicatorName,'{query or 'life expectancy'}')", "$top": 10},
            )
            if resp.status_code != 200:
                return f"WHO API returned {resp.status_code}"
            data = resp.json()
            indicators = data.get("value", [])
            if not indicators:
                return f"No WHO indicators found for '{query}'"
            lines = ["WHO Global Health Observatory indicators:"]
            for ind in indicators:
                lines.append(f"- {ind['IndicatorCode']}: {ind['IndicatorName']}")
            return "\n".join(lines)

    # Fetch data
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"https://ghoapi.azureedge.net/api/{indicator}",
            params={
                "$filter": f"SpatialDim eq '{country}'",
                "$top": 20,
                "$orderby": "TimeDim desc",
            },
        )

    if resp.status_code != 200:
        return f"WHO API returned {resp.status_code}"

    data = resp.json()
    records = data.get("value", [])
    if not records:
        return f"No WHO data for {indicator} in {country}"

    lines = [f"WHO data for {indicator} — {country}:"]
    for r in records:
        year = r.get("TimeDim", "?")
        value = r.get("NumericValue", r.get("Value", "N/A"))
        lines.append(f"  {year}: {value}")

    return "\n".join(lines)
