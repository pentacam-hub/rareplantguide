"""Prepare and publish one Pinterest Pin from the dedicated buying-guide queue."""

import argparse
import datetime
import os
import sys

import yaml
from PIL import Image, ImageDraw, ImageFont

from scripts.post_pin import (
    POST_URL_PREFIX,
    SITE_BASE_URL,
    get_access_token,
    get_board_config,
    get_or_create_board,
    save_rotated_refresh_token,
)
from scripts.post_promo_pin import (
    FONT_PATH,
    build_promo_description,
    build_promo_image,
    create_promo_pin,
    find_existing_promo_pin,
)

QUEUE_PATH = "promo-buying-guides.yaml"
NO_CANDIDATE_EXIT = 3


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"topics": []}


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def pick_topic(queue, statuses):
    for topic in queue.get("topics", []):
        if topic.get("status") in statuses:
            return topic
    return None


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
    parts.append("Open the guide to see the recommended picks and choose the right setup.")
    return " ".join(parts)[:500].rstrip()


def add_commercial_cta(image_path, topic):
    """Replace the generic save CTA with a high-contrast lower-funnel CTA.

    Commercial Pin standard:
    - one image-led 2:3 creative (created by build_promo_image)
    - short bold hook
    - high contrast
    - direct CTA at the bottom
    - arrow cue when configured
    """
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

    # Cover the generic CTA with a clean, dark, high-contrast lower CTA block.
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


def prepare(queue):
    topic = pick_topic(queue, {"prepared", "pending"})
    if not topic:
        print("No buying-guide Pinterest Pin is pending.")
        return False

    if topic.get("status") == "prepared" and topic.get("promo_pin_image_path"):
        print(f"Buying-guide Pin already prepared for '{topic.get('title')}'.")
        return True

    topic["promo_pin_title"] = build_commercial_title(topic)
    topic["promo_pin_description"] = build_commercial_description(topic)
    topic["promo_pin_image_path"] = build_commercial_image(topic)
    topic["promo_pin_prepared_date"] = datetime.date.today().isoformat()
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

    board_name, board_description = get_board_config(topic)
    board_id = get_or_create_board(access_token, board_name, board_description)
    article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/"

    existing = find_existing_promo_pin(access_token, article_url, topic["promo_pin_title"])
    if existing:
        result = existing
        print(f"Buying-guide Pin already exists for '{topic['promo_pin_title']}'.")
    else:
        result = create_promo_pin(access_token, board_id, topic)
        print(
            f"Buying-guide Pinterest Pin published for '{topic['promo_pin_title']}' "
            f"to '{board_name}' (id: {result.get('id')})."
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
