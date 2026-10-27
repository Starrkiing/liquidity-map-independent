#!/usr/bin/env python3
"""Public-source US liquidity research collector; no Claude inputs or credentials.

This is a NEW, limited-scope collector. It is NOT the prior ChatGPT Sites source
and cannot be described as a byte-identical migration of that deployment.
"""
import csv
import hashlib
import io
import json
import os
import time as _time
from datetime import date, datetime, timedelta, timezone, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
FED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
TGA = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
# FRED: request ~400 days only (enough for three aligned observations and the weekly carry-forward);
# the full 20-year CSV is slow from GitHub runners and timed out on the first hosted run (run 40425518688).
FRED_START = (date.today() - timedelta(days=400)).isoformat()
URLS = {
    "walcl": FED + "WALCL&cosd=" + FRED_START,
    "rrp": FED + "RRPONTSYD&cosd=" + FRED_START,
    "tga": TGA + "?" + urlencode({
        "filter": "account_type:eq:Treasury General Account (TGA) Closing Balance",
        "fields": "record_date,account_type,open_today_bal",
        "sort": "-record_date",
        "page[size]": "100",
    }),
}
D = Decimal


def prior_business_day(d):
    d -= timedelta(days=1)
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d


def expected_date(source, now_et):
    today = now_et.date()
    if source == "tga":
        return prior_business_day(today) if now_et.time() >= time(16) else prior_business_day(prior_business_day(today))
    if source == "rrp":
        return today if today.weekday() < 5 and now_et.time() >= time(15) else prior_business_day(today)
    if source == "walcl":
        # Latest available H.4.1 observation is Wednesday, normally released Thursday 16:30 ET.
        back = (today.weekday() - 2) % 7
        wednesday = today - timedelta(days=back)
        if today.weekday() == 2 or (today.weekday() == 3 and now_et.time() < time(17)):
            wednesday -= timedelta(days=7)
        return wednesday
    raise ValueError(source)


def status_for(source, latest, now_et):
    if latest is None:
        return "MISSING"
    return "LATE" if latest < expected_date(source, now_et) else "CURRENT"


def fetch(url, tries=3, timeout=90, wait=10):
    """GET with retries. Three attempts, 90 s each, 10 s then 20 s backoff; the last error is raised."""
    last = None
    for attempt in range(tries):
        try:
            request = Request(url, headers={"User-Agent": "Starrkiing-Liquidity-Independent/0.1 (public research collector)"})
            with urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                data = response.read(8_000_001)
                if len(data) > 8_000_000:
                    raise ValueError("source too large")
                return data
        except Exception as e:  # network errors and timeouts are retried; the last one is reported
            last = e
            if attempt < tries - 1:
                _time.sleep(wait * (attempt + 1))
    raise last


def parse_fred(raw, series):
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if series not in (rows.fieldnames or []):
        raise ValueError(f"missing FRED column {series}")
    output = {}
    for row in rows:
        stamp = row.get("observation_date") or row.get("DATE") or row.get("date")
        number = row.get(series, ".")
        if not stamp or number in ("", ".", None):
            continue
        try:
            output[date.fromisoformat(stamp)] = D(number)
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"invalid {series} observation") from exc
    if not output:
        raise ValueError("empty FRED series")
    return output


def parse_tga(raw):
    payload = json.loads(raw)
    if not isinstance(payload.get("data"), list):
        raise ValueError("missing FiscalData data list")
    output = {}
    for row in payload["data"]:
        if row.get("account_type") != "Treasury General Account (TGA) Closing Balance":
            continue
        val = row.get("open_today_bal")
        if val is None or val == "":
            continue
        d = date.fromisoformat(row["record_date"])
        if d in output:
            raise ValueError("duplicate Treasury date")
        output[d] = D(val)
    if not output:
        raise ValueError("no TGA closing balance; fail closed")
    return output


def last_available(observations, through):
    eligible = [d for d in observations if d <= through]
    if not eligible:
        raise ValueError("missing aligned source")
    d = max(eligible)
    return d, observations[d]


def calculate_last3(walcl, tga, rrp):
    results = []
    for d in sorted(tga, reverse=True):
        try:
            fd, f = last_available(walcl, d)
            rd, r = last_available(rrp, d)
        except ValueError:
            continue
        # WALCL and TGA in millions USD; RRPONTSYD in billions USD.
        net = (f - tga[d]) / D("1000") - r
        results.append({
            "date": d.isoformat(),
            "us_net_liquidity_bn": str(net.quantize(D("0.000001"))),
            "walcl_date": fd.isoformat(),
            "tga_date": d.isoformat(),
            "rrp_date": rd.isoformat(),
        })
        if len(results) == 3:
            break
    return list(reversed(results))


def collect(now=None, raw_sources=None):
    now = now or datetime.now(timezone.utc)
    now_et = now.astimezone(NY)
    raw_sources = raw_sources or {}
    sources, parsed = {}, {}
    for name, url in URLS.items():
        try:
            raw = raw_sources[name] if name in raw_sources else fetch(url)
            obs = parse_tga(raw) if name == "tga" else parse_fred(raw, "WALCL" if name == "walcl" else "RRPONTSYD")
            latest = max(obs)
            sources[name] = {
                "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                "observed_through": latest.isoformat(), "expected_through": expected_date(name, now_et).isoformat(),
                "status": status_for(name, latest, now_et),
                "latest_value": str(obs[latest]),
                "unit": "USD million" if name != "rrp" else "USD billion",
            }
            parsed[name] = obs
        except Exception as exc:
            # Do not make up observations or drop a failed source silently.
            sources[name] = {"url": url, "status": "FETCH_FAILED", "error": str(exc)[:160],
                             "observed_through": None, "sha256": None}
    usable = len(parsed) == 3
    last3 = calculate_last3(parsed["walcl"], parsed["tga"], parsed["rrp"]) if usable else []
    if usable and not last3:
        usable = False
    status = "FETCH_FAILED" if not usable else ("LATE" if any(v["status"] != "CURRENT" for v in sources.values()) else "CURRENT")
    data = {
        "schema": 1, "collector": "independent-public-sources-v0.1",
        "claim": "US research proxy only; not a complete mirror of ChatGPT Sites",
        "captured_at_utc": now.isoformat(),
        "status": status, "collector_exit_status": "completed_with_warnings" if status != "CURRENT" else "success",
        "sources": sources, "us_net_liquidity_bn_last3": last3,
        "omitted_panels": ["SPX dealer gamma", "dark-pool data", "forecast narrative",
                           "ECB/Cboe/BoJ global decomposition (not yet migrated)"],
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    data["digest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return data


def main():
    data = collect()
    root = Path(os.environ.get("OUTPUT_DIR", "."))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = root / "receipts" / (stamp + ".json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: NEVER overwrite an earlier vintage.
    with dest.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    latest = root / "dist" / "api" / "provenance.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(dest), "status": data["status"], "digest": data["digest_sha256"]}))
    # Warnings are carried forward into published receipts and page banner; fail closed on missing data.
    return 0  # Workflow preserves the receipt, then fails the run if the source failed.


if __name__ == "__main__":
    raise SystemExit(main())
