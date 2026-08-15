"""
Pubblica su Pinterest al massimo un Pin già generato (immagine + testo)
che risulta ancora "pending" in content-queue.yaml.

Va lanciato DOPO che generate_post.py ha fatto commit+push e dopo che
Cloudflare Pages ha finito di ripubblicare il sito, altrimenti Pinterest
non riuscirà a scaricare l'immagine dal dominio live.

Variabili d'ambiente richieste:
    PINTEREST_APP_ID       -> "App ID" della tua app su developers.pinterest.com
    PINTEREST_APP_SECRET   -> "App secret" della stessa app
    PINTEREST_REFRESH_TOKEN      -> ottenuto con l'autorizzazione manuale
    PINTEREST_REFRESH_TOKEN_FILE -> file temporaneo in cui salvare il nuovo
                                    continuous refresh token restituito dall'API
"""

import base64
import os
import sys
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


def pick_pending_pin(queue):
    """Return the oldest pending Pin so a run never publishes more than one."""
    for topic in queue.get("topics", []):
        if topic.get("status") == "done" and topic.get("pin_status") == "pending":
            return topic
    return None


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


def find_existing_pin(access_token, article_url, max_pages=5):
    """Prevent a retry from duplicating a Pin if the previous response was lost."""
    headers = {"Authorization": f"Bearer {access_token}"}
    bookmark = None
    for _ in range(max_pages):
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        resp = requests.get(f"{PINTEREST_API_BASE}/pins", headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        for pin in payload.get("items", []):
            if pin.get("link", "").rstrip("/") == article_url.rstrip("/"):
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
        print("Credenziali Pinterest mancanti (PINTEREST_APP_ID / PINTEREST_APP_SECRET / PINTEREST_REFRESH_TOKEN). Salto la pubblicazione del pin.")
        sys.exit(0)

    queue = load_queue()
    topic = pick_pending_pin(queue)
    if not topic:
        print("Nessun pin in attesa di pubblicazione.")
        sys.exit(0)

    access_token, rotated_refresh_token = get_access_token(app_id, app_secret, refresh_token)
    save_rotated_refresh_token(rotated_refresh_token)
    board_id = get_or_create_board(access_token, DEFAULT_BOARD_NAME)

    try:
        article_url = f"{SITE_BASE_URL}{POST_URL_PREFIX}/{topic['slug']}/"
        existing_pin = find_existing_pin(access_token, article_url)
        if existing_pin:
            result = existing_pin
            print(f"Pin già presente per '{topic['pin_title']}', aggiorno solo lo stato locale.")
        else:
            result = create_pin(access_token, board_id, topic)
            print(f"Pin pubblicato per '{topic['pin_title']}' (id: {result.get('id')})")
        topic["pin_status"] = "posted"
        topic["pinterest_pin_id"] = result.get("id")
    except Exception as e:
        print(f"Errore: pubblicazione Pin fallita per '{topic.get('pin_title')}': {e}")
        # Lo stato resta pending: il prossimo run ritenta senza generare un nuovo articolo.
        raise

    save_queue(queue)


if __name__ == "__main__":
    main()
