# BandoMatch AI — Manuale Operativo Completo
## Guida al Deploy e alla Gestione

---

## 1. DEPLOY RAPIDO SU RENDER.COM (Gratuito — 5 minuti)

### Step 1: Crea un account GitHub
1. Vai su https://github.com e crea un account gratuito
2. Crea un nuovo repository chiamato `bandomatch-ai` (privato)

### Step 2: Carica il codice
```bash
# Nella tua macchina locale, decomprimi il file ZIP
# Poi esegui:
cd bandomatch
git init
git add .
git commit -m "BandoMatch AI v3.0 - Initial commit"
git remote add origin https://github.com/TUO-USERNAME/bandomatch-ai.git
git push -u origin main
```

### Step 3: Deploy su Render.com
1. Vai su https://render.com e crea un account gratuito
2. Clicca **"New +"** → **"Web Service"**
3. Connetti il tuo repository GitHub `bandomatch-ai`
4. Render rileva automaticamente `render.yaml` e configura tutto
5. Aggiungi le variabili d'ambiente (vedi sezione 3)
6. Clicca **"Create Web Service"**
7. In 3-5 minuti il tuo URL sarà: `https://bandomatch-ai.onrender.com`

---

## 2. DEPLOY SU RAILWAY.APP (Alternativa — Piano Starter $5/mese)

1. Vai su https://railway.app
2. Clicca **"New Project"** → **"Deploy from GitHub"**
3. Seleziona il repository `bandomatch-ai`
4. Railway usa automaticamente il `Procfile`
5. Aggiungi le variabili d'ambiente nel pannello **Variables**
6. Il tuo URL sarà: `https://bandomatch-ai.up.railway.app`

---

## 3. VARIABILI D'AMBIENTE NECESSARIE

Copia questo template e compila i valori:

```env
# OBBLIGATORIE
SECRET_KEY=genera-una-stringa-casuale-di-32-caratteri
FLASK_ENV=production

# STRIPE (da https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# STRIPE PRICE IDs (da https://dashboard.stripe.com/products)
STRIPE_PRICE_PREMIUM=price_...   # €9,90/mese
STRIPE_PRICE_PRO=price_...       # €29,90/mese
STRIPE_PRICE_CONSULENZA=price_... # €49 una tantum

# EMAIL (Gmail App Password)
MAIL_USERNAME=tua-email@gmail.com
MAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx  # App Password Gmail
ADMIN_EMAIL=tua-email@gmail.com

# OPENAI (da https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-...
```

---

## 4. CONFIGURAZIONE STRIPE (15 minuti)

### Crea i prodotti:
1. Vai su https://dashboard.stripe.com/products
2. Crea **"BandoMatch Premium"** — €9,90/mese ricorrente
3. Crea **"BandoMatch Pro"** — €29,90/mese ricorrente
4. Crea **"Consulenza Esperto"** — €49 una tantum
5. Copia i **Price ID** (iniziano con `price_`) nelle variabili d'ambiente

### Configura il Webhook:
1. Vai su https://dashboard.stripe.com/webhooks
2. Clicca **"Add endpoint"**
3. URL: `https://tuo-dominio.onrender.com/stripe/webhook`
4. Seleziona eventi: `checkout.session.completed`, `customer.subscription.deleted`
5. Copia il **Webhook Secret** (inizia con `whsec_`) nelle variabili

---

## 5. STRUTTURA DEL PROGETTO

```
bandomatch/
├── app.py                  # App Flask principale (63KB, ~1500 righe)
├── matching_engine.py      # Motore di matching semaforo (27KB)
├── visura_parser.py        # Parser PDF visura camerale (22KB)
├── simulatore_punteggio.py # Simulatore score 0-100 (13KB)
├── scraper_llm.py          # Scraper AI-Augmented (12KB)
├── national_scraper.py     # Scraper 27 sorgenti nazionali (19KB)
├── dossier_pdf.py          # Generatore PDF Dossier (25KB)
├── stripe_payments.py      # Integrazione Stripe (12KB)
├── notifiche_push.py       # Notifiche + Post Social AI (10KB)
├── templates/              # 12 template HTML
│   ├── landing.html        # Landing page principale
│   ├── index.html          # App con upload visura
│   ├── dashboard.html      # Area utente
│   ├── upgrade.html        # Pagina pricing
│   ├── admin.html          # Dashboard admin
│   └── ...
├── requirements.txt        # Dipendenze Python
├── Procfile                # Comando avvio Railway/Heroku
├── render.yaml             # Config deploy Render
├── Dockerfile              # Container Docker
└── .env.example            # Template variabili d'ambiente
```

---

## 6. FUNZIONALITÀ IMPLEMENTATE

### Core Features
| Feature | Descrizione |
|---|---|
| **Parser PDF** | Estrae ATECO, soci, sede, età, quote societarie da visura camerale nativa |
| **Matching Semaforo** | Verde/Giallo/Rosso/Grigio con pre-filtro bloccante |
| **Simulatore Score** | Punteggio 0-100 con suggerimenti per migliorare |
| **Form Integrativo** | 4 domande contestuali (solo se il bando le richiede) |
| **Dossier PDF** | Report professionale con copertina, semafori e piano d'azione |

### Monetizzazione
| Piano | Prezzo | Funzionalità |
|---|---|---|
| **Free** | €0 | 1 analisi/mese, semaforo base |
| **Premium** | €9,90/mese | Analisi illimitate, Dossier PDF, Alert email |
| **Pro** | €29,90/mese | Tutto Premium + Reverse Matching, Post Social AI |
| **Consulenza** | €49 una tantum | Sessione 1:1 con esperto |

### Aggiornamento Automatico
- **Scraper giornaliero**: ogni mattina alle 06:00 aggiorna il database bandi
- **27 sorgenti**: Invitalia, FiRA, 20 Regioni, Ministeri, PNRR
- **LLM-Augmented**: GPT-4.1-mini estrae parametri da PDF bandi complessi
- **Alert email**: ogni mattina alle 08:00 notifica gli utenti con nuovi bandi compatibili

---

## 7. CANALE CNA — PROPOSTA B2B

Per proporre BandoMatch AI alla CNA:

**Pitch in 30 secondi:**
> "CNA ha già i dati di migliaia di aziende associate. BandoMatch AI trasforma quei dati in opportunità concrete di finanziamento. Ogni volta che un associato ottiene un bando grazie alla nostra piattaforma, CNA diventa l'eroe della storia."

**Modello di Partnership:**
- CNA ottiene accesso white-label (logo CNA sull'app)
- Prezzo speciale per associati: €7,90/mese invece di €9,90
- Revenue share: 20% a CNA per ogni abbonamento da associati

---

## 8. ROADMAP FUTURA

| Priorità | Feature | Impatto |
|---|---|---|
| 🔴 Alta | Integrazione API InfoCamere (dati ufficiali) | Elimina errori OCR |
| 🔴 Alta | Verifica automatica De Minimis | Matching più preciso |
| 🟡 Media | App mobile (React Native) | Più utenti |
| 🟡 Media | Integrazione DURC automatico | Requisito chiave |
| 🟢 Bassa | Marketplace consulenti | Upsell naturale |

---

## 9. SUPPORTO

Per qualsiasi problema tecnico, contatta:
- **Manus AI** (Lead Software Engineer del progetto)
- **Gemini** (Strategia e Product Design)

---

*BandoMatch AI v3.0 — Sviluppato da Manus AI + Gemini per Simone Floriano*
*Aprile 2026*
