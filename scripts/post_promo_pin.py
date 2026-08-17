"""Create and publish one fresh evergreen Pinterest Pin for an older article.

The normal content workflow publishes one new article and its original Pin per day.
This script supplies the second daily Pin without creating a second article.

Usage:
    python scripts/post_promo_pin.py --prepare
    python scripts/post_promo_pin.py --publish

--prepare creates a visually distinct 1000x1500 image for an older article and
marks it pending in content-queue.yaml. The workflow commits it and waits for the
site deployment. --publish then sends that deployed image to Pinterest.
"""

import argparse
import datetime
import os
import textwrap

import requests
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from scripts.post_pin import (
    PINTEREST_API_BASE,
    POST_URL_PREFIX,
    QUEUE_PATH,
    SITE_BASE_URL,
    build_alt_text,
    canonical_link,
    get_access_token,
    get_board_config,
    get_or_create_board,
    save_rotated_refresh_token,
)

PINS_DIR = "static/images/pins"
IMAGES_DIR = "static/images"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PROMO_MIN_AGE_DAYS = 3


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def pick_pending_promo(queue):
    for topic in queue.get("topics", []):
        if topic.get("status") == "done" and topic.get("promo_pin_status") == "pending":
            return topic
    return None


def pick_promo_candidate(queue, today=None):
    """Pick the oldest article eligible for one additional fresh Pin."""
    pending = pick_pending_promo(queue)
    if pending:
        return pending

    today = today or datetime.date.today()
    candidates = []
    for topic in queue.get("topics", []):
        published = parse_date(topic.get("published_date"))
        original_posted = topic.get("pin_status") in {"posted", "posted_manual"}
        promo_done = topic.get("promo_pin_status") in {"pending", "posted"}
        if not (
            topic.get("status") == "done"
            and topic.get("slug")
            and published
            and original_posted
            and not promo_done
        ):
            continue
        if (today - published).days < PROMO_MIN_AGE_DAYS:
            continue
        candidates.append((published, topic))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_promo_title(topic):
    """Use the editorial queue title as a distinct search-friendly Pin title."""
    title = (topic.get("title") or topic.get("pin_title") or "Rare Plant Care Guide").strip()
    return title[:100]


def build_promo_description(topic):
    base = (topic.get("pin_description") or "").strip().rstrip(" .")
    keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]
    primary = keywords[0] if keywords else "rare plant care"

    parts = [f"Save this practical {primary} guide for later."]
    if base:
        parts.append(base + ".")
    if len(keywords) > 1:
        parts.append("Also covers " + ", ".join(keywords[1:3]) + ".")
    parts.append("Open the full guide for the step-by-step details.")
    return " ".join(parts)[:500].rstrip()


def wrap_lines(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_vertical_background(source_path, width=1000, height=1500):
    if os.path.exists(source_path):
        base = Image.open(source_path).convert("RGB")
        src_ratio = base.width / base.height
        target_ratio = width / height
        if src_ratio > target_ratio:
            crop_width = int(base.height * target_ratio)
            left = (base.width - crop_width) // 2
            base = base.crop((left, 0, left + crop_width, base.height))
        else:
            crop_height = int(base.width / target_ratio)
            top = (base.height - crop_height) // 2
            base = base.crop((0, top, base.width, top + crop_height))
        base = base.resize((width, height))
        return ImageEnhance.Brightness(base).enhance(0.78)
    return Image.new("RGB", (width, height), (40, 67, 48))


def build_promo_image(topic):
    """Create a second, visually distinct creative from the article cover."""
    width, height = 1000, 1500
    slug = topic["slug"]
    cover_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")
    base = make_vertical_background(cover_path, width, height).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Distinct top editorial card instead of the original Pin's lower gradient layout.
    draw.rounded_rectangle((55, 85, 945, 790), radius=42, fill=(255, 255, 255, 235))

    keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]
    kicker = (keywords[0] if keywords else "RARE PLANT GUIDE").upper()[:42]
    kicker_font = ImageFont.truetype(FONT_PATH, 30)
    draw.text((105, 145), kicker, font=kicker_font, fill=(45, 88, 58, 255))

    title = build_promo_title(topic)
    title_size = 64
    max_width = 790
    while title_size >= 42:
        title_font = ImageFont.truetype(FONT_PATH, title_size)
        lines = wrap_lines(draw, title, title_font, max_width)
        if len(lines) <= 5:
            break
        title_size -= 4

    y = 225
    line_height = int(title_size * 1.22)
    for line in lines[:5]:
        draw.text((105, y), line, font=title_font, fill=(25, 35, 28, 255))
        y += line_height

    cta_font = ImageFont.truetype(FONT_PATH, 32)
    draw.text((105, 690), "SAVE THIS GUIDE", font=cta_font, fill=(45, 88, 58, 255))

    footer = Image.new("RGBA", (width, 105), (20, 38, 26, 225))
    overlay.alpha_composite(footer, (0, height - 105))
    brand_font = ImageFont.truetype(FONT_PATH, 30)
    draw.text((65, height - 72), "TheRarePlantGuide.com", font=brand_font, fill=(255, 255, 255, 245))

    final = Image.alpha_composite(base, overlay).convert("RGB")
    os.makedirs(PINS_DIR, exist_ok=True)
    filename = f"{slug}-save-guide.jpg"
    local_path = os.path.join(PINS_DIR, filename)
    final.save(local_path, "JPEG", quality=91)
    return f"/images/pins/{filename}"


