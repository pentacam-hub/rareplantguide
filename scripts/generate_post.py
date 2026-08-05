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
import textwrap
import datetime
import requests
import yaml
from slugify import slugify
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import google.generativeai as genai

QUEUE_PATH = "content-queue.yaml"
POSTS_DIR = "content/posts"          # <-- adatta se la tua struttura Hugo usa un'altra cartella
IMAGES_DIR = "static/images"         # le immagini scaricate vanno qui, come le altre già presenti
PINS_DIR = "static/images/pins"      # immagini verticali 1000x1500 pronte per Pinterest
MODEL_NAME = "gemini-3.5-flash"      # modello gratuito e attuale (verificare periodicamente su ai.google.dev/gemini-api/docs/models se cambia)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # presente di default sui runner ubuntu-latest


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


TITLE_MARK = "===TITLE==="
DESCRIPTION_MARK = "===DESCRIPTION==="
TAGS_MARK = "===TAGS==="
BODY_MARK = "===BODY==="


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

Respond in EXACTLY this plain text format, nothing before or after, no markdown code fences
around the whole response, using these exact section markers on their own line:

{TITLE_MARK}
<a natural, click-worthy title, one line, no quotes around it>
{DESCRIPTION_MARK}
<one-sentence SEO description, under 155 characters, one line>
{TAGS_MARK}
<2 to 4 relevant tags, comma-separated, one line>
{BODY_MARK}
<the full article body in markdown, starting directly with the first paragraph, no title heading inside it>
"""


def parse_article_response(text):
    def extract(start_mark, end_mark):
        start = text.index(start_mark) + len(start_mark)
        end = text.index(end_mark) if end_mark else len(text)
        return text[start:end].strip()

    title = extract(TITLE_MARK, DESCRIPTION_MARK)
    description = extract(DESCRIPTION_MARK, TAGS_MARK)
    tags_line = extract(TAGS_MARK, BODY_MARK)
    tags = [t.strip() for t in tags_line.split(",") if t.strip()]
    body_markdown = extract(BODY_MARK, None)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "body_markdown": body_markdown,
    }


def generate_article(model, topic):
    prompt = build_prompt(topic)
    response = model.generate_content(prompt)
    try:
        return parse_article_response(response.text)
    except ValueError as e:
        raise ValueError(f"Impossibile analizzare la risposta del modello: {e}\n\nRisposta grezza:\n{response.text[:2000]}")


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


def build_markdown_file(article, cover, today, weight=None):
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

    if weight is not None:
        front_matter_lines.append(f"weight: {weight}")

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


def wrap_title(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_pin_image(title, slug, cover_local_path):
    """Crea un'immagine verticale 1000x1500 con il titolo in overlay,
    pronta per essere pubblicata su Pinterest. Usa la cover come sfondo
    se disponibile, altrimenti un gradiente verde neutro."""
    W, H = 1000, 1500

    if cover_local_path and os.path.exists(cover_local_path.lstrip("/")):
        base = Image.open(cover_local_path.lstrip("/")).convert("RGB")
        # crop centrale per riempire 1000x1500 senza deformare
        src_ratio = base.width / base.height
        target_ratio = W / H
        if src_ratio > target_ratio:
            new_width = int(base.height * target_ratio)
            left = (base.width - new_width) // 2
            base = base.crop((left, 0, left + new_width, base.height))
        else:
            new_height = int(base.width / target_ratio)
            top = (base.height - new_height) // 2
            base = base.crop((0, top, base.width, top + new_height))
        base = base.resize((W, H))
        base = ImageEnhance.Brightness(base).enhance(0.75)
    else:
        base = Image.new("RGB", (W, H), (36, 66, 46))  # verde scuro neutro

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # gradiente scuro nella metà inferiore, per leggibilità del testo
    gradient_height = int(H * 0.55)
    for y in range(gradient_height):
        alpha = int(200 * (y / gradient_height))
        draw.line([(0, H - gradient_height + y), (W, H - gradient_height + y)], fill=(0, 0, 0, alpha))

    title_font_size = 68
    title_font = ImageFont.truetype(FONT_PATH, title_font_size)
    max_text_width = W - 120
    lines = wrap_title(draw, title, title_font, max_text_width)
    while len(lines) > 4 and title_font_size > 40:
        title_font_size -= 4
        title_font = ImageFont.truetype(FONT_PATH, title_font_size)
        lines = wrap_title(draw, title, title_font, max_text_width)

    line_height = int(title_font_size * 1.25)
    text_block_height = line_height * len(lines)
    y = H - 220 - text_block_height
    for line in lines:
        draw.text((60, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += line_height

    brand_font = ImageFont.truetype(FONT_PATH, 34)
    draw.text((60, H - 80), "TheRarePlantGuide.com", font=brand_font, fill=(255, 255, 255, 230))

    final = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    os.makedirs(PINS_DIR, exist_ok=True)
    pin_path = os.path.join(PINS_DIR, f"{slug}.jpg")
    final.save(pin_path, "JPEG", quality=90)
    return f"/images/pins/{slug}.jpg"


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

    content = build_markdown_file(article, cover, today, weight=topic.get("featured_weight"))

    os.makedirs(POSTS_DIR, exist_ok=True)
    filepath = os.path.join(POSTS_DIR, f"{slug}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    cover_local_path = cover["local_path"] if cover else None
    pin_image_path = build_pin_image(article["title"], slug, cover_local_path)

    topic["status"] = "done"
    topic["published_date"] = today
    topic["slug"] = slug
    topic["pin_title"] = article["title"]
    topic["pin_description"] = article["description"]
    topic["pin_image_path"] = pin_image_path
    topic["pin_status"] = "pending"
    save_queue(queue)

    print(f"Articolo generato con successo: {filepath}")
    print(f"Immagine pin salvata in: static{pin_image_path}")
    if cover:
        print(f"Immagine di copertina salvata in: {IMAGES_DIR}/{slug}.jpg")


if __name__ == "__main__":
    main()
