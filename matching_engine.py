"""
BandoMatch AI — Matching Engine
Algoritmo di matching tra profilo impresa (da visura) e bandi di finanziamento.
Logica semaforo: VERDE / GIALLO / ROSSO / GRIGIO
Autore: Manus AI (Lead Software Engineer)
"""

import json
from typing import Optional
from datetime import date, datetime


# ─────────────────────────────────────────────
# COSTANTI SEMAFORO
# ─────────────────────────────────────────────

VERDE  = "VERDE"   # Match ≥ 80%: tutti i requisiti obbligatori soddisfatti
GIALLO = "GIALLO"  # Match 50-79%: requisiti principali OK ma con condizioni
ROSSO  = "ROSSO"   # Match < 50%: uno o più requisiti obbligatori non soddisfatti
GRIGIO = "GRIGIO"  # Dati insufficienti per calcolare il match


# ─────────────────────────────────────────────
# BLACKLIST ATECO DE MINIMIS (Reg. UE 2831/2023)
# Sezioni e codici esclusi dal regime de minimis
# ─────────────────────────────────────────────

ATECO_ESCLUSI_DE_MINIMIS = {
    "sezioni_escluse": [
        "01",  # Coltivazioni agricole e produzione di prodotti animali
        "02",  # Silvicoltura e utilizzo di aree forestali
        "03",  # Pesca e acquacoltura
    ],
    "codici_esclusi": [
        "10.1",  # Lavorazione e conservazione di carne
        "10.2",  # Lavorazione e conservazione di pesce
        "49.4",  # Trasporto di merci su strada (parzialmente)
    ],
    "note": "Basato su Regolamento (UE) 2023/2831 della Commissione del 13 dicembre 2023"
}

# Regioni del Mezzogiorno (per Resto al Sud 2.0)
REGIONI_MEZZOGIORNO = [
    "Abruzzo", "Basilicata", "Calabria", "Campania",
    "Molise", "Puglia", "Sardegna", "Sicilia"
]

# Aree cratere sismico Centro Italia (per Resto al Sud 2.0)
PROVINCE_CRATERE_SISMICO = ["RI", "MC", "AP", "PG"]


# ─────────────────────────────────────────────
# DATABASE BANDI (JSON strutturato)
# ─────────────────────────────────────────────

