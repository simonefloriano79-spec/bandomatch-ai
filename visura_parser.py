"""
BandoMatch AI — Visura Camerale Parser
Estrae dati strutturati da PDF nativi di visure camerali (Infocamere/CCIAA)
Autore: Manus AI (Lead Software Engineer)
"""

import re
import json
import pdfplumber
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Optional


# ─────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────

def _clean(text: str) -> str:
    """Rimuove spazi multipli e newline inutili."""
    return re.sub(r'\s+', ' ', text).strip()

def _parse_date(raw: str) -> Optional[date]:
    """Tenta di parsare una data in vari formati italiani."""
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None

def _calc_age(birth_date: date) -> int:
    """Calcola l'età in anni interi dalla data di nascita."""
    today = date.today()
    return relativedelta(today, birth_date).years

def _calc_company_age_months(constitution_date: date) -> int:
    """Calcola l'età dell'impresa in mesi dalla data di costituzione."""
    today = date.today()
    delta = relativedelta(today, constitution_date)
    return delta.years * 12 + delta.months


# ─────────────────────────────────────────────
# ESTRAZIONE TESTO DAL PDF
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Estrae tutto il testo da un PDF nativo usando pdfplumber."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    return "\n".join(full_text)


# ─────────────────────────────────────────────
# PARSER CAMPI SPECIFICI
# ─────────────────────────────────────────────

