# BandoMatch AI — v3.0 🚀

**Il motore di matching predittivo tra PMI italiane e bandi di finanziamento pubblico.**

> Sviluppato da Manus (Lead Software Engineer) in collaborazione con Gemini (Architetto Strategico).

---

## Architettura

```
bandomatch/
├── app.py                  # Flask app principale (1.500+ righe)
├── visura_parser.py        # Parser PDF visura camerale nativa
├── matching_engine.py      # Motore matching con logica semaforo
├── simulatore_punteggio.py # Simulatore score 0-100
├── scraper_llm.py          # Scraper LLM-Augmented (GPT-4.1-mini)
├── national_scraper.py     # National Scraper (20 regioni + portali)
├── notifiche_push.py       # Notifiche predittive + Post Social AI
├── stripe_payments.py      # Integrazione Stripe (Premium/Pro/Consulenza)
├── dossier_pdf.py          # Generatore Dossier PDF professionale
├── templates/              # 12 template HTML (dark mode)
├── requirements.txt        # Dipendenze Python
├── Procfile                # Per Railway/Heroku
├── Dockerfile              # Per deploy containerizzato
└── .env.example            # Template variabili d'ambiente
```

---

## Funzionalità

### Core
- **Parser PDF Visura Camerale**: estrae ATECO, soci con quote ponderate, sede, età, forma giuridica
- **Matching Engine**: semaforo Verde/Giallo/Rosso/Grigio con pre-filtro bloccante
- **Simulatore Punteggio**: score 0-100 con suggerimenti "cosa fare per salire"

### Database Bandi
- **National Scraper**: 27 sorgenti (20 regioni + portali nazionali + aggregatori)
- **Scraper LLM-Augmented**: GPT-4.1-mini estrae parametri da testo non strutturato
- **Aggiornamento automatico**: ogni giorno alle 06:00 (APScheduler)
- **Feedback Loop**: tabella `feedback_bandi` per auto-apprendimento

### Monetizzazione
| Piano | Prezzo | Features |
|-------|--------|----------|
| Free | €0 | 1 analisi gratuita |
| Premium | €9,90/mese | Analisi illimitate + Dossier PDF + Alert email |
| Pro | €29,90/mese | Tutto Premium + Simulatore avanzato + Post Social AI + API |
| Consulenza | €49 una tantum | Sessione 60 min con esperto |

### UX
- **Teaser psicologico**: mostra valore potenziale prima del paywall
- **Dossier PDF professionale**: generato automaticamente post-pagamento
- **Alert email**: notifiche per nuovi bandi compatibili
- **Post Social AI**: contenuti LinkedIn/Instagram generati da GPT-4.1-mini
- **Dashboard Admin**: metriche utenti, bandi, feedback loop

---

## Deploy su Railway (raccomandato)

### 1. Crea account Railway
Vai su [railway.app](https://railway.app) e crea un account gratuito.

### 2. Crea un nuovo progetto
```bash
# Installa Railway CLI
npm install -g @railway/cli

# Login
railway login

# Crea progetto
railway init
```

### 3. Configura le variabili d'ambiente
Nella dashboard Railway, vai su **Variables** e aggiungi:
```
SECRET_KEY=<stringa-casuale-lunga>
OPENAI_API_KEY=<tua-chiave-openai>
STRIPE_SECRET_KEY=<tua-chiave-stripe>
STRIPE_PUBLISHABLE_KEY=<tua-chiave-pubblica-stripe>
STRIPE_WEBHOOK_SECRET=<secret-webhook-stripe>
ADMIN_EMAIL=simone.floriano79@gmail.com
ADMIN_PASSWORD=<password-sicura>
```

### 4. Deploy
```bash
# Dalla directory del progetto
railway up
```

Il deploy è automatico. Railway rileva il `Procfile` e avvia Gunicorn.

---

## Deploy con Docker

```bash
# Build
docker build -t bandomatch-ai .

# Run
docker run -p 5000:5000 --env-file .env bandomatch-ai
```

---

## Configurazione Stripe

### 1. Crea i prodotti in Stripe
Vai su [dashboard.stripe.com/products](https://dashboard.stripe.com/products) e crea:
- **BandoMatch Premium**: €9,90/mese ricorrente
- **BandoMatch Pro**: €29,90/mese ricorrente
- **Consulenza Esperto**: €49,00 una tantum

### 2. Copia gli ID dei prezzi
Copia i `price_xxx` e inseriscili nel file `stripe_payments.py` o nelle variabili d'ambiente.

### 3. Configura il Webhook
In Stripe Dashboard → Webhooks → Aggiungi endpoint:
- URL: `https://tuo-dominio.railway.app/webhook/stripe`
- Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

---

## Sviluppo Locale

```bash
# Clona il repo
git clone <repo-url>
cd bandomatch

# Installa dipendenze
pip install -r requirements.txt

# Copia e configura .env
cp .env.example .env
# Modifica .env con le tue chiavi

# Avvia
python3 app.py
```

L'app sarà disponibile su `http://localhost:5000`.

---

## Credenziali Admin Default

- **Email**: `simone.floriano79@gmail.com`
- **Password**: `BandoMatch2025!`

> ⚠️ Cambia la password admin prima del deploy in produzione!

---

## Roadmap

- [ ] Integrazione con Agenzia delle Entrate (verifica de minimis automatica)
- [ ] App mobile (React Native)
- [ ] API pubblica per consulenti e commercialisti
- [ ] Programma di affiliazione (20% commissione)
- [ ] Integrazione con software di contabilità (Fatture in Cloud, Zucchetti)

---

*BandoMatch AI — Costruito con ❤️ da Manus + Gemini per le PMI italiane*