BANDI_DATABASE = [
    {
        "id": "resto_al_sud_2_0",
        "nome": "Resto al Sud 2.0 (Investire al Sud)",
        "ente": "Invitalia",
        "url": "https://www.invitalia.it/incentivi-e-strumenti/resto-al-sud-20",
        "stato": "ATTIVO",
        "data_apertura": "2025-10-15",
        "data_scadenza": None,  # A sportello senza scadenza
        "procedura": "sportello",
        "dotazione_totale": 356400000,
        "regioni_ammesse": REGIONI_MEZZOGIORNO + ["Lazio", "Marche", "Umbria"],  # Cratere sismico
        "province_extra": PROVINCE_CRATERE_SISMICO,
        "requisiti": {
            "eta_minima_soci": 18,
            "eta_massima_soci": 34,
            "condizione_occupazionale": ["inoccupato", "inattivo", "disoccupato", "working poor"],
            "forme_giuridiche_ammesse": ["Impresa individuale", "SNC", "SAS", "SRL", "SRLS", "Cooperativa", "Libera professione", "STP"],
            "forme_giuridiche_escluse": ["SPA"],
            "ateco_sezioni_escluse": ["01", "02", "03"],
            "eta_impresa_max_mesi": None,  # Nuove imprese o da costituire
        },
        "agevolazioni": {
            "voucher_avvio": 40000,
            "voucher_avvio_maggiorato": 50000,
            "percentuale_fondo_perduto_fino_120k": 75,
            "percentuale_fondo_perduto_120k_200k": 70,
            "massimale_investimento": 200000,
        },
        "requisiti_form_integrativo": [
            "condizione_occupazionale",
            "eta_soci_confermata"
        ],
        "descrizione": "Incentivo per l'avvio di nuove attività imprenditoriali nelle regioni del Mezzogiorno. Voucher fino a 50.000€ + contributo a fondo perduto fino al 75% per investimenti fino a 200.000€."
    },
    {
        "id": "abruzzo_micro_prestiti_giovani",
        "nome": "Abruzzo Micro Prestiti — Linea A (Giovani)",
        "ente": "FiRA S.p.A. - Regione Abruzzo",
        "url": "https://www.fira.it/fira-avviso-unico-abruzzo-micro-prestiti-apertura-maggio-2026chiusura-fino-a-esaurimento-risorse/",
        "stato": "IN_APERTURA",
        "data_apertura": "2026-05-12",
        "data_scadenza": None,  # Fino a esaurimento risorse
        "procedura": "sportello",
        "dotazione_totale": 19000000,
        "regioni_ammesse": ["Abruzzo"],
        "province_extra": [],
        "requisiti": {
            "eta_minima_soci": 18,
            "eta_massima_soci": 35,
            "percentuale_soci_under35_minima": 70.0,
            "forme_giuridiche_ammesse": ["Impresa individuale", "SNC", "SAS", "SRL", "SRLS", "Cooperativa", "Libera professione"],
            "forme_giuridiche_escluse": ["SPA"],
            "ateco_regime": "de_minimis",
            "eta_impresa_max_mesi": 24,
        },
        "agevolazioni": {
            "micro_prestito_min": 10000,
            "micro_prestito_max": 80000,
            "tasso_interesse": 0,
            "fondo_perduto_percentuale": 30,
            "fondo_perduto_max": 24000,
            "spesa_progetto_min": 13000,
            "spesa_progetto_max": 104000,
            "garanzie": "Nessuna",
        },
        "requisiti_form_integrativo": [],
        "descrizione": "Micro-prestito a tasso zero (10-80k€) + 30% fondo perduto per giovani under 35 che avviano nuove imprese in Abruzzo. Nessuna garanzia richiesta."
    },
    {
        "id": "abruzzo_micro_prestiti_donne",
        "nome": "Abruzzo Micro Prestiti — Linea B (Donne)",
        "ente": "FiRA S.p.A. - Regione Abruzzo",
        "url": "https://www.fira.it/fira-avviso-unico-abruzzo-micro-prestiti-apertura-maggio-2026chiusura-fino-a-esaurimento-risorse/",
        "stato": "IN_APERTURA",
        "data_apertura": "2026-05-12",
        "data_scadenza": None,
        "procedura": "sportello",
        "dotazione_totale": 19000000,
        "regioni_ammesse": ["Abruzzo"],
        "province_extra": [],
        "requisiti": {
            "genere_soci": "F",
            "percentuale_soci_donne_minima": 70.0,
            "forme_giuridiche_ammesse": ["Impresa individuale", "SNC", "SAS", "SRL", "SRLS", "Cooperativa", "Libera professione"],
            "forme_giuridiche_escluse": ["SPA"],
            "ateco_regime": "de_minimis",
            "eta_impresa_max_mesi": 24,
        },
        "agevolazioni": {
            "micro_prestito_min": 10000,
            "micro_prestito_max": 80000,
            "tasso_interesse": 0,
            "fondo_perduto_percentuale": 30,
            "fondo_perduto_max": 24000,
            "spesa_progetto_min": 13000,
            "spesa_progetto_max": 104000,
            "garanzie": "Nessuna",
        },
        "requisiti_form_integrativo": ["genere_soci_confermato"],
        "descrizione": "Micro-prestito a tasso zero (10-80k€) + 30% fondo perduto per imprese a prevalenza femminile (≥70% quote) in Abruzzo. Nessuna garanzia richiesta."
    },
    {
        "id": "abruzzo_digitalizzazione_pmi",
        "nome": "PR FESR Abruzzo — Digitalizzazione PMI (Azione 1.2.2.1)",
        "ente": "Regione Abruzzo / FiRA",
        "url": "https://www.fira.it/abruzzo-coesione-pubblicata-la-scheda-tecnica-del-bando-fesr-per-la-digitalizzazione-delle-pmi/",
        "stato": "IN_PREPARAZIONE",
        "data_apertura": None,
        "data_scadenza": None,
        "procedura": "concessorio",
        "dotazione_totale": 10000000,
        "regioni_ammesse": ["Abruzzo"],
        "province_extra": [],
        "requisiti": {
            "forme_giuridiche_ammesse": ["Impresa individuale", "SNC", "SAS", "SRL", "SRLS", "SPA", "Cooperativa"],
            "forme_giuridiche_escluse": [],
            "ateco_regime": "de_minimis",
            "eta_impresa_max_mesi": None,
            "dimensione": "PMI",
        },
        "agevolazioni": {
            "percentuale_fondo_perduto": 70,
            "anticipo_possibile": 40,
            "regime_aiuti": "de minimis (Reg. UE 2023/2831)",
        },
        "requisiti_form_integrativo": [],
        "descrizione": "Contributo a fondo perduto fino al 70% per digitalizzazione PMI abruzzesi: e-commerce, cybersecurity, marketing digitale, software gestionale."
    },
    {
        "id": "decontribuzione_sud",
        "nome": "Decontribuzione Sud",
        "ente": "INPS / Governo Italiano",
        "url": "https://www.inps.it/",
        "stato": "ATTIVO",
        "data_apertura": "2021-01-01",
        "data_scadenza": "2029-12-31",
        "procedura": "automatico",
        "dotazione_totale": None,
        "regioni_ammesse": REGIONI_MEZZOGIORNO,
        "province_extra": [],
        "requisiti": {
            "forme_giuridiche_ammesse": ["Tutti"],
            "forme_giuridiche_escluse": [],
            "ateco_sezioni_escluse": [],
            "eta_impresa_max_mesi": None,
            "dipendenti_richiesti": True,
        },
        "agevolazioni": {
            "tipologia": "Sgravio contributivo",
            "percentuale_sgravio": 30,
            "note": "Sgravio del 30% sui contributi previdenziali per dipendenti nelle regioni del Mezzogiorno",
        },
        "requisiti_form_integrativo": [],
        "descrizione": "Sgravio contributivo del 30% per imprese con dipendenti nelle regioni del Mezzogiorno. Valido fino al 2029."
    }
]


