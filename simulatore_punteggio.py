"""
BandoMatch AI — Simulatore di Punteggio v3.0
Calcola il punteggio attuale e suggerisce azioni per aumentarlo.
Logica: punteggio base + bonus per caratteristiche vantaggiose.
Autore: Manus AI (Lead Software Engineer)
"""

from typing import Optional


# ─────────────────────────────────────────────
# TABELLA BONUS PUNTEGGIO
# Ogni bonus ha: punti, descrizione, azione suggerita
# ─────────────────────────────────────────────

BONUS_TABLE = {
    # BONUS DEMOGRAFICI
    "socio_donna": {
        "punti": 8,
        "label": "Imprenditrice donna",
        "descrizione": "Almeno il 51% delle quote detenute da donne",
        "azione": "Hai già questo bonus! Molti bandi premiano le imprese femminili.",
        "categoria": "demografico"
    },
    "socio_under30": {
        "punti": 12,
        "label": "Socio under 30",
        "descrizione": "Almeno un socio ha meno di 30 anni",
        "azione": "Considera di coinvolgere un socio under 30: sblocchi bandi come 'Resto al Sud 2.0' e 'Micro Prestiti Linea A'.",
        "categoria": "demografico"
    },
    "socio_under35": {
        "punti": 8,
        "label": "Socio under 35",
        "descrizione": "Almeno il 70% delle quote detenute da under 35",
        "azione": "Con soci under 35 al 70%+ accedi a bandi regionali per giovani imprenditori.",
        "categoria": "demografico"
    },
    "disoccupato": {
        "punti": 10,
        "label": "Titolare disoccupato/inoccupato",
        "descrizione": "Il titolare era disoccupato o inoccupato prima di avviare l'impresa",
        "azione": "Questo requisito sblocca 'Resto al Sud 2.0' e i bandi per l'autoimprenditorialità.",
        "categoria": "demografico"
    },

    # BONUS GEOGRAFICI
    "mezzogiorno": {
        "punti": 10,
        "label": "Sede nel Mezzogiorno",
        "descrizione": "Sede legale in una delle regioni del Mezzogiorno",
        "azione": "Hai già questo bonus! Accedi a Resto al Sud, Decontribuzione Sud e bandi regionali.",
        "categoria": "geografico"
    },
    "zona_sismica": {
        "punti": 8,
        "label": "Sede in zona sismica",
        "descrizione": "Sede in provincia del cratere sismico Centro Italia (RI, MC, AP, PG)",
        "azione": "Hai già questo bonus! Accedi ai bandi per la ricostruzione post-sisma.",
        "categoria": "geografico"
    },
    "zona_svantaggiata": {
        "punti": 6,
        "label": "Sede in area svantaggiata",
        "descrizione": "Sede in comune montano, isola minore o area a bassa densità",
        "azione": "Verifica se il tuo comune è classificato come area svantaggiata: sblocchi bandi LEADER e PSR.",
        "categoria": "geografico"
    },

    # BONUS SETTORIALI
    "green_energy": {
        "punti": 10,
        "label": "Investimento Green/Fotovoltaico",
        "descrizione": "L'investimento riguarda energia rinnovabile o efficienza energetica",
        "azione": "Hai già questo bonus! Accedi a Transizione 5.0, Conto Termico e bandi regionali FESR.",
        "categoria": "settoriale"
    },
    "industria_40": {
        "punti": 8,
        "label": "Investimento Industria 4.0",
        "descrizione": "L'investimento riguarda macchinari, automazione o digitalizzazione",
        "azione": "Hai già questo bonus! Accedi al Piano Transizione 5.0 e ai bandi FESR per innovazione.",
        "categoria": "settoriale"
    },
    "export": {
        "punti": 7,
        "label": "Progetto di internazionalizzazione",
        "descrizione": "L'investimento riguarda l'export o l'apertura di mercati esteri",
        "azione": "Hai già questo bonus! Accedi ai bandi SIMEST, ICE e voucher per l'internazionalizzazione.",
        "categoria": "settoriale"
    },
    "assunzione": {
        "punti": 9,
        "label": "Piano di assunzione",
        "descrizione": "L'impresa prevede di assumere nuovo personale",
        "azione": "Hai già questo bonus! Accedi a decontribuzione, bonus assunzioni under 30 e bandi occupazione.",
        "categoria": "settoriale"
    },

    # BONUS AZIENDALI
    "impresa_nuova": {
        "punti": 8,
        "label": "Impresa giovane (< 24 mesi)",
        "descrizione": "L'impresa ha meno di 24 mesi di vita",
        "azione": "Hai già questo bonus! Le startup accedono a bandi specifici come Micro Prestiti e Smart&Start.",
        "categoria": "aziendale"
    },
    "micro_impresa": {
        "punti": 5,
        "label": "Micro impresa (< 10 dipendenti)",
        "descrizione": "L'impresa ha meno di 10 dipendenti e fatturato < 2M€",
        "azione": "Hai già questo bonus! Le micro imprese accedono a bandi de minimis con procedure semplificate.",
        "categoria": "aziendale"
    },
    "no_de_minimis": {
        "punti": 7,
        "label": "Nessun aiuto de minimis ricevuto",
        "descrizione": "L'impresa non ha ricevuto aiuti de minimis negli ultimi 3 anni",
        "azione": "Hai già questo bonus! Hai il massimale de minimis disponibile (€300.000 nel triennio).",
        "categoria": "aziendale"
    },
    "cooperativa": {
        "punti": 6,
        "label": "Forma cooperativa",
        "descrizione": "L'impresa è una cooperativa o società cooperativa",
        "azione": "Le cooperative accedono a bandi specifici del Ministero dello Sviluppo Economico.",
        "categoria": "aziendale"
    },
}

