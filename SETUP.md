# Setup del sistema di agenti — The Rare Plant Guide

## 1. Copia i file nel repo
Copia questi file mantenendo la stessa struttura di cartelle dentro
`rareplantguide`:

```
.github/workflows/auto-post.yml
scripts/requirements.txt
scripts/generate_post.py
content-queue.yaml
```

✅ Path già verificati e corretti per la tua struttura reale:
- `POSTS_DIR = "content/posts"` → confermato, è dove hai già i tuoi file `.md`
- `IMAGES_DIR = "static/images"` → confermato, è dove hai già le immagini scaricate finora

Non serve modificare nulla, puoi copiare i file così come sono.

## 2. Prendi una chiave API Gemini gratuita (per il testo)
1. Vai su https://aistudio.google.com/app/apikey
2. Accedi con un account Google, clicca "Create API key"
3. Copia la chiave (è gratuita, con limiti di utilizzo generosi per
   pochi articoli a settimana — nessuna carta di credito richiesta)

## 3. Prendi una chiave API Unsplash gratuita (per le immagini)
1. Vai su https://unsplash.com/developers e crea un account (gratuito)
2. "New Application" → accetta i termini → dai un nome all'app
   (es. "TheRarePlantGuide")
3. Nella pagina dell'app copia la "Access Key"
4. Il piano gratuito (demo) permette 50 richieste/ora — più che
   sufficiente per 1-2 articoli a settimana

## 4. Aggiungi entrambe le chiavi come secret su GitHub
1. Vai sul repo → Settings → Secrets and variables → Actions
2. "New repository secret" → nome `GEMINI_API_KEY` → incolla la chiave Gemini → Salva
3. "New repository secret" → nome `UNSPLASH_ACCESS_KEY` → incolla la chiave Unsplash → Salva

## 5. Testalo subito (senza aspettare lunedì/giovedì)
1. Vai su repo → tab "Actions"
2. Seleziona il workflow "Auto Publish Article"
3. Clicca "Run workflow" (pulsante in alto a destra) per lanciarlo
   manualmente e vedere se genera correttamente il primo articolo

Se tutto funziona, vedrai un nuovo commit con un file `.md` dentro
`content/posts/`, e Cloudflare Pages ripubblicherà il sito da solo
in pochi minuti.

## Come funziona la schedulazione
- Parte automaticamente **lunedì e giovedì alle 08:00 UTC**
- Ogni esecuzione pesca il prossimo argomento "pending" da
  `content-queue.yaml`, lo marca come "done" dopo la pubblicazione
- Quando la coda finisce (25 argomenti = circa 3 mesi a ritmo di
  2/settimana), aggiungi semplicemente altri topic allo stesso file,
  seguendo lo stesso formato

## Note
- Il modello usato è `gemini-2.0-flash-exp` (gratuito). Se Google lo
  deprecasse o lo rinominasse, basta cambiare la stringa `MODEL_NAME`
  in `scripts/generate_post.py`
- Le immagini di copertina vengono ora scaricate automaticamente da
  Unsplash (foto reali gratuite, royalty-free) in base alla
  `image_query` che hai definito per ogni topic in `content-queue.yaml`.
  Lo script rispetta le linee guida API di Unsplash: notifica il
  download e aggiunge in fondo all'articolo una riga di attribuzione
  al fotografo (obbligatoria per l'uso gratuito delle foto)
- Se non trova un'immagine adatta, o se manca la chiave
  `UNSPLASH_ACCESS_KEY`, il post viene comunque creato ma senza cover
  — non blocca mai la pubblicazione del testo
- Lo stile delle foto Unsplash (fotografia reale) è diverso da quello
  "editorial botanico" generato con Bing Image Creator che usavi prima:
  se vuoi restare fedele a quello stile, posso invece impostare lo
  script per generare le immagini con un modello AI anziché scaricarle
  da Unsplash — fammi sapere