def parse_ragione_sociale(text: str) -> Optional[str]:
    """Estrae la ragione sociale / denominazione dell'impresa."""
    patterns = [
        r'(?:Denominazione|Ragione sociale|Ditta)\s*[:\-]?\s*([A-Z][^\n]{2,80})',
        r'(?:DENOMINAZIONE|RAGIONE SOCIALE)\s*[:\-]?\s*([A-Z][^\n]{2,80})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _clean(m.group(1))
    return None

def parse_codice_fiscale(text: str) -> Optional[str]:
    """Estrae il codice fiscale / P.IVA dell'impresa."""
    m = re.search(r'(?:Codice fiscale|C\.F\.|CF|P\.IVA|Partita IVA)\s*[:\-]?\s*([0-9]{11}|[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z])', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: cerca un CF da 16 caratteri alfanumerici
    m = re.search(r'\b([A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z])\b', text)
    if m:
        return m.group(1)
    return None

def parse_forma_giuridica(text: str) -> Optional[str]:
    """Estrae la forma giuridica dell'impresa."""
    patterns = [
        r'(?:Forma giuridica|Natura giuridica)\s*[:\-]?\s*([A-Za-z\s\.]{3,60}?)(?:\n|$)',
        r'\b(S\.R\.L\.|SRL|S\.P\.A\.|SPA|S\.N\.C\.|SNC|S\.A\.S\.|SAS|SRLS|S\.R\.L\.S\.|Ditta individuale|Impresa individuale|Società cooperativa|Società a responsabilità limitata|Società per azioni)\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _clean(m.group(1))
    return None

def parse_ateco(text: str) -> list[dict]:
    """Estrae i codici ATECO con descrizione."""
    results = []
    # Pattern per codice ATECO (es. 62.01.00, 47.11, 10.1)
    pattern = r'(\d{2}\.\d{1,2}(?:\.\d{1,2})?)\s*[-–]?\s*([A-Za-zÀ-ÿ][^\n]{5,100})'
    matches = re.findall(pattern, text)
    seen = set()
    for code, desc in matches:
        if code not in seen:
            seen.add(code)
            results.append({
                "codice": code.strip(),
                "descrizione": _clean(desc),
                "sezione": code[:2]
            })
    return results[:5]  # Massimo 5 codici ATECO

def parse_sede_legale(text: str) -> dict:
    """Estrae indirizzo, comune, provincia e regione della sede legale."""
    result = {"indirizzo": None, "comune": None, "provincia": None, "regione": None, "cap": None}
    
    # Cerca blocco sede legale
    sede_block = re.search(
        r'(?:Sede legale|SEDE LEGALE)\s*[:\-]?\s*(.*?)(?=\n(?:Sede|Unità|Capitale|Soci|ATECO|$))',
        text, re.IGNORECASE | re.DOTALL
    )
    if sede_block:
        block = sede_block.group(1)
        # CAP
        cap_m = re.search(r'\b(\d{5})\b', block)
        if cap_m:
            result["cap"] = cap_m.group(1)
        # Provincia (2 lettere maiuscole tra parentesi o dopo comune)
        prov_m = re.search(r'\(([A-Z]{2})\)', block)
        if prov_m:
            result["provincia"] = prov_m.group(1)
        # Comune: prende solo la prima parola/frase prima di eventuali tag
        comune_m = re.search(r'(?:Comune|Città|Municipio)\s*[:\-]?\s*([A-Za-zÀ-ÿ\s\']{3,40}?)(?:\n|DATA|$)', block, re.IGNORECASE)
        if comune_m:
            result["comune"] = _clean(comune_m.group(1))
        # Indirizzo
        via_m = re.search(r'(?:Via|Viale|Corso|Piazza|Largo|Strada|Loc\.|Localit[àa])\s+[^\n]{5,80}', block, re.IGNORECASE)
        if via_m:
            result["indirizzo"] = _clean(via_m.group(0))
    
    # Fallback: cerca CAP e provincia nel testo generale
    if not result["cap"]:
        cap_m = re.search(r'\b(\d{5})\b', text)
        if cap_m:
            result["cap"] = cap_m.group(1)
    if not result["provincia"]:
        prov_m = re.search(r'\(([A-Z]{2})\)', text)
        if prov_m:
            result["provincia"] = prov_m.group(1)
    
    # Mappa provincia → regione
    result["regione"] = _provincia_to_regione(result.get("provincia"))
    
    return result

def parse_data_costituzione(text: str) -> Optional[dict]:
    """Estrae la data di costituzione e calcola l'età in mesi."""
    patterns = [
        r'(?:Data di costituzione|Data costituzione|Costituita il|Iscritta il|Data iscrizione)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})',
        r'(?:COSTITUZIONE|ISCRIZIONE)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            d = _parse_date(m.group(1))
            if d:
                age_months = _calc_company_age_months(d)
                return {
                    "data": d.strftime("%Y-%m-%d"),
                    "eta_mesi": age_months,
                    "eta_anni": age_months // 12
                }
    return None

def parse_capitale_sociale(text: str) -> Optional[float]:
    """Estrae il capitale sociale."""
    m = re.search(
        r'(?:Capitale sociale|Capitale)\s*[:\-]?\s*(?:Euro|EUR|€)?\s*([\d\.,]+)',
        text, re.IGNORECASE
    )
    if m:
        raw = m.group(1).replace('.', '').replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            pass
    return None

def parse_soci(text: str) -> list[dict]:
    """Estrae i soci con nome, quota e data di nascita se disponibile."""
    soci = []
    # Pattern per soci con quota
    pattern = r'([A-Z][A-Z\s\']{5,40})\s+(?:nato|nata)\s+(?:il\s+)?(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})?\s*[-–]?\s*(\d{1,3}(?:[,\.]\d{1,4})?)\s*%'
    matches = re.findall(pattern, text)
    for nome, data_nascita, quota in matches:
        # Pulizia nome: rimuove parole chiave spurie
        nome_clean = re.sub(r'\b(SOCI|TITOLARI|NATO|NATA|IL|E)\b', '', nome, flags=re.IGNORECASE).strip()
        nome_clean = re.sub(r'\s+', ' ', nome_clean).strip()
        socio = {
            "nome": nome_clean,
            "quota_percentuale": float(quota.replace(',', '.'))
        }
        if data_nascita:
            d = _parse_date(data_nascita)
            if d:
                socio["data_nascita"] = d.strftime("%Y-%m-%d")
                socio["eta_anni"] = _calc_age(d)
        soci.append(socio)
    
    # Fallback: cerca nomi con date di nascita senza quote
    if not soci:
        pattern2 = r'([A-Z][A-Z\s\']{5,40})\s+(?:nato|nata)\s+(?:a\s+\w+\s+)?il\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})'
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        for nome, data_nascita in matches2:
            d = _parse_date(data_nascita)
            socio = {"nome": _clean(nome)}
            if d:
                socio["data_nascita"] = d.strftime("%Y-%m-%d")
                socio["eta_anni"] = _calc_age(d)
            soci.append(socio)
    
    return soci[:10]  # Massimo 10 soci

def parse_fatturato(text: str) -> Optional[float]:
    """Estrae il fatturato annuo se presente nella visura."""
    m = re.search(
        r'(?:Fatturato|Ricavi|Volume d\'affari)\s*[:\-]?\s*(?:Euro|EUR|€)?\s*([\d\.,]+)',
        text, re.IGNORECASE
    )
    if m:
        raw = m.group(1).replace('.', '').replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            pass
    return None

def parse_numero_dipendenti(text: str) -> Optional[int]:
    """Estrae il numero di dipendenti se presente."""
    m = re.search(
        r'(?:Dipendenti|Addetti|N\.\s*dipendenti)\s*[:\-]?\s*(\d+)',
        text, re.IGNORECASE
    )
    if m:
        return int(m.group(1))
    return None


# ─────────────────────────────────────────────
# CALCOLI DERIVATI PER IL MATCHING
# ─────────────────────────────────────────────

def calc_percentuale_under35(soci: list[dict]) -> float:
    """
    Calcola la percentuale di quote societarie detenute da soci under 35.
    Se le quote non sono disponibili, usa il conteggio semplice.
    """
    if not soci:
        return 0.0
    
    soci_con_quota = [s for s in soci if "quota_percentuale" in s and "eta_anni" in s]
    
    if soci_con_quota:
        # Ponderazione per quote (metodo corretto per Abruzzo Micro Prestiti)
        quota_under35 = sum(s["quota_percentuale"] for s in soci_con_quota if s["eta_anni"] < 35)
        quota_totale = sum(s["quota_percentuale"] for s in soci_con_quota)
        if quota_totale > 0:
            return round((quota_under35 / quota_totale) * 100, 2)
    
    # Fallback: conteggio semplice
    soci_con_eta = [s for s in soci if "eta_anni" in s]
    if soci_con_eta:
        under35 = sum(1 for s in soci_con_eta if s["eta_anni"] < 35)
        return round((under35 / len(soci_con_eta)) * 100, 2)
    
    return 0.0

def calc_percentuale_donne(soci: list[dict]) -> float:
    """
    Stima la percentuale di quote detenute da donne.
    (Richiede campo 'genere' nei dati socio — spesso non presente nella visura base)
    """
    soci_con_genere = [s for s in soci if "genere" in s]
    if not soci_con_genere:
        return None  # Dato non disponibile dalla visura
    
    soci_con_quota = [s for s in soci_con_genere if "quota_percentuale" in s]
    if soci_con_quota:
        quota_donne = sum(s["quota_percentuale"] for s in soci_con_quota if s.get("genere") == "F")
        quota_totale = sum(s["quota_percentuale"] for s in soci_con_quota)
        if quota_totale > 0:
            return round((quota_donne / quota_totale) * 100, 2)
    
    donne = sum(1 for s in soci_con_genere if s.get("genere") == "F")
    return round((donne / len(soci_con_genere)) * 100, 2)


# ─────────────────────────────────────────────
# MAPPA PROVINCE → REGIONI
# ─────────────────────────────────────────────

PROVINCE_REGIONI = {
    "AQ": "Abruzzo", "CH": "Abruzzo", "PE": "Abruzzo", "TE": "Abruzzo",
    "MT": "Basilicata", "PZ": "Basilicata",
    "CZ": "Calabria", "CS": "Calabria", "KR": "Calabria", "RC": "Calabria", "VV": "Calabria",
    "AV": "Campania", "BN": "Campania", "CE": "Campania", "NA": "Campania", "SA": "Campania",
    "BO": "Emilia-Romagna", "FE": "Emilia-Romagna", "FC": "Emilia-Romagna", "MO": "Emilia-Romagna",
    "PR": "Emilia-Romagna", "PC": "Emilia-Romagna", "RA": "Emilia-Romagna", "RE": "Emilia-Romagna", "RN": "Emilia-Romagna",
    "GO": "Friuli-Venezia Giulia", "PN": "Friuli-Venezia Giulia", "TS": "Friuli-Venezia Giulia", "UD": "Friuli-Venezia Giulia",
    "FR": "Lazio", "LT": "Lazio", "RI": "Lazio", "RM": "Lazio", "VT": "Lazio",
    "GE": "Liguria", "IM": "Liguria", "SP": "Liguria", "SV": "Liguria",
    "BG": "Lombardia", "BS": "Lombardia", "CO": "Lombardia", "CR": "Lombardia", "LC": "Lombardia",
    "LO": "Lombardia", "MB": "Lombardia", "MI": "Lombardia", "MN": "Lombardia", "PV": "Lombardia",
    "SO": "Lombardia", "VA": "Lombardia",
    "AN": "Marche", "AP": "Marche", "FM": "Marche", "MC": "Marche", "PU": "Marche",
    "CB": "Molise", "IS": "Molise",
    "AL": "Piemonte", "AT": "Piemonte", "BI": "Piemonte", "CN": "Piemonte", "NO": "Piemonte",
    "TO": "Piemonte", "VB": "Piemonte", "VC": "Piemonte",
    "BA": "Puglia", "BT": "Puglia", "BR": "Puglia", "FG": "Puglia", "LE": "Puglia", "TA": "Puglia",
    "CA": "Sardegna", "CI": "Sardegna", "NU": "Sardegna", "OG": "Sardegna", "OR": "Sardegna",
    "OT": "Sardegna", "SS": "Sardegna", "VS": "Sardegna",
    "AG": "Sicilia", "CL": "Sicilia", "CT": "Sicilia", "EN": "Sicilia", "ME": "Sicilia",
    "PA": "Sicilia", "RG": "Sicilia", "SR": "Sicilia", "TP": "Sicilia",
    "AR": "Toscana", "FI": "Toscana", "GR": "Toscana", "LI": "Toscana", "LU": "Toscana",
    "MS": "Toscana", "PI": "Toscana", "PT": "Toscana", "PO": "Toscana", "SI": "Toscana",
    "BZ": "Trentino-Alto Adige", "TN": "Trentino-Alto Adige",
    "PG": "Umbria", "TR": "Umbria",
    "AO": "Valle d'Aosta",
    "BL": "Veneto", "PD": "Veneto", "RO": "Veneto", "TV": "Veneto", "VE": "Veneto", "VI": "Veneto", "VR": "Veneto",
}

def _provincia_to_regione(provincia: Optional[str]) -> Optional[str]:
    if not provincia:
        return None
    return PROVINCE_REGIONI.get(provincia.upper())


# ─────────────────────────────────────────────
# PARSER PRINCIPALE
# ─────────────────────────────────────────────

def parse_visura(pdf_path: str) -> dict:
    """
    Funzione principale: estrae tutti i dati strutturati da una visura camerale PDF nativa.
    Restituisce un dizionario JSON-serializzabile.
    """
    text = extract_text_from_pdf(pdf_path)
    
    # Estrazione campi base
    ragione_sociale = parse_ragione_sociale(text)
    codice_fiscale = parse_codice_fiscale(text)
    forma_giuridica = parse_forma_giuridica(text)
    ateco = parse_ateco(text)
    sede = parse_sede_legale(text)
    costituzione = parse_data_costituzione(text)
    capitale = parse_capitale_sociale(text)
    soci = parse_soci(text)
    fatturato = parse_fatturato(text)
    dipendenti = parse_numero_dipendenti(text)
    
    # Calcoli derivati per matching
    perc_under35 = calc_percentuale_under35(soci)
    perc_donne = calc_percentuale_donne(soci)
    
    # Codici ATECO primari (sezione)
    ateco_sezioni = list(set(a["sezione"] for a in ateco))
    
    # Forma giuridica normalizzata
    forma_norm = _normalizza_forma_giuridica(forma_giuridica)
    
    result = {
        "meta": {
            "parser_version": "1.0.0",
            "parsed_at": datetime.now().isoformat(),
            "source_file": pdf_path
        },
        "impresa": {
            "ragione_sociale": ragione_sociale,
            "codice_fiscale": codice_fiscale,
            "forma_giuridica": forma_giuridica,
            "forma_giuridica_normalizzata": forma_norm,
            "capitale_sociale": capitale,
            "fatturato": fatturato,
            "numero_dipendenti": dipendenti,
        },
        "sede_legale": sede,
        "costituzione": costituzione,
        "ateco": {
            "codici": ateco,
            "sezioni": ateco_sezioni,
            "codice_primario": ateco[0]["codice"] if ateco else None,
        },
        "soci": soci,
        "indicatori_matching": {
            "percentuale_soci_under35": perc_under35,
            "percentuale_soci_donne": perc_donne,
            "eta_impresa_mesi": costituzione["eta_mesi"] if costituzione else None,
            "regione": sede.get("regione"),
            "provincia": sede.get("provincia"),
            "forma_giuridica_normalizzata": forma_norm,
            "is_mezzogiorno": sede.get("regione") in [
                "Abruzzo", "Basilicata", "Calabria", "Campania",
                "Molise", "Puglia", "Sardegna", "Sicilia"
            ] if sede.get("regione") else None,
        }
    }
    
    return result

def _normalizza_forma_giuridica(raw: Optional[str]) -> Optional[str]:
    """Normalizza la forma giuridica in categorie standard."""
    if not raw:
        return None
    raw_up = raw.upper()
    if any(x in raw_up for x in ["S.R.L.S.", "SRLS"]):
        return "SRLS"
    if any(x in raw_up for x in ["S.R.L.", "SRL", "RESPONSABILITÀ LIMITATA"]):
        return "SRL"
    if any(x in raw_up for x in ["S.P.A.", "SPA", "PER AZIONI"]):
        return "SPA"
    if any(x in raw_up for x in ["S.N.C.", "SNC", "NOME COLLETTIVO"]):
        return "SNC"
    if any(x in raw_up for x in ["S.A.S.", "SAS", "ACCOMANDITA SEMPLICE"]):
        return "SAS"
    if any(x in raw_up for x in ["COOPERATIVA", "COOP"]):
        return "Cooperativa"
    if any(x in raw_up for x in ["INDIVIDUALE", "DITTA"]):
        return "Impresa individuale"
    if any(x in raw_up for x in ["LIBERO PROFESSIONISTA", "PROFESSIONISTA"]):
        return "Libera professione"
    return raw


# ─────────────────────────────────────────────
# VISURA DI TEST (SIMULATA)
# ─────────────────────────────────────────────

def create_sample_visura_text() -> str:
    """Crea un testo simulato di visura camerale per testing."""
    return """
CAMERA DI COMMERCIO INDUSTRIA ARTIGIANATO E AGRICOLTURA DI PESCARA
VISURA CAMERALE ORDINARIA

Denominazione: TECH SOLUTIONS ABRUZZO S.R.L.
Codice fiscale: 01234567890
Partita IVA: 01234567890
Forma giuridica: Società a responsabilità limitata
Numero REA: PE-123456

SEDE LEGALE
Via Roma, 45
65100 Pescara (PE)
Comune: Pescara

DATA DI COSTITUZIONE: 15/03/2023
Iscritta il: 15/03/2023

CAPITALE SOCIALE: Euro 10.000,00

ATTIVITÀ PREVALENTE (ATECO 2007)
62.01.00 - Produzione di software non connesso all'edizione
62.02.00 - Consulenza nel settore delle tecnologie dell'informatica

SOCI E TITOLARI
ROSSI MARCO nato il 12/05/1992 - 60%
BIANCHI LAURA nata il 23/08/1995 - 40%

Numero dipendenti: 3
"""

def test_parser_with_sample():
    """Testa il parser con una visura simulata."""
    import tempfile
    import os
    
    # Crea un PDF di test con pdfplumber non disponibile per testo diretto
    # Usiamo fpdf2 per creare un PDF di test
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        
        sample_text = create_sample_visura_text()
        for line in sample_text.split('\n'):
            pdf.cell(0, 5, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        
        test_pdf_path = "/home/ubuntu/bandomatch/test_visura.pdf"
        pdf.output(test_pdf_path)
        
        result = parse_visura(test_pdf_path)
        return result
    except Exception as e:
        # Fallback: testa direttamente sul testo
        text = create_sample_visura_text()
        return _parse_from_text(text)

def _parse_from_text(text: str) -> dict:
    """Versione del parser che accetta testo diretto (per testing)."""
    ragione_sociale = parse_ragione_sociale(text)
    codice_fiscale = parse_codice_fiscale(text)
    forma_giuridica = parse_forma_giuridica(text)
    ateco = parse_ateco(text)
    sede = parse_sede_legale(text)
    costituzione = parse_data_costituzione(text)
    capitale = parse_capitale_sociale(text)
    soci = parse_soci(text)
    fatturato = parse_fatturato(text)
    dipendenti = parse_numero_dipendenti(text)
    
    perc_under35 = calc_percentuale_under35(soci)
    perc_donne = calc_percentuale_donne(soci)
    ateco_sezioni = list(set(a["sezione"] for a in ateco))
    forma_norm = _normalizza_forma_giuridica(forma_giuridica)
    
    return {
        "meta": {"parser_version": "1.0.0", "parsed_at": datetime.now().isoformat()},
        "impresa": {
            "ragione_sociale": ragione_sociale,
            "codice_fiscale": codice_fiscale,
            "forma_giuridica": forma_giuridica,
            "forma_giuridica_normalizzata": forma_norm,
            "capitale_sociale": capitale,
            "fatturato": fatturato,
            "numero_dipendenti": dipendenti,
        },
        "sede_legale": sede,
        "costituzione": costituzione,
        "ateco": {
            "codici": ateco,
            "sezioni": ateco_sezioni,
            "codice_primario": ateco[0]["codice"] if ateco else None,
        },
        "soci": soci,
        "indicatori_matching": {
            "percentuale_soci_under35": perc_under35,
            "percentuale_soci_donne": perc_donne,
            "eta_impresa_mesi": costituzione["eta_mesi"] if costituzione else None,
            "regione": sede.get("regione"),
            "provincia": sede.get("provincia"),
            "forma_giuridica_normalizzata": forma_norm,
            "is_mezzogiorno": sede.get("regione") in [
                "Abruzzo", "Basilicata", "Calabria", "Campania",
                "Molise", "Puglia", "Sardegna", "Sicilia"
            ] if sede.get("regione") else None,
        }
    }


if __name__ == "__main__":
    print("=== BandoMatch AI — Visura Parser Test ===\n")
    result = test_parser_with_sample()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    # Salva il risultato
    with open("/home/ubuntu/bandomatch/parsed_visura_sample.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print("\n✅ Risultato salvato in parsed_visura_sample.json")