def prepare(queue):
    topic = pick_promo_candidate(queue)
    if not topic:
        print("No article is currently eligible for an evergreen Pinterest Pin.")
        return False

    if topic.get("promo_pin_status") == "pending" and topic.get("promo_pin_image_path"):
        print(f"Promo Pin already pending for '{topic.get('title')}'.")
        return False

    topic["promo_pin_title"] = build_promo_title(topic)
    topic["promo_pin_description"] = build_promo_description(topic)
    topic["promo_pin_image_path"] = build_promo_image(topic)
    topic["promo_pin_status"] = "pending"
    topic["promo_pin_prepared_date"] = datetime.date.today().isoformat()
    save_queue(queue)
    print(f"Prepared evergreen Pinterest creative for '{topic['promo_pin_title']}'.")
    return True


def find_existing_promo_pin(access_token, article_url, promo_title, max_pages=5):
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
            if (
                canonical_link(pin.get("link", "")) == target
                and (pin.get("title") or "").strip() == promo_title.strip()
            ):
                return pin
        bookmark = payload.get("bookmark")
        if not bookmark:
            break
    return None


def create_promo_pin(access_token, board_id, topic):
    slug = topic["slug"]
    article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{slug}/"
    image_url = f"{SITE_BASE_URL}{topic['promo_pin_image_path']}"
    promo_topic = dict(topic)
    promo_topic["pin_title"] = topic["promo_pin_title"]

    payload = {
        "board_id": board_id,
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": article_url,
        "title": topic["promo_pin_title"][:100],
        "description": topic["promo_pin_description"][:500],
        "alt_text": build_alt_text(promo_topic),
    }
    resp = requests.post(
        f"{PINTEREST_API_BASE}/pins",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def publish(queue):
    topic = pick_pending_promo(queue)
    if not topic:
        print("No pending evergreen Pinterest Pin found.")
        return False

    app_id = os.environ.get("PINTEREST_APP_ID")
    app_secret = os.environ.get("PINTEREST_APP_SECRET")
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN")
    if not all([app_id, app_secret, refresh_token]):
        raise RuntimeError("Pinterest credentials are missing.")

    access_token, rotated_refresh_token = get_access_token(app_id, app_secret, refresh_token)
    save_rotated_refresh_token(rotated_refresh_token)

    board_name, board_description = get_board_config(topic)
    board_id = get_or_create_board(access_token, board_name, board_description)
    article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/"

    existing = find_existing_promo_pin(access_token, article_url, topic["promo_pin_title"])
    if existing:
        result = existing
        print(f"Evergreen Pin already exists for '{topic['promo_pin_title']}'.")
    else:
        result = create_promo_pin(access_token, board_id, topic)
        print(
            f"Evergreen Pinterest Pin published for '{topic['promo_pin_title']}' "
            f"to '{board_name}' (id: {result.get('id')})."
        )

    topic["promo_pin_status"] = "posted"
    topic["promo_pinterest_pin_id"] = result.get("id")
    topic["promo_pinterest_board"] = board_name
    topic["promo_pin_published_date"] = datetime.date.today().isoformat()
    save_queue(queue)
    return True


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    queue = load_queue()
    if args.prepare:
        prepare(queue)
    else:
        publish(queue)


if __name__ == "__main__":
    main()
