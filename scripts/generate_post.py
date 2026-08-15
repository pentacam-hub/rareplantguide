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
import re
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
MAX_GENERATION_ATTEMPTS = 3


def get_internal_link_candidates(queue, current_topic, max_links=6):
    """Return published posts, prioritizing the current topic cluster."""
    cluster = current_topic.get("cluster")
    published = [
        item for item in queue.get("topics", [])
        if item.get("status") == "done" and item.get("slug")
    ]
    published.sort(key=lambda item: item.get("cluster") != cluster)

    links = []
    seen = set()
    for item in published:
        slug = item["slug"]
        if slug in seen:
            continue
        seen.add(slug)
        links.append((item.get("pin_title") or item["title"], slug))
    return links[:max_links]


def build_prompt(topic, internal_links=None, correction_notes=None):
    keywords = ", ".join(topic.get("keywords", []))
    link_lines = "\n".join(
        f'- [{title}](/posts/{slug}/)' for title, slug in (internal_links or [])
    ) or "- No internal links are available for this article."
    correction_block = ""
    if correction_notes:
        correction_block = (
            "\nThe previous draft failed these automated checks. Correct every item:\n- "
            + "\n- ".join(correction_notes)
            + "\n"
        )

    return f"""You are an editorial writer for "The Rare Plant Guide", an English-language
educational website about rare and variegated houseplants.

Write a full blog post on this topic: "{topic['title']}"
Keywords to weave in naturally (do not force them, do not list them): {keywords}

Style and requirements:
- Use a warm, clear editorial voice, but never write in first person.
- Never invent personal experiences, testing, credentials, interviews, case studies, forum
  consensus, expert quotes, statistics, research, or scientific claims.
- Lead with a direct answer to the reader's problem. Avoid generic greetings and long stories.
- Separate observable signs from possible causes; do not present a symptom as a certain diagnosis.
- Give practical, plant-safe steps. Do not recommend off-label pesticide use, unsafe chemical
  mixtures, or household-remedy concentrations. Remind readers to follow product labels where relevant.
- Use 5-7 descriptive H2 (##) sections, short paragraphs, and useful lists or checklists.
- Length: 1000-1400 words.
- Include a final `## Frequently Asked Questions` section with at least three concise questions,
  each formatted as an H3 (`### Question?`) followed by a useful answer.
- Use 2-3 of the internal links supplied below naturally inside relevant paragraphs. Keep each URL exact.
- Do not add an H1 heading or repeat the article title inside the body.
- Do not add external citations unless source information is explicitly supplied; never invent sources.
- Finish with a concise action-oriented takeaway, not motivational filler.

Available internal links:
{link_lines}
{correction_block}

Respond in EXACTLY this plain text format, nothing before or after, no markdown code fences
around the whole response, using these exact section markers on their own line:

{TITLE_MARK}
<a specific SEO title of 40-70 characters, one line, no quotes around it>
{DESCRIPTION_MARK}
<one-sentence SEO description of 110-155 characters, one line>
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


def extract_faq(body_markdown):
    match = re.search(
        r"^## Frequently Asked Questions\s*$([\s\S]*)",
        body_markdown,
        flags=re.MULTILINE,
    )
    if not match:
        return []

    faq_block = match.group(1)
    questions = list(re.finditer(r"^###\s+(.+?\?)\s*$", faq_block, flags=re.MULTILINE))
    items = []
    for index, question_match in enumerate(questions):
        answer_start = question_match.end()
        answer_end = questions[index + 1].start() if index + 1 < len(questions) else len(faq_block)
        answer = faq_block[answer_start:answer_end].strip()
        answer = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", answer)
        answer = re.sub(r"[*_`]", "", answer)
        answer = re.sub(r"\s+", " ", answer).strip()
        if answer:
            items.append({"question": question_match.group(1).strip(), "answer": answer})
    return items


def validate_article(article, internal_links=None):
    errors = []
    title = article.get("title", "").strip()
    description = article.get("description", "").strip()
    tags = article.get("tags", [])
    body = article.get("body_markdown", "").strip()
    words = re.findall(r"\b[\w'-]+\b", body)

    if not 40 <= len(title) <= 70:
        errors.append(f"title length is {len(title)} characters; required range is 40-70")
    if not 110 <= len(description) <= 155:
        errors.append(f"description length is {len(description)} characters; required range is 110-155")
    if not 2 <= len(tags) <= 4:
        errors.append(f"tag count is {len(tags)}; required range is 2-4")
    if not 900 <= len(words) <= 1600:
        errors.append(f"body length is {len(words)} words; required range is 900-1600")
    if re.search(r"^#\s+", body, flags=re.MULTILINE):
        errors.append("body contains an H1 heading")
    if len(re.findall(r"^##\s+", body, flags=re.MULTILINE)) < 5:
        errors.append("body contains fewer than five H2 sections")

    first_person = re.search(r"\b(?:I|me|my|mine|we|us|our|ours)\b", body, flags=re.IGNORECASE)
    if first_person:
        errors.append(f"first-person language detected: '{first_person.group(0)}'")

    faq = extract_faq(body)
    if len(faq) < 3:
        errors.append("Frequently Asked Questions section contains fewer than three valid Q&A items")
    else:
        article["faq"] = faq

    required_links = min(2, len(internal_links or []))
    internal_link_count = len(re.findall(r"\]\(/posts/[^\)]+/\)", body))
    if internal_link_count < required_links:
        errors.append(
            f"body contains {internal_link_count} internal links; at least {required_links} are required"
        )

    forbidden_phrases = (
        "plant community forums",
        "fellow growers",
        "according to growers",
        "studies show",
        "research proves",
    )
    lowered_body = body.lower()
    for phrase in forbidden_phrases:
        if phrase in lowered_body:
            errors.append(f"unsupported attribution detected: '{phrase}'")

    return errors


def generate_article(model, topic, internal_links=None):
    correction_notes = None
    last_response = ""
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        prompt = build_prompt(topic, internal_links=internal_links, correction_notes=correction_notes)
        response = model.generate_content(prompt)
        last_response = response.text
        try:
            article = parse_article_response(response.text)
        except (ValueError, AttributeError) as error:
            correction_notes = [f"output format could not be parsed: {error}"]
            print(f"Tentativo {attempt}/{MAX_GENERATION_ATTEMPTS} non valido: {correction_notes[0]}")
            continue

        errors = validate_article(article, internal_links=internal_links)
        if not errors:
            return article

        correction_notes = errors
        print(f"Tentativo {attempt}/{MAX_GENERATION_ATTEMPTS} rifiutato dai controlli qualità:")
        for error in errors:
            print(f"- {error}")

    raise ValueError(
        "Generazione interrotta: nessuna bozza ha superato i controlli qualità dopo "
        f"{MAX_GENERATION_ATTEMPTS} tentativi. Ultima risposta:\n{last_response[:2000]}"
    )


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


def get_related_links(queue, current_topic, max_links=3):
    """Trova fino a max_links articoli già pubblicati nello stesso cluster
    tematico, da linkare in fondo al nuovo articolo (link interni SEO)."""
    cluster = current_topic.get("cluster")
    if not cluster:
        return []
    related = []
    for t in queue.get("topics", []):
        if (
            t.get("cluster") == cluster
            and t.get("status") == "done"
            and t.get("slug")
            and t.get("slug") != current_topic.get("slug")
        ):
            title = t.get("pin_title") or t.get("title")
            related.append((title, t["slug"]))
    return related[:max_links]


def build_markdown_file(article, cover, today, weight=None, related_links=None):
    tags_yaml = json.dumps(article["tags"], ensure_ascii=False)

    front_matter_lines = [
        "---",
        f'title: {json.dumps(article["title"], ensure_ascii=False)}',
        f"date: {today}",
        "draft: false",
        f'description: {json.dumps(article["description"], ensure_ascii=False)}',
        f"tags: {tags_yaml}",
        'categories: ["Plant Care"]',
    ]

    if article.get("faq"):
        front_matter_lines.append("faq:")
        for item in article["faq"]:
            question = json.dumps(item["question"], ensure_ascii=False)
            answer = json.dumps(item["answer"], ensure_ascii=False)
            front_matter_lines.extend([
                f"  - question: {question}",
                f"    answer: {answer}",
            ])

    if weight is not None:
        front_matter_lines.append(f"weight: {weight}")

    body = article["body_markdown"].strip()

    if related_links:
        links_md = "\n".join(f"- [{title}](/posts/{slug}/)" for title, slug in related_links)
        body += f"\n\n## Related Guides\n\n{links_md}"

    if cover:
        front_matter_lines += [
            "cover:",
            f'    image: {json.dumps(cover["local_path"], ensure_ascii=False)}',
            f'    alt: {json.dumps(cover["alt"], ensure_ascii=False)}',
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

    internal_links = get_internal_link_candidates(queue, topic)
    article = generate_article(model, topic, internal_links=internal_links)

    slug = slugify(article["title"])
    today = datetime.date.today().isoformat()

    cover = None
    if unsplash_key:
        image_query = topic.get("image_query", topic["title"])
        cover = fetch_cover_image(image_query, slug, unsplash_key)

    related_links = get_related_links(queue, topic)
    content = build_markdown_file(article, cover, today, weight=topic.get("featured_weight"), related_links=related_links)

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
