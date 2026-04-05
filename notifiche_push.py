"""
BandoMatch AI v3.0 — Modulo Notifiche Push Predittive + Post Social Automatici
Gemini Strategy: "Il bando deve cercare l'imprenditore, non il contrario"
"""

import json
import os
import sqlite3
from datetime import datetime
from openai import OpenAI

# OpenAI client (pre-configurato con API key dall'ambiente)
client = OpenAI()

DB_PATH = os.path.join(os.path.dirname(__file__), 'bandomatch.db')
BANDI_DB_PATH = os.path.join(os.path.dirname(__file__), 'bandi_db.json')


def carica_bandi_db():
    """Carica il database dei bandi dal file JSON."""
    try:
        with open(BANDI_DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def get_utenti_premium():
    """Recupera tutti gli utenti con piano premium o pro dal DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.nome, u.piano,
               a.dati_estratti, a.risultati_matching, a.created_at
        FROM utenti u
        LEFT JOIN analisi a ON a.utente_id = u.id
        WHERE u.piano IN ('premium', 'pro')
        AND a.id = (SELECT MAX(id) FROM analisi WHERE utente_id = u.id)
    """)
    utenti = cursor.fetchall()
    conn.close()
    return utenti


def genera_notifica_predittiva(nome_azienda, nome_bando, valore_max, semaforo):
    """Genera il testo personalizzato della notifica push predittiva."""
    emoji_semaforo = {"verde": "🟢", "giallo": "🟡", "rosso": "🔴", "grigio": "⚫"}.get(semaforo, "🔵")
    
    templates = {
        "verde": [
            f"🚨 {nome_azienda}, NUOVO BANDO COMPATIBILE! {emoji_semaforo} '{nome_bando}' — fino a €{valore_max:,.0f} a fondo perduto. Il tuo semaforo è VERDE. Candidati subito!",
            f"💰 Trovati €{valore_max:,.0f} per {nome_azienda}! Il bando '{nome_bando}' è perfetto per te. Semaforo VERDE — agisci entro 48h!",
        ],
        "giallo": [
            f"⚡ {nome_azienda}, bando '{nome_bando}' quasi compatibile! {emoji_semaforo} Fino a €{valore_max:,.0f}. Completa il profilo per sbloccare il semaforo VERDE.",
        ],
        "grigio": [
            f"📋 {nome_azienda}, bando '{nome_bando}' rilevato (€{valore_max:,.0f}). Dati insufficienti per il calcolo — completa il profilo per verificare la compatibilità.",
        ]
    }
    
    import random
    msgs = templates.get(semaforo, templates["grigio"])
    return random.choice(msgs)


