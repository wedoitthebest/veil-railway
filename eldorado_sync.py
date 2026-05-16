
import os
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import requests
from botocore.exceptions import ClientError
from pycognito import AWSSRP

from db import cfg, save, log
from services import product_service

BASE_URL = "https://www.eldorado.gg"
POOL_ID = "us-east-2_MlnzCFgHk"
CLIENT_ID = "1956req5ro9drdtbf5i6kis4la"
REGION = "us-east-2"

TOKEN_CACHE = {"token": None, "time": 0}

GAME_ALIASES = {
    "aotr": ["aotr", "attack on titan revolution", "attack-on-titan-revolution", "attack on titan", "yhwach"],
    "gpo": ["gpo", "grand piece online", "grand-piece-online", "grand piece"],
    "sbtd": ["sbtd", "spongebob tower defense", "spongebob-tower-defense", "sponge", "krusty", "pearl", "bubble blower", "secret formula", "karate throne", "golden limo", "moth wings", "luck of the irish"],
    "da-hood": ["da hood", "dahood", "da-hood"],
}

GAME_LABELS = {
    "aotr": "AOTR",
    "gpo": "GPO",
    "sbtd": "SBTD",
    "da-hood": "Da Hood",
    "other": "Other",
}

def authenticate():
    if TOKEN_CACHE["token"] and time.time() - TOKEN_CACHE["time"] < 45 * 60:
        return TOKEN_CACHE["token"]

    email = os.getenv("ELDORADO_EMAIL", "").strip()
    password = os.getenv("ELDORADO_PASSWORD", "").strip()

    if not email or not password:
        raise RuntimeError("Missing ELDORADO_EMAIL or ELDORADO_PASSWORD in .env")

    client = boto3.client("cognito-idp", region_name=REGION)

    try:
        try:
            aws_srp = AWSSRP(username=email, password=password, pool_id=POOL_ID, client_id=CLIENT_ID, client=client)
        except TypeError:
            aws_srp = AWSSRP(username=email, password=password, pool_id=POOL_ID, _client_id=CLIENT_ID, client=client)

        auth_params = aws_srp.get_auth_params()
        response = client.initiate_auth(AuthFlow="USER_SRP_AUTH", AuthParameters=auth_params, ClientId=CLIENT_ID)

        if response.get("ChallengeName") != "PASSWORD_VERIFIER":
            raise RuntimeError(f"Unexpected Cognito challenge: {response.get('ChallengeName')}")

        challenge_response = aws_srp.process_challenge(response["ChallengeParameters"], auth_params)
        response = client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName="PASSWORD_VERIFIER",
            ChallengeResponses=challenge_response,
        )

        token = response["AuthenticationResult"]["IdToken"]
        TOKEN_CACHE["token"] = token
        TOKEN_CACHE["time"] = time.time()
        return token

    except ClientError as exc:
        err = exc.response.get("Error", {})
        raise RuntimeError(f"Cognito auth failed: {err.get('Code')} - {err.get('Message')}")
    except Exception as exc:
        raise RuntimeError(f"Cognito auth failed: {exc}")

def auth_headers(game_id: str = "70") -> Dict[str, str]:
    token = authenticate()
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "de-DE,de;q=0.7,en-US;q=0.5,en;q=0.3",
        "Cache-Control": "no-cache",
        "Cookie": f"__Host-EldoradoIdToken={token}",
        "Referer": f"{BASE_URL}/sell/offer/CustomItem/{game_id}",
        "swagger": "Swager request",
        "User-Agent": "VeilDiscordControlCenter/26.0",
    }

def api_error(resp: requests.Response) -> str:
    try:
        data = resp.json()
        msgs = data.get("messages") or data.get("errors") or data.get("message") or data.get("title") or resp.text
        if isinstance(msgs, list):
            out = []
            for m in msgs:
                if isinstance(m, dict):
                    out.append(str(m.get("message") or m.get("error") or m))
                else:
                    out.append(str(m))
            return "; ".join(out)
        if isinstance(msgs, dict):
            return json.dumps(msgs, ensure_ascii=False)
        return str(msgs)
    except Exception:
        return (resp.text or resp.reason or "Unknown error")[:500]

