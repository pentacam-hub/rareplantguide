"""Publish Analyze My Income Pinterest Pins from ami-pinterest-queue.yaml.

This automation intentionally uses an OAuth refresh token tied to the Analyze My
Income Pinterest account. It does not fall back to client_credentials, because a
client-credentials token acts for the Pinterest app owner and could publish to the
wrong brand account when the app is owned elsewhere.
"""

import base64
import datetime
import os
import textwrap
from urllib.parse import urlsplit, urlunsplit

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

QUEUE_PATH = "ami-pinterest-queue.yaml"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_SCOPES = "boards:read,boards:write,pins:read,pins:write"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def load_queue(path=QUEUE_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_queue(data, path=QUEUE_PATH):
    data["updated"] = datetime.date.today().isoformat()
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=120)


def pick_pending_pin(queue):
    for pin in queue.get("pins", []):
        if pin.get("status") == "pending":
            return pin
    return None


def canonical_link(url):
    if not url:
        return ""
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _basic_auth_header(app_id, app_secret):
    encoded = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def get_access_token(app_id, app_secret, refresh_token):
    if not refresh_token:
        raise RuntimeError("AMI_PINTEREST_REFRESH_TOKEN is required for the Analyze My Income account.")

    response = requests.post(
        f"{PINTEREST_API_BASE}/oauth/token",
        headers=_basic_auth_header(app_id, app_secret),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": PINTEREST_SCOPES,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["access_token"], payload.get("refresh_token")


def save_rotated_refresh_token(refresh_token):
    token_path = os.environ.get("AMI_PINTEREST_REFRESH_TOKEN_FILE")
    if not refresh_token or not token_path:
        return
    fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(refresh_token)


def list_boards(access_token, max_pages=5):
    headers = {"Authorization": f"Bearer {access_token}"}
    bookmark = None
    boards = []
    for _ in range(max_pages):
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        response = requests.get(
            f"{PINTEREST_API_BASE}/boards",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        boards.extend(payload.get("items", []))
        bookmark = payload.get("bookmark")
        if not bookmark:
            break
    return boards


def get_or_create_board(access_token, board_name, board_description):
    for board in list_boards(access_token):
        if (board.get("name") or "").strip().lower() == board_name.strip().lower():
            return board["id"]

    response = requests.post(
        f"{PINTEREST_API_BASE}/boards",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"name": board_name, "description": board_description[:500]},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["id"]


def find_existing_pin(access_token, destination, title, max_pages=5):
    headers = {"Authorization": f"Bearer {access_token}"}
    bookmark = None
    target = canonical_link(destination)
    for _ in range(max_pages):
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        response = requests.get(
            f"{PINTEREST_API_BASE}/pins",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        for existing in payload.get("items", []):
            if (
                canonical_link(existing.get("link", "")) == target
                and (existing.get("title") or "").strip() == title.strip()
            ):
                return existing
        bookmark = payload.get("bookmark")
        if not bookmark:
            break
    return None


def wrap_text(draw, text, font, max_width):
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


def build_pin_image(pin):
    width, height = 1000, 1500
    image = Image.new("RGB", (width, height), (247, 249, 252))
    draw = ImageDraw.Draw(image)

    # Analyze My Income visual system: dark decision panel + green signal accent.
    draw.rounded_rectangle((55, 55, 945, 1445), radius=44, fill=(16, 32, 51))
    draw.rounded_rectangle((85, 100, 915, 260), radius=30, fill=(236, 253, 245))
    draw.rectangle((85, 1310, 915, 1322), fill=(16, 185, 129))

    kicker_font = ImageFont.truetype(FONT_BOLD, 38)
    brand_font = ImageFont.truetype(FONT_BOLD, 31)
    small_font = ImageFont.truetype(FONT_REGULAR, 29)

    kicker = str(pin.get("kicker") or "ANALYZE MY INCOME").upper()[:42]
    draw.text((125, 155), kicker, font=kicker_font, fill=(4, 120, 87))

    title = str(pin.get("graphic_title") or pin.get("title") or "Know Your Numbers")
    title_size = 78
    max_width = 760
    while title_size >= 48:
        title_font = ImageFont.truetype(FONT_BOLD, title_size)
        lines = wrap_text(draw, title, title_font, max_width)
        if len(lines) <= 5:
            break
        title_size -= 4

    y = 365
    line_height = int(title_size * 1.22)
    for line in lines[:5]:
        draw.text((120, y), line, font=title_font, fill=(255, 255, 255))
        y += line_height

    # Lightweight calculator motif without inventing a numeric result.
    card_top = 930
    draw.rounded_rectangle((120, card_top, 880, card_top + 270), radius=30, fill=(255, 255, 255))
    draw.text((165, card_top + 42), "FREE 2026 CALCULATOR", font=brand_font, fill=(16, 32, 51))
    draw.text((165, card_top + 105), "Clear inputs → clear estimate", font=small_font, fill=(71, 85, 105))
    draw.rounded_rectangle((165, card_top + 180, 520, card_top + 230), radius=22, fill=(16, 185, 129))
    cta_font = ImageFont.truetype(FONT_BOLD, 25)
    draw.text((204, card_top + 192), "CHECK YOUR NUMBERS", font=cta_font, fill=(255, 255, 255))

    draw.text((120, 1360), "AnalyzeMyIncome.com", font=brand_font, fill=(255, 255, 255))

    output_path = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), f"{pin['id']}.jpg")
    image.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


def build_media_source(image_path):
    with open(image_path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return {
        "source_type": "image_base64",
        "content_type": "image/jpeg",
        "data": encoded,
        "is_standard": True,
    }


def build_alt_text(pin):
    return f"{pin.get('kicker', '')}. {pin.get('graphic_title', pin.get('title', ''))}. Analyze My Income calculator graphic."[:500]


def create_pin(access_token, board_id, pin, image_path):
    payload = {
        "board_id": board_id,
        "media_source": build_media_source(image_path),
        "link": pin["destination"],
        "title": pin["title"][:100],
        "description": pin["description"][:800],
        "alt_text": build_alt_text(pin),
    }
    response = requests.post(
        f"{PINTEREST_API_BASE}/pins",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def publish_next(queue_path=QUEUE_PATH):
    queue = load_queue(queue_path)
    pin = pick_pending_pin(queue)
    if not pin:
        print("Analyze My Income Pinterest queue is empty.")
        return False

    app_id = os.environ.get("AMI_PINTEREST_APP_ID")
    app_secret = os.environ.get("AMI_PINTEREST_APP_SECRET")
    refresh_token = os.environ.get("AMI_PINTEREST_REFRESH_TOKEN")
    if not app_id or not app_secret or not refresh_token:
        raise RuntimeError(
            "Missing AMI Pinterest credentials: AMI_PINTEREST_APP_ID, "
            "AMI_PINTEREST_APP_SECRET, AMI_PINTEREST_REFRESH_TOKEN"
        )

    access_token, rotated_refresh_token = get_access_token(app_id, app_secret, refresh_token)
    save_rotated_refresh_token(rotated_refresh_token)

    board_id = get_or_create_board(
        access_token,
        pin["board"],
        pin.get("board_description") or "Analyze My Income calculators and money planning tools.",
    )

    existing = find_existing_pin(access_token, pin["destination"], pin["title"])
    if existing:
        result = existing
        print(f"Pin already exists: {pin['id']} / {pin['title']}")
    else:
        image_path = build_pin_image(pin)
        result = create_pin(access_token, board_id, pin, image_path)
        print(f"Published {pin['id']} to '{pin['board']}' (Pinterest id {result.get('id')}).")

    pin["status"] = "posted"
    pin["pinterest_pin_id"] = result.get("id")
    pin["published_date"] = datetime.date.today().isoformat()
    save_queue(queue, queue_path)
    return True


if __name__ == "__main__":
    publish_next()
