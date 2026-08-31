"""Prepare and publish one Pinterest Pin from the dedicated buying-guide queue."""

import argparse
import datetime
import os
import sys

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

from scripts.post_pin import (
    PINTEREST_API_BASE,
    POST_URL_PREFIX,
    SITE_BASE_URL,
    build_alt_text,
    build_image_media_source,
    get_access_token,
    get_or_create_board,
    save_rotated_refresh_token,
)
from scripts.post_promo_pin import (
    FONT_PATH,
    build_promo_image,
    find_existing_promo_pin,
)

QUEUE_PATH = "promo-buying-guides.yaml"
NO_CANDIDATE_EXIT = 3
COMMERCIAL_MIN_GAP_DAYS = 2
COMMERCIAL_BOARD = (
    "Rare Plant Buying, Prices & Collecting",
    "Buying guides, product comparisons, rare plant prices, collecting advice and practical gear for rare plant growers.",
)


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"topics": []}


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def pick_topic(queue, statuses):
    """Pick the highest-priority topic while preserving queue order for ties."""
    candidates = [
        (index, topic)
        for index, topic in enumerate(queue.get("topics", []))
        if topic.get("status") in statuses
    ]
    if not candidates:
        return None

    def sort_key(item):
        index, topic = item
        try:
            priority = int(topic.get("priority", 999))
        except (TypeError, ValueError):
            priority = 999
        return priority, index

    return min(candidates, key=sort_key)[1]


def latest_commercial_pin_date(queue):
    dates = []
    for topic in queue.get("topics", []):
        if topic.get("status") != "posted":
            continue
        published = parse_date(topic.get("published_pin_date"))
        if published:
            dates.append(published)
    return max(dates) if dates else None


def commercial_slot_open(queue, today=None):
    """Limit buying-guide Pins so evergreen content still fills most promo slots."""
    today = today or datetime.date.today()
    latest = latest_commercial_pin_date(queue)
    return latest is None or (today - latest).days >= COMMERCIAL_MIN_GAP_DAYS


def destination_url(topic):
    """Return the real commercial landing URL when the queue provides one."""
    destination = str(topic.get("destination_path") or "").strip()
    if destination:
        if destination.startswith("https://") or destination.startswith("http://"):
            return destination.rstrip("/") + "/"
        return f"{SITE_BASE_URL}/{destination.lstrip('/').rstrip('/')}/"
    return f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/"


def build_commercial_title(topic):
    """Use a short conversion hook when one is supplied, otherwise keep the SEO title."""
    title = (
        topic.get("commercial_hook")
        or topic.get("pin_title")
        or topic.get("title")
        or "Rare Plant Buying Guide"
    )
    return str(title).strip()[:100]


def build_commercial_description(topic):
    """Keep Pinterest copy clear, commercial and aligned with the destination page."""
    base = (topic.get("pin_description") or "").strip().rstrip(" .")
    keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]

    parts = []
    if base:
        parts.append(base + ".")
    if keywords:
        parts.append("Compare options for " + ", ".join(keywords[:3]) + ".")
    parts.append("Open the buying guide to compare the recommended picks and choose the right setup.")
    return " ".join(parts)[:500].rstrip()


