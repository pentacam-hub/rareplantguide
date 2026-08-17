"""
Publish at most one already-generated Pinterest Pin (image + metadata)
that is still marked as "pending" in content-queue.yaml.

Run this AFTER generate_post.py has committed and pushed and AFTER
Cloudflare has deployed the site, so Pinterest can fetch the live image.

Required environment variables:
    PINTEREST_APP_ID
    PINTEREST_APP_SECRET
    PINTEREST_REFRESH_TOKEN
    PINTEREST_REFRESH_TOKEN_FILE
"""

import base64
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import requests
import yaml

QUEUE_PATH = "content-queue.yaml"
SITE_BASE_URL = "https://therareplantguide.com"
POST_URL_PREFIX = "/posts"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"

DEFAULT_BOARD = (
    "Rare Plant Care Tips",
    "Practical rare houseplant care, troubleshooting, propagation and collecting guides from The Rare Plant Guide.",
)

BOARD_BY_CLUSTER = {
    "variegation-care": (
        "Variegated Plant Care & Monstera Tips",
        "Variegated Monstera, Philodendron and Syngonium care tips covering light, reversion, growth and healthy variegation.",
    ),
    "propagation": (
        "Rare Plant Propagation & Rooting",
        "Rare plant propagation guides for cuttings, nodes, sphagnum moss, rooting, acclimation and healthy new growth.",
    ),
    "care-troubleshooting": (
        "Rare Plant Problems & Care Solutions",
        "Troubleshooting guides for root rot, pests, soil, humidity, repotting, fertilizer and everyday rare plant care problems.",
    ),
    "buying-market": (
        "Rare Plant Buying, Prices & Collecting",
        "Guides to buying rare plants, avoiding scams, understanding prices, tissue culture and building a collection wisely.",
    ),
}


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def pick_pending_pin(queue):
    """Return the oldest pending Pin so a run never publishes more than one."""
    for topic in queue.get("topics", []):
        if topic.get("status") == "done" and topic.get("pin_status") == "pending":
            return topic
    return None


def get_board_config(topic):
    return BOARD_BY_CLUSTER.get(topic.get("cluster"), DEFAULT_BOARD)


def build_pin_description(topic):
    """Build a keyword-rich but readable description, capped at 500 chars."""
    base = (topic.get("pin_description") or "").strip()
    keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]

    parts = []
    if base:
        parts.append(base.rstrip(" .") + ".")
    if keywords:
        parts.append("Covers " + ", ".join(keywords[:3]) + ".")
    parts.append("Save this guide for later and read the full step-by-step article.")

    description = " ".join(parts)
    return description[:500].rstrip()


def build_alt_text(topic):
    title = (topic.get("pin_title") or topic.get("title") or "Rare plant care guide").strip()
    keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]
    if keywords:
        return f"{title}. Visual guide about {', '.join(keywords[:3])}."[:500]
    return title[:500]


def get_access_token(app_id, app_secret, refresh_token):
    basic = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    resp = requests.post(
        f"{PINTEREST_API_BASE}/oauth/token",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload["access_token"], payload.get("refresh_token")


def save_rotated_refresh_token(refresh_token):
    """Store the rotated token in a runner-only file for the workflow to persist."""
    token_path = os.environ.get("PINTEREST_REFRESH_TOKEN_FILE")
    if not refresh_token or not token_path:
        return
    fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as token_file:
        token_file.write(refresh_token)


def get_or_create_board(access_token, board_name, board_description):
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = requests.get(
        f"{PINTEREST_API_BASE}/boards",
        headers=headers,
        params={"page_size": 100},
        timeout=20,
    )
    resp.raise_for_status()
    for board in resp.json().get("items", []):
        if board["name"].strip().lower() == board_name.strip().lower():
            return board["id"]

    create_resp = requests.post(
        f"{PINTEREST_API_BASE}/boards",
        headers={**headers, "Content-Type": "application/json"},
        json={"name": board_name, "description": board_description},
        timeout=20,
    )
    create_resp.raise_for_status()
    return create_resp.json()["id"]


def create_pin(access_token, board_id, topic):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    slug = topic["slug"]
    image_url = f"{SITE_BASE_URL}{topic['pin_image_path']}"
    article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{slug}/"

    payload = {
        "board_id": board_id,
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": article_url,
        "title": topic["pin_title"][:100],
        "description": build_pin_description(topic),
        "alt_text": build_alt_text(topic),
    }
    resp = requests.post(f"{PINTEREST_API_BASE}/pins", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def canonical_link(url):
    """Normalize a Pin/article URL for duplicate detection."""
    if not url:
        return ""
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def find_existing_pin(access_token, article_url, max_pages=5):
    """Prevent a retry from duplicating a Pin if the previous response was lost."""
    headers = {"Authorization": f"Bearer {access_token}"}
    bookmark = None
    target = canonical_link(article_url)

    for _ in range(max_pages):
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        resp = requests.get(f"{PINTEREST_API_BASE}/pins", headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        for pin in payload.get("items", []):
            if canonical_link(pin.get("link", "")) == target:
                return pin
        bookmark = payload.get("bookmark")
        if not bookmark:
            break
    return None


def main():
    app_id = os.environ.get("PINTEREST_APP_ID")
    app_secret = os.environ.get("PINTEREST_APP_SECRET")
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN")

    if not all([app_id, app_secret, refresh_token]):
        print(
            "Pinterest credentials missing "
            "(PINTEREST_APP_ID / PINTEREST_APP_SECRET / PINTEREST_REFRESH_TOKEN)."
        )
        sys.exit(1)

    queue = load_queue()
    topic = pick_pending_pin(queue)
    if not topic:
        print("No pending Pinterest Pin found.")
        sys.exit(0)

    access_token, rotated_refresh_token = get_access_token(app_id, app_secret, refresh_token)
    save_rotated_refresh_token(rotated_refresh_token)

    board_name, board_description = get_board_config(topic)
    board_id = get_or_create_board(access_token, board_name, board_description)

    try:
        article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/"
        existing_pin = find_existing_pin(access_token, article_url)
        if existing_pin:
            result = existing_pin
            print(f"Pin already exists for '{topic['pin_title']}'. Updating local status only.")
        else:
            result = create_pin(access_token, board_id, topic)
            print(
                f"Pinterest Pin published for '{topic['pin_title']}' "
                f"to board '{board_name}' (id: {result.get('id')})"
            )
        topic["pin_status"] = "posted"
        topic["pinterest_pin_id"] = result.get("id")
        topic["pinterest_board"] = board_name
    except Exception as exc:
        print(f"Pinterest publication failed for '{topic.get('pin_title')}': {exc}")
        raise

    save_queue(queue)


if __name__ == "__main__":
    main()
