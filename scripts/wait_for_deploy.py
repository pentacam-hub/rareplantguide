"""Wait until pending Pinterest article and, when needed, creative assets are public."""

import argparse
import time

import requests

from scripts.post_pin import POST_URL_PREFIX, SITE_BASE_URL, load_queue, pick_pending_pins


def pending_urls(queue, kind="original", limit=1):
    if kind == "promo":
        topics = [
            topic
            for topic in queue.get("topics", [])
            if topic.get("status") == "done"
            and topic.get("promo_pin_status") == "pending"
            and topic.get("promo_pin_image_path")
        ][: max(0, limit)]
        image_key = "promo_pin_image_path"
    else:
        topics = pick_pending_pins(queue, max(0, limit))
        image_key = "pin_image_path"

    return [
        {
            "article": f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/",
            "image": f"{SITE_BASE_URL}{topic[image_key]}",
        }
        for topic in topics
    ]


def url_is_ready(url, expected_type):
    try:
        response = requests.get(url, timeout=20, stream=True)
        content_type = response.headers.get("Content-Type", "").lower()
        return response.status_code == 200 and expected_type in content_type
    except requests.RequestException:
        return False


def wait_for_urls(urls, timeout, interval, article_only=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        states = []
        all_ready = True
        for item in urls:
            article_ready = url_is_ready(item["article"], "text/html")
            image_ready = True if article_only else url_is_ready(item["image"], "image/")
            states.append((article_ready, image_ready))
            all_ready = all_ready and article_ready and image_ready
        if all_ready:
            return True
        state_text = ", ".join(
            f"#{index + 1}:articolo={article},immagine={image}"
            for index, (article, image) in enumerate(states)
        )
        print(f"Deploy non ancora pronto ({state_text}); nuovo controllo tra {interval}s.")
        time.sleep(interval)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--kind", choices=("original", "promo"), default="original")
    parser.add_argument("--max-pins", type=int, default=1)
    parser.add_argument("--article-only", action="store_true")
    args = parser.parse_args()

    urls = pending_urls(load_queue(), kind=args.kind, limit=max(1, args.max_pins))
    if not urls:
        print(f"Nessun Pin {args.kind} pending: controllo deploy non necessario.")
        return

    if not wait_for_urls(urls, args.timeout, args.interval, article_only=args.article_only):
        raise SystemExit(
            "Deploy non disponibile entro il timeout; Pinterest verrà ritentato al prossimo run."
        )
    print(f"Deploy pronto per {len(urls)} Pin {args.kind} pending.")


if __name__ == "__main__":
    main()
