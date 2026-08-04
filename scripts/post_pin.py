"""
Pubblica su Pinterest i pin già generati (immagine + testo) che risultano
ancora "pending" in content-queue.yaml.

Va lanciato DOPO che generate_post.py ha fatto commit+push e dopo che
Cloudflare Pages ha finito di ripubblicare il sito, altrimenti Pinterest
non riuscirà a scaricare l'immagine dal dominio live.

Variabili d'ambiente richieste:
    PINTEREST_APP_ID       -> "App ID" della tua app su developers.pinterest.com
    PINTEREST_APP_SECRET   -> "App secret" della stessa app
    PINTEREST_REFRESH_TOKEN -> ottenuto una tantum con l'autorizzazione manuale
                               (vedi SETUP.md, sezione Pinterest)
"""

import os
import sys
import base64
import yaml
import requests

QUEUE_PATH = "content-queue.yaml"
SITE_BASE_URL = "https://therareplantguide.com"  # <-- verifica corrisponda al tuo dominio live
POST_URL_PREFIX = "/posts"                        # <-- verifica il permalink dei post in hugo.toml
DEFAULT_BOARD_NAME = "Rare Plant Care Tips"        # board di destinazione dei pin
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


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
    return resp.json()["access_token"]


def get_or_create_board(access_token, board_name):
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = requests.get(f"{PINTEREST_API_BASE}/boards", headers=headers, params={"page_size": 100}, timeout=20)
    resp.raise_for_status()
    for board in resp.json().get("items", []):
        if board["name"].strip().lower() == board_name.strip().lower():
            return board["id"]

    create_resp = requests.post(
        f"{PINTEREST_API_BASE}/boards",
        headers=headers,
        json={"name": board_name, "description": f"Auto-managed board for {SITE_BASE_URL}"},
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
        "description": topic["pin_description"][:500],
    }
    resp = requests.post(f"{PINTEREST_API_BASE}/pins", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    app_id = os.environ.get("PINTEREST_APP_ID")
    app_secret = os.environ.get("PINTEREST_APP_SECRET")
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN")

    if not all([app_id, app_secret, refresh_token]):
        print("Credenziali Pinterest mancanti (PINTEREST_APP_ID / PINTEREST_APP_SECRET / PINTEREST_REFRESH_TOKEN). Salto la pubblicazione del pin.")
        sys.exit(0)

    queue = load_queue()
    pending_pins = [t for t in queue.get("topics", []) if t.get("pin_status") == "pending"]

    if not pending_pins:
        print("Nessun pin in attesa di pubblicazione.")
        sys.exit(0)

    access_token = get_access_token(app_id, app_secret, refresh_token)
    board_id = get_or_create_board(access_token, DEFAULT_BOARD_NAME)

    for topic in pending_pins:
        try:
            result = create_pin(access_token, board_id, topic)
            topic["pin_status"] = "posted"
            topic["pinterest_pin_id"] = result.get("id")
            print(f"Pin pubblicato per '{topic['pin_title']}' (id: {result.get('id')})")
        except Exception as e:
            print(f"Attenzione: pubblicazione pin fallita per '{topic.get('pin_title')}': {e}")
            # lascia pin_status a "pending", verrà ritentato alla prossima esecuzione

    save_queue(queue)


if __name__ == "__main__":
    main()
