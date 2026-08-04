"""
Genera automaticamente un nuovo articolo (testo + immagine di copertina)
per The Rare Plant Guide.

Pesca il prossimo topic "pending" da content-queue.yaml, chiama l'API
gratuita di Google Gemini per scrivere il post in tono personale,
scarica una foto di copertina gratuita da Unsplash, e salva tutto
pronto per Hugo (tema PaperMod).

Variabili d'ambiente richieste:
    GEMINI_API_KEY      -> chiave gratuita da https://aistudio.google.com/app/apikey
    UNSPLASH_ACCESS_KEY -> chiave gratuita da https://unsplash.com/developers
"""

import os
import sys
import json
import datetime
import requests
import yaml
from slugify import slugify
import google.generativeai as genai

QUEUE_PATH = "content-queue.yaml"
POSTS_DIR = "content/posts"          # <-- adatta se la tua struttura Hugo usa un'altra cartella
IMAGES_DIR = "static/images"         # le immagini scaricate vanno qui, come le altre già presenti
MODEL_NAME = "gemini-2.0-flash-exp"  # modello gratuito


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_queue(data):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def pick_topic(queue):
    for item in queue.get("topics", []):
        if item.get("status") == "pending":
            return item
    return None


def build_prompt(topic):
    keywords = ", ".join(topic.get("keywords", []))
    return f"""You are the writer behind "The Rare Plant Guide", an English-language blog
about caring for rare and variegated houseplants, written by an experienced hobbyist grower.

Write a full blog post on this topic: "{topic['title']}"
Keywords to weave in naturally (do not force them, do not list them): {keywords}

Style and requirements:
- First person, warm, personal, conversational tone — like a real grower talking to a friend
- Include one short, specific personal anecdote about a mistake you made with this exact
  problem and what you learned from it (invent something plausible and concrete, not generic)
- Include a paragraph summarizing tips that plant community forums and fellow growers
  commonly share about this topic — described in general terms, not attributed to any
  specific named person or platform
- Structure the body with clear H2 (##) markdown subheadings, practical and actionable content
- Length: 900-1300 words
- End with a short, encouraging takeaway
- Do not fabricate scientific claims; keep care advice realistic and safe for the plants involved

Respond ONLY with a JSON object (no markdown fences, no commentary) with exactly these fields:
{{
  "title": "<a natural, click-worthy title, can refine the one given above>",
  "description": "<one-sentence SEO description, under 155 characters>",
  "tags": ["<2 to 4 relevant tags>"],
  "body_markdown": "<the full article body in markdown, starting directly with the first paragraph, no title heading inside it>"
}}
"""


def generate_article(model, topic):
    prompt = build_prompt(topic)
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    data = json.loads(response.text)
    required = ["title", "description", "tags", "body_markdown"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Risposta del modello incompleta, mancano i campi: {missing}")
    return data


def fetch_cover_image(query, slug, unsplash_key):
    """Cerca e scarica una foto gratuita da Unsplash. Ritorna un dict con
    path locale, alt text e dati di attribuzione, oppure None se fallisce."""
    try:
        search = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {unsplash_key}"},
            timeout=20,
        )
        search.raise_for_status()
        results = search.json().get("results", [])
        if not results:
            print(f"Nessuna immagine trovata su Unsplash per '{query}'.")
            return None

        photo = results[0]
        image_url = photo["urls"]["regular"]
        photographer_name = photo["user"]["name"]
        photographer_link = photo["user"]["links"]["html"]
        download_location = photo["links"]["download_location"]

        # Requisito delle linee guida API di Unsplash: notificare il download
        requests.get(
            download_location,
            headers={"Authorization": f"Client-ID {unsplash_key}"},
            timeout=20,
        )

        img_data = requests.get(image_url, timeout=30)
        img_data.raise_for_status()

        os.makedirs(IMAGES_DIR, exist_ok=True)
        image_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")
        with open(image_path, "wb") as f:
            f.write(img_data.content)

        return {
            "local_path": f"/images/{slug}.jpg",
            "alt": query,
            "photographer_name": photographer_name,
            "photographer_link": photographer_link,
        }
    except Exception as e:
        print(f"Attenzione: download immagine fallito ({e}). Il post verrà creato senza cover.")
        return None


def build_markdown_file(article, cover, today):
    tags_yaml = json.dumps(article["tags"], ensure_ascii=False)

    front_matter_lines = [
        "---",
        f'title: "{article["title"]}"',
        f"date: {today}",
        "draft: false",
        f'description: "{article["description"]}"',
        f"tags: {tags_yaml}",
        'categories: ["Plant Care"]',
    ]

    body = article["body_markdown"].strip()

    if cover:
        front_matter_lines += [
            "cover:",
            f'    image: "{cover["local_path"]}"',
            f'    alt: "{cover["alt"]}"',
            "    relative: false",
        ]
        attribution = (
            f'\n\n*Cover photo by [{cover["photographer_name"]}]'
            f'({cover["photographer_link"]}?utm_source=rareplantguide&utm_medium=referral) '
            f'on [Unsplash](https://unsplash.com/?utm_source=rareplantguide&utm_medium=referral).*'
        )
        body += attribution

    front_matter_lines.append("---")
    return "\n".join(front_matter_lines) + "\n\n" + body + "\n"


def main():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY")

    if not gemini_key:
        print("Errore: variabile d'ambiente GEMINI_API_KEY mancante.")
        sys.exit(1)
    if not unsplash_key:
        print("Attenzione: UNSPLASH_ACCESS_KEY mancante, il post verrà creato senza immagine.")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel(MODEL_NAME)

    queue = load_queue()
    topic = pick_topic(queue)
    if not topic:
        print("Nessun topic 'pending' in coda. Aggiungi nuovi argomenti a content-queue.yaml.")
        sys.exit(0)

    article = generate_article(model, topic)

    slug = slugify(article["title"])
    today = datetime.date.today().isoformat()

    cover = None
    if unsplash_key:
        image_query = topic.get("image_query", topic["title"])
        cover = fetch_cover_image(image_query, slug, unsplash_key)

    content = build_markdown_file(article, cover, today)

    os.makedirs(POSTS_DIR, exist_ok=True)
    filepath = os.path.join(POSTS_DIR, f"{slug}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    topic["status"] = "done"
    topic["published_date"] = today
    save_queue(queue)

    print(f"Articolo generato con successo: {filepath}")
    if cover:
        print(f"Immagine di copertina salvata in: {IMAGES_DIR}/{slug}.jpg")


if __name__ == "__main__":
    main()
