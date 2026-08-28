"""Prepare and publish one Pinterest Pin from the dedicated buying-guide queue."""

import argparse
import datetime
import os
import sys

import yaml

from scripts.post_pin import (
    POST_URL_PREFIX,
    SITE_BASE_URL,
    get_access_token,
    get_board_config,
    get_or_create_board,
    save_rotated_refresh_token,
)
from scripts.post_promo_pin import (
    build_promo_description,
    build_promo_image,
    build_promo_title,
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


def prepare(queue):
    topic = pick_topic(queue, {"prepared", "pending"})
    if not topic:
        print("No buying-guide Pinterest Pin is pending.")
        return False

    if topic.get("status") == "prepared" and topic.get("promo_pin_image_path"):
        print(f"Buying-guide Pin already prepared for '{topic.get('title')}'.")
        return True

    topic["promo_pin_title"] = build_promo_title(topic)
    topic["promo_pin_description"] = build_promo_description(topic)
    topic["promo_pin_image_path"] = build_promo_image(topic)
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
