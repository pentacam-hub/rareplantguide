"""Wait until the pending article and Pin image are publicly available."""

import argparse
import time

import requests

from scripts.post_pin import POST_URL_PREFIX, SITE_BASE_URL, load_queue, pick_pending_pin


def pending_urls(queue):
    topic = pick_pending_pin(queue)
    if not topic:
        return None
    return {
        "article": f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/",
        "image": f"{SITE_BASE_URL}{topic['pin_image_path']}",
    }


def url_is_ready(url, expected_type):
    try:
        response = requests.get(url, timeout=20, stream=True)
        content_type = response.headers.get("Content-Type", "").lower()
        return response.status_code == 200 and expected_type in content_type
    except requests.RequestException:
        return False


def wait_for_urls(urls, timeout, interval):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        article_ready = url_is_ready(urls["article"], "text/html")
        image_ready = url_is_ready(urls["image"], "image/")
        if article_ready and image_ready:
            return True
        print(
            "Deploy non ancora pronto "
            f"(articolo={article_ready}, immagine={image_ready}); nuovo controllo tra {interval}s."
        )
        time.sleep(interval)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    urls = pending_urls(load_queue())
    if not urls:
        print("Nessun Pin pending: controllo deploy non necessario.")
        return

    if not wait_for_urls(urls, args.timeout, args.interval):
        raise SystemExit(
            "Deploy non disponibile entro il timeout; Pinterest verrà ritentato al prossimo run."
        )
    print(f"Deploy pronto: {urls['article']} e {urls['image']}")


if __name__ == "__main__":
    main()