def request_or_error(method: str, path: str, *, params=None, json_body=None, timeout=30) -> requests.Response:
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    headers = auth_headers()
    data = None
    if json_body is not None:
        headers = {**headers, "Content-Type": "application/json"}
        data = json.dumps(json_body)
    resp = requests.request(method.upper(), url, headers=headers, params=params, data=data, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"API {resp.status_code}: {api_error(resp)}")
    return resp

def parse_json_or_text(resp: requests.Response) -> Any:
    if not resp.text:
        return {"ok": True, "status": resp.status_code}
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text, "status": resp.status_code}

def _money_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("amount", "value", "price", "priceInUSD"):
            if key in value:
                try:
                    return float(value[key])
                except Exception:
                    pass
    if isinstance(value, str):
        m = re.search(r"\d+(?:[.,]\d+)?", value)
        if m:
            try:
                return float(m.group(0).replace(",", "."))
            except Exception:
                pass
    return None

def _price_string(offer: Dict[str, Any]) -> str:
    pricing = offer.get("pricing") if isinstance(offer.get("pricing"), dict) else {}
    candidates = [
        offer.get("pricePerUnitInUSD"),
        offer.get("pricePerUnitWithDiscountInUSD"),
        pricing.get("pricePerUnitInUSD"),
        offer.get("priceInUSD"),
        offer.get("pricePerUnit"),
        offer.get("pricePerUnitWithDiscount"),
        pricing.get("pricePerUnit"),
        offer.get("price"),
        offer.get("unitPrice"),
    ]
    for candidate in candidates:
        amount = _money_amount(candidate)
        if amount is not None:
            return f"${amount:g}"
    return "Ask"

def _slug(value: str) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "other"

def _game_slug_from_listing(title: str, game_name: str, game_id: str, category: str, raw: Dict[str, Any]) -> str:
    hay = " ".join([str(title or ""), str(game_name or ""), str(game_id or ""), str(category or ""), json.dumps(raw, ensure_ascii=False)[:2000]]).lower()
    for slug, aliases in GAME_ALIASES.items():
        if any(alias in hay for alias in aliases):
            return slug

    if game_name:
        cleaned = _slug(game_name)
        if cleaned in ("spongebob-tower-defense", "spongebob"):
            return "sbtd"
        if cleaned in ("grand-piece-online", "grand-piece"):
            return "gpo"
        if cleaned in ("attack-on-titan-revolution", "attack-on-titan"):
            return "aotr"
        if cleaned in ("da-hood", "dahood"):
            return "da-hood"
        return cleaned

    return "other"

def _game_label(slug: str, game_name: str = "") -> str:
    return GAME_LABELS.get(slug, str(game_name or slug).replace("-", " ").title())

def _active_state(value: Any) -> bool:
    s = str(value or "Active").lower()
    return not any(bad in s for bad in ["paused", "deleted", "inactive", "closed", "disabled", "soldout", "sold out"])