# ─────────────────────────────────────────────
# FUNZIONI DI VERIFICA REQUISITI
# ─────────────────────────────────────────────

def check_regione(profilo: dict, bando: dict) -> dict:
    """Verifica se la regione dell'impresa è ammessa dal bando."""
    regione = profilo.get("indicatori_matching", {}).get("regione")
    provincia = profilo.get("indicatori_matching", {}).get("provincia")
    
    if not regione:
        return {"ok": None, "motivo": "Regione non determinabile dalla visura", "bloccante": True}
    
    regioni_ammesse = bando.get("regioni_ammesse", [])
    province_extra = bando.get("province_extra", [])
    
    if regione in regioni_ammesse:
        return {"ok": True, "motivo": f"Regione {regione} ammessa"}
    
    if provincia and provincia in province_extra:
        return {"ok": True, "motivo": f"Provincia {provincia} ammessa (area speciale)"}
    
    return {"ok": False, "motivo": f"Regione {regione} NON ammessa dal bando", "bloccante": True}

def check_ateco(profilo: dict, bando: dict) -> dict:
    """Verifica se i codici ATECO dell'impresa sono ammessi."""
    ateco_sezioni = profilo.get("ateco", {}).get("sezioni", [])
    codice_primario = profilo.get("ateco", {}).get("codice_primario")
    
    if not ateco_sezioni and not codice_primario:
        return {"ok": None, "motivo": "Codice ATECO non trovato nella visura", "bloccante": True}
    
    req = bando.get("requisiti", {})
    
    # Controlla sezioni escluse specifiche del bando
    sezioni_escluse_bando = req.get("ateco_sezioni_escluse", [])
    for sezione in ateco_sezioni:
        if sezione in sezioni_escluse_bando:
            return {"ok": False, "motivo": f"Sezione ATECO {sezione} esclusa dal bando", "bloccante": True}
    
    # Controlla regime de minimis
    if req.get("ateco_regime") == "de_minimis":
        sezioni_escluse_dm = ATECO_ESCLUSI_DE_MINIMIS["sezioni_escluse"]
        for sezione in ateco_sezioni:
            if sezione in sezioni_escluse_dm:
                return {"ok": False, "motivo": f"Sezione ATECO {sezione} esclusa dal regime de minimis (Reg. UE 2831/2023)", "bloccante": True}
    
    return {"ok": True, "motivo": f"Codice ATECO {codice_primario} ammesso"}