def add_commercial_cta(image_path, topic):
    """Replace the generic save CTA with a high-contrast lower-funnel CTA."""
    local_path = os.path.join("static", str(image_path).lstrip("/"))
    image = Image.open(local_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    cta = str(topic.get("commercial_cta") or "SEE THE PICKS >").upper()[:30]
    font_size = 34
    font = ImageFont.truetype(FONT_PATH, font_size)
    max_width = 760
    while font_size > 25 and draw.textlength(cta, font=font) > max_width:
        font_size -= 2
        font = ImageFont.truetype(FONT_PATH, font_size)

    x1, y1, x2, y2 = 72, 1260, 928, 1365
    draw.rounded_rectangle((x1, y1, x2, y2), radius=24, fill=(12, 12, 12))
    bbox = draw.textbbox((0, 0), cta, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = x1 + (x2 - x1 - text_w) // 2
    ty = y1 + (y2 - y1 - text_h) // 2 - bbox[1]
    draw.text((tx, ty), cta, font=font, fill=(255, 255, 255))

    image.save(local_path, "JPEG", quality=92, optimize=True)
    return image_path


def build_commercial_image(topic):
    """Create a single-image commercial Pin using the short hook and direct CTA."""
    creative_topic = dict(topic)
    creative_topic["title"] = build_commercial_title(topic)
    creative_topic["pin_title"] = build_commercial_title(topic)
    image_path = build_promo_image(creative_topic)
    return add_commercial_cta(image_path, topic)


def create_buying_pin(access_token, board_id, topic):
    """Create a commercial Pin that links to the queue's real buying-guide destination."""
    promo_topic = dict(topic)
    promo_topic["pin_title"] = topic["promo_pin_title"]
    payload = {
        "board_id": board_id,
        "media_source": build_image_media_source(topic["promo_pin_image_path"]),
        "link": destination_url(topic),
        "title": topic["promo_pin_title"][:100],
        "description": topic["promo_pin_description"][:500],
        "alt_text": build_alt_text(promo_topic),
    }
    response = requests.post(
        f"{PINTEREST_API_BASE}/pins",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def prepare(queue, today=None):
    # A previously prepared Pin must always finish, regardless of the cooldown.
    prepared = pick_topic(queue, {"prepared"})
    if prepared:
        if prepared.get("promo_pin_image_path"):
            print(f"Buying-guide Pin already prepared for '{prepared.get('title')}'.")
            return True
        topic = prepared
    else:
        if not commercial_slot_open(queue, today=today):
            print("Commercial Pin cooldown active; use the evergreen promo fallback.")
            return False
        topic = pick_topic(queue, {"pending"})

    if not topic:
        print("No buying-guide Pinterest Pin is pending.")
        return False

    topic["promo_pin_title"] = build_commercial_title(topic)
    topic["promo_pin_description"] = build_commercial_description(topic)
    topic["promo_pin_image_path"] = build_commercial_image(topic)
    topic["promo_pin_prepared_date"] = (today or datetime.date.today()).isoformat()
    topic["status"] = "prepared"
    save_queue(queue)
    print(f"Prepared buying-guide Pinterest creative for '{topic['promo_pin_title']}'.")
    return True


def publish(queue):
    topic = pick_topic(queue, {"prepared"})
    if not topic:
        print("No prepared buying-guide Pinterest Pin found.")
        return False

    app_id = os.environ.get("PINTEREST_APP_ID")
    app_secret = os.environ.get("PINTEREST_APP_SECRET")
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN")
    if not all([app_id, app_secret]):
        raise RuntimeError("Pinterest credentials are missing (PINTEREST_APP_ID / PINTEREST_APP_SECRET).")

    access_token, rotated_refresh_token = get_access_token(app_id, app_secret, refresh_token)
    save_rotated_refresh_token(rotated_refresh_token)

    board_name, board_description = COMMERCIAL_BOARD
    board_id = get_or_create_board(access_token, board_name, board_description)
    landing_url = destination_url(topic)

    existing = find_existing_promo_pin(access_token, landing_url, topic["promo_pin_title"])
    if existing:
        result = existing
        print(f"Buying-guide Pin already exists for '{topic['promo_pin_title']}'.")
    else:
        result = create_buying_pin(access_token, board_id, topic)
        print(
            f"Buying-guide Pinterest Pin published for '{topic['promo_pin_title']}' "
            f"to '{board_name}' (id: {result.get('id')}) -> {landing_url}"
        )

    topic["status"] = "posted"
    topic["pinterest_pin_id"] = result.get("id")
    topic["pinterest_board"] = board_name
    topic["published_pin_date"] = datetime.date.today().isoformat()
    save_queue(queue)
    return True


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    queue = load_queue()
    ok = prepare(queue) if args.prepare else publish(queue)
    if not ok:
        sys.exit(NO_CANDIDATE_EXIT)


if __name__ == "__main__":
    main()