def genera_post_social(bando: dict) -> dict:
    """
    Genera automaticamente post social per LinkedIn, Instagram e Twitter/X
    usando GPT-4.1-mini per ogni nuovo bando caricato nel sistema.
    """
    nome_bando = bando.get('nome', 'Nuovo Bando')
    valore_max = bando.get('massimale_spesa', 0)
    regioni = ', '.join(bando.get('regioni_ammesse', ['Italia']))
    settori = bando.get('settori_ammessi_descrizione', 'PMI di tutti i settori')
    scadenza = bando.get('scadenza', 'a sportello')
    perc_fondo_perduto = bando.get('percentuale_fondo_perduto', 0)
    
    prompt = f"""Sei un copywriter esperto di marketing per PMI italiane. 
Genera 3 post social per il bando "{nome_bando}":
- Valore massimo: €{valore_max:,}
- Fondo perduto: {perc_fondo_perduto}%
- Regioni: {regioni}
- Settori: {settori}
- Scadenza: {scadenza}

Genera:
1. POST LINKEDIN (professionale, 150-200 parole, con hashtag #PMI #Finanziamenti #Bandi)
2. POST INSTAGRAM (emozionale, 80-100 parole, con 5 emoji pertinenti e hashtag)
3. POST TWITTER/X (incisivo, max 280 caratteri, con 2-3 hashtag)

Formato risposta JSON:
{{"linkedin": "...", "instagram": "...", "twitter": "..."}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        posts = json.loads(response.choices[0].message.content)
        return {
            "bando_id": bando.get('id', ''),
            "bando_nome": nome_bando,
            "generato_il": datetime.now().isoformat(),
            "posts": posts
        }
    except Exception as e:
        # Fallback con template statico
        return {
            "bando_id": bando.get('id', ''),
            "bando_nome": nome_bando,
            "generato_il": datetime.now().isoformat(),
            "posts": {
                "linkedin": f"🎯 NUOVO BANDO DISPONIBILE: {nome_bando}\n\nFino a €{valore_max:,} a fondo perduto ({perc_fondo_perduto}%) per le PMI di {regioni}.\n\nScadenza: {scadenza}\n\nCarica la tua visura su BandoMatch AI e scopri se sei compatibile in 30 secondi!\n\n#PMI #Finanziamenti #Bandi #Impresa #BandoMatchAI",
                "instagram": f"💰 €{valore_max:,} disponibili per la tua azienda!\n\nIl bando '{nome_bando}' è aperto per le PMI di {regioni}.\n\n✅ Fondo perduto: {perc_fondo_perduto}%\n📅 Scadenza: {scadenza}\n\nScopri se sei compatibile con BandoMatch AI! 🚀\n\n#PMI #Bandi #Finanziamenti #Impresa #Startup",
                "twitter": f"💰 BANDO APERTO: {nome_bando} — fino a €{valore_max:,} ({perc_fondo_perduto}% fondo perduto) per PMI di {regioni}. Scad: {scadenza}. Verifica compatibilità su BandoMatch AI! #PMI #Bandi"
            }
        }


def esegui_matching_predittivo_utenti():
    """
    Esegue il matching predittivo per tutti gli utenti premium/pro
    e genera le notifiche per i nuovi bandi compatibili.
    Chiamato dallo scheduler ogni mattina alle 08:00.
    """
    from matching_engine import match_tutti_bandi
    
    bandi = carica_bandi_db()
    utenti = get_utenti_premium()
    notifiche_generate = []
    
    for utente in utenti:
        try:
            dati_impresa = json.loads(utente['dati_estratti']) if utente['dati_estratti'] else None
            if not dati_impresa:
                continue
            
            risultati = match_tutti_bandi(dati_impresa)
            
            for r in risultati:
                if r.get('semaforo') in ('verde', 'giallo'):
                    notifica = {
                        "utente_id": utente['id'],
                        "email": utente['email'],
                        "nome_azienda": dati_impresa.get('ragione_sociale', 'La tua azienda'),
                        "bando_id": r.get('bando_id', ''),
                        "bando_nome": r.get('nome', ''),
                        "semaforo": r.get('semaforo', ''),
                        "valore_potenziale": r.get('valore_potenziale', 0),
                        "testo_notifica": genera_notifica_predittiva(
                            dati_impresa.get('ragione_sociale', 'La tua azienda'),
                            r.get('nome', ''),
                            r.get('valore_potenziale', 0),
                            r.get('semaforo', '')
                        ),
                        "generata_il": datetime.now().isoformat()
                    }
                    notifiche_generate.append(notifica)
        except Exception as e:
            continue
    
    # Salva le notifiche nel DB
    if notifiche_generate:
        _salva_notifiche_db(notifiche_generate)
    
    return notifiche_generate


def _salva_notifiche_db(notifiche: list):
    """Salva le notifiche generate nel database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crea la tabella se non esiste
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifiche_push (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utente_id INTEGER,
            email TEXT,
            nome_azienda TEXT,
            bando_id TEXT,
            bando_nome TEXT,
            semaforo TEXT,
            valore_potenziale REAL,
            testo_notifica TEXT,
            letta INTEGER DEFAULT 0,
            inviata_email INTEGER DEFAULT 0,
            generata_il TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for n in notifiche:
        cursor.execute("""
            INSERT INTO notifiche_push 
            (utente_id, email, nome_azienda, bando_id, bando_nome, semaforo, 
             valore_potenziale, testo_notifica, generata_il)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            n['utente_id'], n['email'], n['nome_azienda'],
            n['bando_id'], n['bando_nome'], n['semaforo'],
            n['valore_potenziale'], n['testo_notifica'], n['generata_il']
        ))
    
    conn.commit()
    conn.close()


def genera_post_social_tutti_bandi_nuovi(bandi_nuovi: list) -> list:
    """
    Genera i post social per tutti i nuovi bandi caricati nel sistema.
    Chiamato dallo scraper dopo ogni aggiornamento.
    """
    posts_generati = []
    for bando in bandi_nuovi:
        post = genera_post_social(bando)
        posts_generati.append(post)
    return posts_generati


def get_notifiche_utente(utente_id: int) -> list:
    """Recupera le notifiche non lette per un utente."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM notifiche_push 
        WHERE utente_id = ? AND letta = 0
        ORDER BY created_at DESC
        LIMIT 10
    """, (utente_id,))
    notifiche = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return notifiche


def segna_notifica_letta(notifica_id: int):
    """Segna una notifica come letta."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE notifiche_push SET letta = 1 WHERE id = ?", (notifica_id,))
    conn.commit()
    conn.close()


# ============================================================
# TEST STANDALONE
# ============================================================
if __name__ == "__main__":
    print("=== TEST Notifiche Push + Post Social ===\n")
    
    # Test generazione post social
    bando_test = {
        "id": "resto_al_sud",
        "nome": "Resto al Sud 2.0",
        "massimale_spesa": 200000,
        "percentuale_fondo_perduto": 50,
        "regioni_ammesse": ["Abruzzo", "Campania", "Sicilia", "Calabria"],
        "settori_ammessi_descrizione": "Artigianato, Manifatturiero, Servizi alle imprese",
        "scadenza": "A sportello (fino ad esaurimento fondi)"
    }
    
    print("📱 Generazione Post Social per 'Resto al Sud 2.0'...")
    posts = genera_post_social(bando_test)
    print(f"\n✅ Post generati per: {posts['bando_nome']}")
    print(f"\n--- LINKEDIN ---\n{posts['posts']['linkedin'][:200]}...")
    print(f"\n--- INSTAGRAM ---\n{posts['posts']['instagram'][:150]}...")
    print(f"\n--- TWITTER/X ---\n{posts['posts']['twitter']}")
    
    # Test notifica predittiva
    print("\n\n🔔 Test Notifica Predittiva:")
    notifica = genera_notifica_predittiva(
        "Tech Solutions Srl", "Resto al Sud 2.0", 200000, "verde"
    )
    print(f"✅ {notifica}")
    
    print("\n\n✅ Modulo Notifiche Push + Post Social operativo!")