def check_forma_giuridica(profilo: dict, bando: dict) -> dict:
    """Verifica se la forma giuridica è ammessa."""
    forma = profilo.get("impresa", {}).get("forma_giuridica_normalizzata")
    
    if not forma:
        return {"ok": None, "motivo": "Forma giuridica non determinabile", "bloccante": False}
    
    req = bando.get("requisiti", {})
    ammesse = req.get("forme_giuridiche_ammesse", [])
    escluse = req.get("forme_giuridiche_escluse", [])
    
    if "Tutti" in ammesse:
        return {"ok": True, "motivo": "Tutte le forme giuridiche ammesse"}
    
    if forma in escluse:
        return {"ok": False, "motivo": f"Forma giuridica {forma} ESCLUSA dal bando", "bloccante": True}
    
    if forma in ammesse:
        return {"ok": True, "motivo": f"Forma giuridica {forma} ammessa"}
    
    # Verifica parziale (es. "SRL" match con "Società a responsabilità limitata")
    for a in ammesse:
        if forma.upper() in a.upper() or a.upper() in forma.upper():
            return {"ok": True, "motivo": f"Forma giuridica {forma} compatibile con {a}"}
    
    return {"ok": None, "motivo": f"Forma giuridica {forma} non verificabile con certezza", "bloccante": False}

def check_eta_impresa(profilo: dict, bando: dict) -> dict:
    """Verifica l'età dell'impresa rispetto al limite del bando."""
    eta_mesi = profilo.get("indicatori_matching", {}).get("eta_impresa_mesi")
    max_mesi = bando.get("requisiti", {}).get("eta_impresa_max_mesi")
    
    if max_mesi is None:
        return {"ok": True, "motivo": "Nessun limite di età impresa per questo bando"}
    
    if eta_mesi is None:
        return {"ok": None, "motivo": "Data di costituzione non trovata nella visura", "bloccante": False}
    
    if eta_mesi <= max_mesi:
        return {"ok": True, "motivo": f"Impresa di {eta_mesi} mesi (limite: {max_mesi} mesi)"}
    
    return {"ok": False, "motivo": f"Impresa troppo vecchia: {eta_mesi} mesi (limite: {max_mesi} mesi)", "bloccante": True}

def check_eta_soci(profilo: dict, bando: dict) -> dict:
    """Verifica l'età dei soci rispetto ai requisiti del bando."""
    soci = profilo.get("soci", [])
    req = bando.get("requisiti", {})
    
    eta_min = req.get("eta_minima_soci")
    eta_max = req.get("eta_massima_soci")
    perc_under35_min = req.get("percentuale_soci_under35_minima")
    
    if eta_min is None and eta_max is None and perc_under35_min is None:
        return {"ok": True, "motivo": "Nessun requisito di età soci per questo bando"}
    
    soci_con_eta = [s for s in soci if "eta_anni" in s]
    
    if not soci_con_eta:
        return {"ok": None, "motivo": "Date di nascita soci non trovate nella visura — dato richiesto", "bloccante": False}
    
    # Verifica percentuale under 35 ponderata per quote
    if perc_under35_min is not None:
        perc_under35 = profilo.get("indicatori_matching", {}).get("percentuale_soci_under35", 0)
        if perc_under35 >= perc_under35_min:
            return {"ok": True, "motivo": f"{perc_under35:.1f}% quote detenute da soci under 35 (minimo: {perc_under35_min}%)"}
        else:
            return {"ok": False, "motivo": f"Solo {perc_under35:.1f}% quote under 35 (richiesto: ≥{perc_under35_min}%)", "bloccante": True}
    
    # Verifica età massima del titolare/socio principale
    if eta_max is not None:
        soci_ammessi = [s for s in soci_con_eta if s["eta_anni"] <= eta_max]
        if not soci_ammessi:
            return {"ok": False, "motivo": f"Nessun socio ha meno di {eta_max} anni", "bloccante": True}
        return {"ok": True, "motivo": f"{len(soci_ammessi)} socio/i con età ≤ {eta_max} anni"}
    
    return {"ok": True, "motivo": "Requisiti età soci soddisfatti"}