# Punteggio base garantito a tutti
PUNTEGGIO_BASE = 30

# Punteggio massimo teorico
PUNTEGGIO_MAX = PUNTEGGIO_BASE + sum(b["punti"] for b in BONUS_TABLE.values())


def calcola_simulatore(profilo: dict, form_extra: dict = None) -> dict:
    """
    Calcola il punteggio attuale dell'impresa e i bonus disponibili.
    
    Args:
        profilo: Profilo estratto dalla visura camerale
        form_extra: Dati aggiuntivi dal form integrativo
    
    Returns:
        dict con punteggio, bonus attivi, bonus disponibili e suggerimenti
    """
    if form_extra is None:
        form_extra = {}
    
    bonus_attivi = []
    bonus_disponibili = []
    punteggio = PUNTEGGIO_BASE
    
    indicatori = profilo.get("indicatori_matching", {})
    soci = profilo.get("soci", [])
    impresa = profilo.get("impresa", {})
    
    # ─── VERIFICA BONUS DEMOGRAFICI ───────────────
    
    # Socio donna
    perc_donne = indicatori.get("percentuale_soci_donne", 0) or 0
    if perc_donne >= 51:
        bonus_attivi.append("socio_donna")
        punteggio += BONUS_TABLE["socio_donna"]["punti"]
    else:
        bonus_disponibili.append("socio_donna")
    
    # Socio under 30
    has_under30 = any(
        s.get("eta_anni") is not None and s["eta_anni"] < 30
        for s in soci
    )
    if has_under30:
        bonus_attivi.append("socio_under30")
        punteggio += BONUS_TABLE["socio_under30"]["punti"]
    else:
        bonus_disponibili.append("socio_under30")
    
    # Socio under 35 (70%+ quote)
    perc_under35 = indicatori.get("percentuale_soci_under35", 0) or 0
    if perc_under35 >= 70:
        bonus_attivi.append("socio_under35")
        punteggio += BONUS_TABLE["socio_under35"]["punti"]
    elif "socio_under30" not in bonus_attivi:
        bonus_disponibili.append("socio_under35")
    
    # Condizione occupazionale
    cond_occ = form_extra.get("condizione_occupazionale", "")
    if cond_occ in ["disoccupato", "inoccupato"]:
        bonus_attivi.append("disoccupato")
        punteggio += BONUS_TABLE["disoccupato"]["punti"]
    else:
        bonus_disponibili.append("disoccupato")
    
    # ─── VERIFICA BONUS GEOGRAFICI ────────────────
    
    regione = indicatori.get("regione", "")
    REGIONI_MEZZOGIORNO = [
        "Abruzzo", "Basilicata", "Calabria", "Campania",
        "Molise", "Puglia", "Sardegna", "Sicilia"
    ]
    PROVINCE_CRATERE = ["RI", "MC", "AP", "PG"]
    
    if regione in REGIONI_MEZZOGIORNO:
        bonus_attivi.append("mezzogiorno")
        punteggio += BONUS_TABLE["mezzogiorno"]["punti"]
    else:
        provincia = indicatori.get("provincia", "")
        if provincia in PROVINCE_CRATERE:
            bonus_attivi.append("zona_sismica")
            punteggio += BONUS_TABLE["zona_sismica"]["punti"]
        else:
            bonus_disponibili.append("mezzogiorno")
    
    # ─── VERIFICA BONUS SETTORIALI ────────────────
    
    finalita = form_extra.get("finalita_investimento", "")
    
    if finalita == "fotovoltaico":
        bonus_attivi.append("green_energy")
        punteggio += BONUS_TABLE["green_energy"]["punti"]
    elif finalita == "macchinari":
        bonus_attivi.append("industria_40")
        punteggio += BONUS_TABLE["industria_40"]["punti"]
    elif finalita == "internazionalizzazione":
        bonus_attivi.append("export")
        punteggio += BONUS_TABLE["export"]["punti"]
    elif finalita == "assunzioni":
        bonus_attivi.append("assunzione")
        punteggio += BONUS_TABLE["assunzione"]["punti"]
    elif finalita == "digitalizzazione":
        bonus_attivi.append("industria_40")
        punteggio += BONUS_TABLE["industria_40"]["punti"]
    else:
        bonus_disponibili.extend(["green_energy", "industria_40", "export", "assunzione"])
    
    # ─── VERIFICA BONUS AZIENDALI ─────────────────
    
    eta_mesi = indicatori.get("eta_impresa_mesi", 999)
    if eta_mesi is not None and eta_mesi <= 24:
        bonus_attivi.append("impresa_nuova")
        punteggio += BONUS_TABLE["impresa_nuova"]["punti"]
    else:
        bonus_disponibili.append("impresa_nuova")
    
    # De minimis
    de_minimis = form_extra.get("de_minimis", "no")
    if de_minimis == "no":
        bonus_attivi.append("no_de_minimis")
        punteggio += BONUS_TABLE["no_de_minimis"]["punti"]
    else:
        bonus_disponibili.append("no_de_minimis")
    
    # Forma giuridica cooperativa
    forma = impresa.get("forma_giuridica_normalizzata", "")
    if "Cooperativa" in forma or "Coop" in forma.upper():
        bonus_attivi.append("cooperativa")
        punteggio += BONUS_TABLE["cooperativa"]["punti"]
    
    # ─── CALCOLA PERCENTUALE E LIVELLO ────────────
    
    percentuale = min(round((punteggio / 100) * 100), 100)
    
    # Determina livello
    if percentuale >= 80:
        livello = "ECCELLENTE"
        livello_colore = "#00C851"
        livello_emoji = "🏆"
    elif percentuale >= 60:
        livello = "BUONO"
        livello_colore = "#4a9eff"
        livello_emoji = "✅"
    elif percentuale >= 40:
        livello = "MEDIO"
        livello_colore = "#FFB300"
        livello_emoji = "⚡"
    else:
        livello = "DA MIGLIORARE"
        livello_colore = "#FF6B6B"
        livello_emoji = "📈"
    
    # ─── GENERA SUGGERIMENTI PRIORITARI ───────────
    
    # Ordina bonus disponibili per impatto (punti decrescenti)
    suggerimenti = []
    for bonus_id in bonus_disponibili:
        if bonus_id in BONUS_TABLE:
            b = BONUS_TABLE[bonus_id].copy()
            b["id"] = bonus_id
            suggerimenti.append(b)
    
    suggerimenti.sort(key=lambda x: x["punti"], reverse=True)
    suggerimenti = suggerimenti[:4]  # Top 4 suggerimenti
    
    # Calcola punteggio potenziale se si applicano tutti i suggerimenti
    punti_potenziali = sum(s["punti"] for s in suggerimenti)
    punteggio_potenziale = min(punteggio + punti_potenziali, 100)
    percentuale_potenziale = min(round((punteggio_potenziale / 100) * 100), 100)
    
    # ─── DETTAGLIO BONUS ATTIVI ───────────────────
    
    bonus_attivi_dettaglio = []
    for bonus_id in bonus_attivi:
        if bonus_id in BONUS_TABLE:
            b = BONUS_TABLE[bonus_id].copy()
            b["id"] = bonus_id
            bonus_attivi_dettaglio.append(b)
    
    return {
        "punteggio": punteggio,
        "punteggio_max": 100,
        "percentuale": percentuale,
        "punteggio_potenziale": punteggio_potenziale,
        "percentuale_potenziale": percentuale_potenziale,
        "livello": livello,
        "livello_colore": livello_colore,
        "livello_emoji": livello_emoji,
        "bonus_attivi": bonus_attivi_dettaglio,
        "n_bonus_attivi": len(bonus_attivi),
        "suggerimenti": suggerimenti,
        "messaggio": _genera_messaggio_simulatore(percentuale, punteggio_potenziale, suggerimenti)
    }


def _genera_messaggio_simulatore(percentuale: int, punteggio_potenziale: int, suggerimenti: list) -> str:
    """Genera un messaggio motivazionale basato sul punteggio."""
    if percentuale >= 80:
        return f"🏆 Profilo eccellente! Sei tra il top 10% delle PMI italiane per accesso ai finanziamenti."
    elif percentuale >= 60:
        if suggerimenti:
            top = suggerimenti[0]
            return f"✅ Buon profilo! Con '{top['label']}' puoi salire a {punteggio_potenziale}/100 e sbloccare altri {len(suggerimenti)} bandi."
        return "✅ Buon profilo! Completa il form per scoprire altri bandi compatibili."
    elif percentuale >= 40:
        if suggerimenti:
            top = suggerimenti[0]
            return f"⚡ Profilo medio. '{top['label']}' (+{top['punti']} punti) potrebbe portarti a {punteggio_potenziale}/100."
        return "⚡ Profilo medio. Aggiungi più informazioni per migliorare il matching."
    else:
        return f"📈 Profilo da ottimizzare. Applicando i suggerimenti puoi raggiungere {punteggio_potenziale}/100 e accedere a molti più bandi."
