"""Talkdesk Flows API client: start a Studio flow with an "API request" trigger (agentless outbound call).

  token:  POST https://<account>.talkdeskid.com/oauth/token   (client credentials, scope flows-interactions:start)
  start:  POST <api>/flows/<flow_id>/interactions  {input arguments as strings}  -> 202 {interaction_id, ...}

Used only from the jobs runner and the ops trigger, never inside an MCP tool call. Talkdesk allows 2 requests per
second per account; the dispatcher paces itself below that.
"""

import threading
import time

import httpx

from . import config

SCOPE = "flows-interactions:start"
_lock = threading.Lock()
_token = {"value": "", "expires": 0.0}


class TalkdeskError(Exception):
    pass


def configured() -> bool:
    return bool(config.OUTBOUND_ENABLED and config.TALKDESK_ACCOUNT and config.TALKDESK_CLIENT_ID
                and config.TALKDESK_CLIENT_SECRET and config.TALKDESK_OUTBOUND_FLOW_ID)


def missing() -> list[str]:
    need = {"OUTBOUND_ENABLED=true": config.OUTBOUND_ENABLED, "TALKDESK_ACCOUNT": config.TALKDESK_ACCOUNT,
            "TALKDESK_CLIENT_ID": config.TALKDESK_CLIENT_ID, "TALKDESK_CLIENT_SECRET": config.TALKDESK_CLIENT_SECRET,
            "TALKDESK_OUTBOUND_FLOW_ID": config.TALKDESK_OUTBOUND_FLOW_ID}
    return [k for k, v in need.items() if not v]


def _access_token() -> str:
    with _lock:
        if _token["value"] and _token["expires"] > time.time() + 60:
            return _token["value"]
        r = httpx.post(f"https://{config.TALKDESK_ACCOUNT}.talkdeskid.com/oauth/token",
                       data={"grant_type": "client_credentials", "scope": SCOPE},
                       auth=(config.TALKDESK_CLIENT_ID, config.TALKDESK_CLIENT_SECRET), timeout=10)
        if r.status_code != 200:
            raise TalkdeskError(f"token {r.status_code}: {r.text[:200]}")
        body = r.json()
        _token["value"], _token["expires"] = body["access_token"], time.time() + int(body.get("expires_in", 600))
        return _token["value"]


def start_flow(inputs: dict) -> str:
    """Start the outbound flow; returns Talkdesk's interaction_id. Every input is sent as a string (Studio rule)."""
    body = {k: "" if v is None else str(v) for k, v in inputs.items()}
    url = f"{config.TALKDESK_API}/flows/{config.TALKDESK_OUTBOUND_FLOW_ID}/interactions"
    for attempt in (1, 2):
        r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {_access_token()}"}, timeout=15)
        if r.status_code == 401 and attempt == 1:          # token revoked or expired early: fetch a new one once
            _token["value"] = ""
            continue
        if r.status_code not in (200, 201, 202):
            raise TalkdeskError(f"flows {r.status_code}: {r.text[:200]}")
        return r.json().get("interaction_id", "")
    raise TalkdeskError("flows 401 after token refresh")