def check_stato_bando(bando: dict) -> dict:
    """Verifica lo stato del bando (attivo, in apertura, scaduto)."""
    stato = bando.get("stato")
    data_apertura = bando.get("data_apertura")
    data_scadenza = bando.get("data_scadenza")
    today = date.today()
    
    if stato == "ATTIVO":
        if data_scadenza:
            d_scad = datetime.strptime(data_scadenza, "%Y-%m-%d").date()
            giorni_alla_scadenza = (d_scad - today).days
            if giorni_alla_scadenza < 0:
                return {"ok": False, "motivo": "Bando scaduto", "warning": False}
            if giorni_alla_scadenza <= 30:
                return {"ok": True, "motivo": f"Bando in scadenza tra {giorni_alla_scadenza} giorni!", "warning": True}
        return {"ok": True, "motivo": "Bando attivo"}
    
    if stato == "IN_APERTURA":
        if data_apertura:
            d_ap = datetime.strptime(data_apertura, "%Y-%m-%d").date()
            giorni_all_apertura = (d_ap - today).days
            if giorni_all_apertura > 0:
                return {"ok": True, "motivo": f"Bando apre tra {giorni_all_apertura} giorni ({data_apertura})", "warning": True}
        return {"ok": True, "motivo": "Bando in apertura imminente", "warning": True}
    
    if stato == "IN_PREPARAZIONE":
        return {"ok": True, "motivo": "Bando in preparazione — data apertura non ancora definita", "warning": True}
    
    if stato == "CHIUSO":
        return {"ok": False, "motivo": "Bando chiuso", "warning": False}
    
    return {"ok": True, "motivo": f"Stato bando: {stato}"}


# ─────────────────────────────────────────────
# CALCOLO SCORE E SEMAFORO
# ─────────────────────────────────────────────

def calcola_semaforo(checks: dict) -> dict:
    """
    Calcola il colore del semaforo basandosi sui risultati dei check.
    
    Logica:
    - Se qualsiasi check bloccante è ROSSO → ROSSO
    - Se qualsiasi check è GRIGIO (dato mancante) → GRIGIO
    - Se tutti i check obbligatori sono VERDI ma ci sono warning → GIALLO
    - Se tutti i check sono VERDI → VERDE
    """
    
    bloccanti_falliti = []
    dati_mancanti = []
    warning = []
    ok_count = 0
    total_count = 0
    
    for nome_check, risultato in checks.items():
        if risultato is None:
            continue
        
        total_count += 1
        ok = risultato.get("ok")
        motivo = risultato.get("motivo", "")
        is_bloccante = risultato.get("bloccante", False)
        is_warning = risultato.get("warning", False)
        
        if ok is False and is_bloccante:
            bloccanti_falliti.append(f"❌ {nome_check}: {motivo}")
        elif ok is None:
            dati_mancanti.append(f"⚪ {nome_check}: {motivo}")
        elif ok is True and is_warning:
            warning.append(f"⚠️ {nome_check}: {motivo}")
            ok_count += 1
        elif ok is True:
            ok_count += 1
    
    # Determina colore semaforo
    if bloccanti_falliti:
        colore = ROSSO
        score = 0
    elif dati_mancanti:
        colore = GRIGIO
        score = (ok_count / total_count * 100) if total_count > 0 else 0
    elif warning:
        colore = GIALLO
        score = (ok_count / total_count * 100) if total_count > 0 else 0
    else:
        colore = VERDE
        score = 100
    
    return {
        "colore": colore,
        "score": round(score, 1),
        "bloccanti_falliti": bloccanti_falliti,
        "dati_mancanti": dati_mancanti,
        "warning": warning,
        "ok_count": ok_count,
        "total_count": total_count
    }


# ─────────────────────────────────────────────
# MOTORE DI MATCHING PRINCIPALE
# ─────────────────────────────────────────────

