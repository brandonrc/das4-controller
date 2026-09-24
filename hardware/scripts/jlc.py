#!/usr/bin/env python3
"""Search JLCPCB's assembly parts library (public API, no login needed).

    python3 hardware/scripts/jlc.py "RP2350B"
    python3 hardware/scripts/jlc.py C42415655 C165948      # check specific parts
    python3 hardware/scripts/jlc.py -n 20 "USB hub"

Prints LCSC code, Basic/Extended, stock, 1-off price, package, part number.
Basic parts carry no per-part loading fee at JLCPCB; Extended ones do.
"""
import argparse
import json
import urllib.request

API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
TYPE = {"base": "Basic", "expand": "Extended"}


def search(keyword, n=10):
    body = json.dumps({"keyword": keyword, "currentPage": 1, "pageSize": n}).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json",
                                             "User-Agent": "das4-controller-parts/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)["data"]["componentPageInfo"]
    return data.get("list") or []


def row(p):
    price = (p.get("componentPrices") or [{}])[0].get("productPrice", "")
    return (f"{p['componentCode']:<11} {TYPE.get(p['componentLibraryType'], p['componentLibraryType']):<8} "
            f"{p['stockCount']:>8} ${price!s:<8} {p.get('componentSpecificationEn') or '':<22} "
            f"{p.get('componentBrandEn') or ''} {p['componentModelEn']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("-n", type=int, default=10, help="results per query")
    ap.add_argument("--describe", action="store_true", help="also print the description")
    a = ap.parse_args()
    for q in a.query:
        print(f"== {q}")
        for p in search(q, a.n):
            print(row(p))
            if a.describe:
                print("   ", (p.get("describe") or "")[:200])


if __name__ == "__main__":
    main()