def _extract_listing(offer: Dict[str, Any]) -> Dict[str, Any]:
    # This mirrors the working extraction from the tool you uploaded.
    price_obj = offer.get("pricePerUnit") or (offer.get("pricing") or {}).get("pricePerUnit") if isinstance(offer.get("pricing"), dict) else offer.get("pricePerUnit")
    game_id = (
        offer.get("gameId")
        or (offer.get("augmentedGame") or {}).get("gameId") if isinstance(offer.get("augmentedGame"), dict) else offer.get("gameId")
    )
    game_id = game_id or ((offer.get("game") or {}).get("id") if isinstance(offer.get("game"), dict) else "")
    title = offer.get("offerTitle") or offer.get("title") or ""
    game_name = offer.get("gameSeoAlias") or offer.get("gameCategoryTitle") or offer.get("gameName") or ""
    category = offer.get("category") or offer.get("offerType") or "CustomItem"
    quantity = offer.get("quantity") or offer.get("stock") or 0
    try:
        quantity = int(quantity or 0)
    except Exception:
        quantity = 0
    state = offer.get("offerState") or offer.get("state") or ""
    delivery = offer.get("guaranteedDeliveryTime") or offer.get("deliveryTime") or ""
    offer_id = str(offer.get("id") or offer.get("offerId") or offer.get("offer_id") or "").strip()
    url = f"https://www.eldorado.gg/offers/{offer_id}" if offer_id else ""
    slug = _game_slug_from_listing(title, game_name, str(game_id or ""), category, offer)

    return {
        "source": "eldorado",
        "external_id": offer_id,
        "external_url": url,
        "name": str(title or "Eldorado Listing")[:180],
        "price": _price_string(offer),
        "stock": quantity,
        "raw_game": game_name or str(game_id or "") or category,
        "category": _game_label(slug, game_name),
        "game_slug": slug,
        "delivery_type": str(delivery or "Manual")[:60],
        "description": f"Synced from Eldorado. State: {state}. Game: {game_name or game_id or 'unknown'}",
        "enabled": _active_state(state) and quantity > 0,
        "emoji": "🛒",
        "source_payload": json.dumps(offer, ensure_ascii=False)[:20000],
    }

def fetch_eldorado_offers(page_size: int = 40, max_pages: int = 20) -> Dict[str, Any]:
    total = 0
    pages = 0
    errors = []
    offers = []
    seen = set()

    for page in range(1, max_pages + 1):
        try:
            resp = request_or_error(
                "GET",
                "/api/v1/item-management/me/offers/me/search",
                params={"pageIndex": page, "pageSize": page_size},
                timeout=25,
            )
            data = parse_json_or_text(resp)
            results = data.get("results") or []
            if not isinstance(results, list) or not results:
                break

            for item in results:
                offer = item.get("offer") if isinstance(item, dict) and isinstance(item.get("offer"), dict) else item
                if not isinstance(offer, dict):
                    continue
                offer_id = str(offer.get("id") or offer.get("offerId") or offer.get("offer_id") or "").strip()
                if not offer_id:
                    continue
                if offer_id in seen:
                    continue
                seen.add(offer_id)
                offers.append(offer)
                total += 1

            pages += 1
            total_pages = data.get("totalPages") or page
            try:
                total_pages = int(total_pages)
            except Exception:
                total_pages = page
            if page >= total_pages:
                break
        except Exception as exc:
            errors.append(str(exc))
            break

    return {"offers": offers, "total": total, "pages": pages, "errors": errors}

def sync_eldorado_products():
    product_service.init_products()
    fetched = fetch_eldorado_offers()
    offers = fetched["offers"]

    normalized = []
    external_ids = []
    per_game = {}

    for offer in offers:
        listing = _extract_listing(offer)
        if not listing["external_id"]:
            continue
        normalized.append(listing)
        external_ids.append(listing["external_id"])
        per_game[listing["game_slug"]] = per_game.get(listing["game_slug"], 0) + 1
        product_service.upsert_external_product(listing)

    disabled = product_service.disable_missing_external("eldorado", external_ids)

    x = cfg()
    x["last_eldorado_sync"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    x["last_eldorado_count"] = len(normalized)
    x["last_eldorado_pages"] = fetched["pages"]
    x["last_eldorado_per_game"] = per_game
    save(x)

    log("INFO", f"Eldorado working sync imported/updated {len(normalized)} listings across {fetched['pages']} pages; disabled missing {disabled}")

    return {
        "ok": not bool(fetched["errors"]),
        "count": len(normalized),
        "pages": fetched["pages"],
        "disabled_missing": disabled,
        "per_game": per_game,
        "last_sync": x["last_eldorado_sync"],
        "sample": [
            {
                "id": p["external_id"],
                "name": p["name"],
                "game": p["category"],
                "game_slug": p["game_slug"],
                "stock": p["stock"],
                "price": p["price"],
            }
            for p in normalized[:12]
        ],
        "errors": fetched["errors"],
    }