def match_impresa_bando(profilo: dict, bando: dict) -> dict:
    """
    Esegue il matching tra il profilo impresa e un singolo bando.
    Restituisce il risultato con semaforo, score e dettagli.
    """
    
    # PRE-FILTRO BLOCCANTE: Regione e ATECO
    check_reg = check_regione(profilo, bando)
    if check_reg.get("ok") is False:
        return {
            "bando_id": bando["id"],
            "bando_nome": bando["nome"],
            "ente": bando["ente"],
            "semaforo": ROSSO,
            "score": 0,
            "motivo_principale": check_reg["motivo"],
            "checks": {"regione": check_reg},
            "agevolazioni": bando.get("agevolazioni", {}),
            "descrizione": bando.get("descrizione", ""),
            "url": bando.get("url", ""),
            "stato_bando": bando.get("stato"),
            "form_integrativo_richiesto": bando.get("requisiti_form_integrativo", [])
        }
    
    check_atc = check_ateco(profilo, bando)
    if check_atc.get("ok") is False:
        return {
            "bando_id": bando["id"],
            "bando_nome": bando["nome"],
            "ente": bando["ente"],
            "semaforo": ROSSO,
            "score": 0,
            "motivo_principale": check_atc["motivo"],
            "checks": {"regione": check_reg, "ateco": check_atc},
            "agevolazioni": bando.get("agevolazioni", {}),
            "descrizione": bando.get("descrizione", ""),
            "url": bando.get("url", ""),
            "stato_bando": bando.get("stato"),
            "form_integrativo_richiesto": bando.get("requisiti_form_integrativo", [])
        }
    
    # CHECK COMPLETI
    checks = {
        "regione": check_reg,
        "ateco": check_atc,
        "forma_giuridica": check_forma_giuridica(profilo, bando),
        "eta_impresa": check_eta_impresa(profilo, bando),
        "eta_soci": check_eta_soci(profilo, bando),
        "stato_bando": check_stato_bando(bando),
    }
    
    semaforo_result = calcola_semaforo(checks)
    
    # Motivo principale (primo problema trovato)
    motivo_principale = None
    if semaforo_result["bloccanti_falliti"]:
        motivo_principale = semaforo_result["bloccanti_falliti"][0]
    elif semaforo_result["dati_mancanti"]:
        motivo_principale = f"Dati mancanti: {semaforo_result['dati_mancanti'][0]}"
    elif semaforo_result["warning"]:
        motivo_principale = semaforo_result["warning"][0]
    else:
        motivo_principale = "✅ Tutti i requisiti verificati soddisfatti"
    
    return {
        "bando_id": bando["id"],
        "bando_nome": bando["nome"],
        "ente": bando["ente"],
        "semaforo": semaforo_result["colore"],
        "score": semaforo_result["score"],
        "motivo_principale": motivo_principale,
        "checks": checks,
        "semaforo_dettaglio": semaforo_result,
        "agevolazioni": bando.get("agevolazioni", {}),
        "descrizione": bando.get("descrizione", ""),
        "url": bando.get("url", ""),
        "stato_bando": bando.get("stato"),
        "form_integrativo_richiesto": bando.get("requisiti_form_integrativo", [])
    }

