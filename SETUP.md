# Daily Content Agent — The Rare Plant Guide

L'agente vive nel repository e gira tramite GitHub Actions anche quando ChatGPT è chiuso.

## Cosa fa ogni giorno

Il workflow `.github/workflows/auto-post.yml` parte alle **00:15 UTC** e:

1. controlla che tutte le credenziali siano configurate;
2. esegue i test automatici del generatore e dell'integrazione Pinterest;
3. se non esiste un Pin da ritentare, genera un articolo dalla prima voce `pending` di `content-queue.yaml`;
4. genera la cover e un'immagine Pinterest verticale 1000×1500;
5. compila l'intero sito con Hugo e interrompe tutto se il build fallisce;
6. pubblica articolo e immagini su `main`, facendo partire Cloudflare;
7. attende che articolo e immagine siano realmente online;
8. pubblica **un solo Pin** sulla board `Rare Plant Care Tips`;
9. salva nel repository l'ID restituito da Pinterest.

Se Pinterest fallisce, il Pin resta `pending`. Il giorno successivo l'agente ritenta quel Pin e non genera un altro articolo: non crea arretrati e non pubblica più di un Pin al giorno. Prima di creare un Pin controlla anche se sul profilo esiste già un Pin con lo stesso link.

## Configurazione una tantum

Aprire:

`GitHub → pentacam-hub/rareplantguide → Settings → Secrets and variables → Actions`

Aggiungere questi repository secrets:

| Secret | Contenuto |
|---|---|
| `GEMINI_API_KEY` | Chiave API Google AI Studio usata per il testo |
| `UNSPLASH_ACCESS_KEY` | Access Key dell'app Unsplash usata per le foto |
| `PINTEREST_APP_ID` | App ID dell'app Pinterest |
| `PINTEREST_APP_SECRET` | App secret Pinterest |
| `PINTEREST_REFRESH_TOKEN` | Continuous refresh token Pinterest con gli scope richiesti |
| `GH_SECRETS_PAT` | Fine-grained GitHub PAT limitato a questo repository, con `Secrets: Read and write` |

Non inserire mai questi valori nei file del repository.

## Requisiti Pinterest

L'app Pinterest deve essere collegata all'account corretto e il token deve includere gli scope minimi:

- `boards:read`
- `boards:write`
- `pins:read`
- `pins:write`

Perché i Pin siano distribuiti pubblicamente, verificare che l'app abbia l'access tier appropriato per la produzione; nel tier Trial i Pin creati via API sono visibili soltanto al loro autore.

Pinterest usa continuous refresh token con scadenza mobile. Ogni esecuzione salva il nuovo token in un file temporaneo del runner e aggiorna automaticamente `PINTEREST_REFRESH_TOKEN` tramite `GH_SECRETS_PAT`. Il PAT deve essere limitato al solo repository `pentacam-hub/rareplantguide`.

Documentazione ufficiale:

- https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/
- https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/
- https://docs.github.com/rest/actions/secrets

## Avvio e controllo

Per un test manuale:

`GitHub → Actions → Daily Content Agent → Run workflow`

Un run è riuscito soltanto se termina verde e mostra:

- test superati;
- build Hugo completata;
- deploy pubblico rilevato;
- Pin creato oppure Pin preesistente riconosciuto;
- stato `posted` e `pinterest_pin_id` salvati in `content-queue.yaml`.

Gli argomenti futuri si aggiungono a `content-queue.yaml` con `status: pending`. Quando la coda è vuota, il workflow termina senza inventare nuovi argomenti.