def match_tutti_bandi(profilo: dict, bandi: list = None) -> dict:
    """
    Esegue il matching del profilo impresa con tutti i bandi nel database.
    Restituisce i risultati ordinati per score decrescente.
    """
    if bandi is None:
        bandi = BANDI_DATABASE
    
    risultati = []
    for bando in bandi:
        risultato = match_impresa_bando(profilo, bando)
        risultati.append(risultato)
    
    # Ordina: VERDE → GIALLO → GRIGIO → ROSSO, poi per score decrescente
    ordine_semaforo = {VERDE: 0, GIALLO: 1, GRIGIO: 2, ROSSO: 3}
    risultati.sort(key=lambda x: (ordine_semaforo.get(x["semaforo"], 4), -x["score"]))
    
    # Statistiche
    conteggio = {VERDE: 0, GIALLO: 0, GRIGIO: 0, ROSSO: 0}
    for r in risultati:
        conteggio[r["semaforo"]] = conteggio.get(r["semaforo"], 0) + 1
    
    # Valore potenziale massimo (somma massimali bandi VERDE + GIALLO)
    valore_potenziale = 0
    for r in risultati:
        if r["semaforo"] in [VERDE, GIALLO]:
            agev = r.get("agevolazioni", {})
            massimale = agev.get("massimale_investimento") or agev.get("spesa_progetto_max") or 0
            valore_potenziale += massimale
    
    return {
        "profilo_impresa": {
            "ragione_sociale": profilo.get("impresa", {}).get("ragione_sociale"),
            "regione": profilo.get("indicatori_matching", {}).get("regione"),
            "ateco_primario": profilo.get("ateco", {}).get("codice_primario"),
            "forma_giuridica": profilo.get("impresa", {}).get("forma_giuridica_normalizzata"),
        },
        "statistiche": {
            "totale_bandi_analizzati": len(risultati),
            "verde": conteggio[VERDE],
            "giallo": conteggio[GIALLO],
            "grigio": conteggio[GRIGIO],
            "rosso": conteggio[ROSSO],
            "valore_potenziale_massimo": valore_potenziale,
        },
        "risultati": risultati,
        "timestamp": datetime.now().isoformat()
    }


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Carica il profilo dalla visura parsata
    try:
        with open("/home/ubuntu/bandomatch/parsed_visura_sample.json", "r", encoding="utf-8") as f:
            profilo = json.load(f)
    except FileNotFoundError:
        # Profilo di test inline
        profilo = {
            "impresa": {
                "ragione_sociale": "TECH SOLUTIONS ABRUZZO S.R.L.",
                "forma_giuridica_normalizzata": "SRL",
            },
            "sede_legale": {"regione": "Abruzzo", "provincia": "PE"},
            "costituzione": {"data": "2023-03-15", "eta_mesi": 25, "eta_anni": 2},
            "ateco": {"codici": [{"codice": "62.01.00", "sezione": "62"}], "sezioni": ["62"], "codice_primario": "62.01.00"},
            "soci": [
                {"nome": "ROSSI MARCO", "quota_percentuale": 60.0, "eta_anni": 33},
                {"nome": "BIANCHI LAURA", "quota_percentuale": 40.0, "eta_anni": 30}
            ],
            "indicatori_matching": {
                "percentuale_soci_under35": 100.0,
                "percentuale_soci_donne": None,
                "eta_impresa_mesi": 25,
                "regione": "Abruzzo",
                "provincia": "PE",
                "forma_giuridica_normalizzata": "SRL",
                "is_mezzogiorno": True
            }
        }
    
    print("=== BandoMatch AI — Matching Engine Test ===\n")
    risultati = match_tutti_bandi(profilo)
    
    print(f"Impresa: {risultati['profilo_impresa']['ragione_sociale']}")
    print(f"Regione: {risultati['profilo_impresa']['regione']}")
    print(f"ATECO: {risultati['profilo_impresa']['ateco_primario']}")
    print(f"\nBandi analizzati: {risultati['statistiche']['totale_bandi_analizzati']}")
    print(f"🟢 VERDE: {risultati['statistiche']['verde']}")
    print(f"🟡 GIALLO: {risultati['statistiche']['giallo']}")
    print(f"⚪ GRIGIO: {risultati['statistiche']['grigio']}")
    print(f"🔴 ROSSO: {risultati['statistiche']['rosso']}")
    print(f"💰 Valore potenziale: €{risultati['statistiche']['valore_potenziale_massimo']:,.0f}")
    
    print("\n--- DETTAGLIO BANDI ---")
    for r in risultati["risultati"]:
        emoji = {"VERDE": "🟢", "GIALLO": "🟡", "GRIGIO": "⚪", "ROSSO": "🔴"}.get(r["semaforo"], "❓")
        print(f"\n{emoji} {r['semaforo']} ({r['score']}%) — {r['bando_nome']}")
        print(f"   Ente: {r['ente']}")
        print(f"   {r['motivo_principale']}")
    
    # Salva risultati
    with open("/home/ubuntu/bandomatch/matching_results.json", "w", encoding="utf-8") as f:
        json.dump(risultati, f, indent=2, ensure_ascii=False, default=str)
    print("\n✅ Risultati salvati in matching_results.json")
