from typing import Dict, List, Tuple
from datetime import datetime


def calcola_score(profilo: Dict, bando: Dict) -> Dict:
    """
    Calcola il matching score tra un profilo aziendale e un bando.
    
    Args:
        profilo (Dict): Dizionario con dati azienda
            - regione (str): Regione dell'azienda
            - ateco (str): Codice ATECO principale
            - investimento_annuale (float): Investimento annuale in euro
            - anno_costituzione (int): Anno di costituzione
            - fondo_perduto (bool): Se beneficia di fondo perduto
        
        bando (Dict): Dizionario con dati bando
            - regioni_ammesse (List[str]): Lista regioni eligibili
            - ateco_ammessi (List[str]): Lista ATECO eligibili (codici 2-5 caratteri)
            - investimento_min (float): Investimento minimo richiesto
            - investimento_max (float): Investimento massimo consentito
            - anni_costituzione_min (int): Anni minimi da costituzione
            - bonus_fondo_perduto (bool): Bonus se fondo perduto
    
    Returns:
        Dict: Contenente:
            - score (int): Score totale 0-100
            - motivazioni (List[str]): Motivi dell'assegnazione punti
    """
    
    score = 0
    motivazioni = []
    
    # VALIDAZIONE: Controlla se regione è ammessa
    if not _verifica_regione(profilo, bando):
        return {
            "score": 0,
            "motivazioni": ["Regione non ammessa dal bando"]
        }
    
    # PUNTEGGIO REGIONE: +20 punti
    score += 20
    motivazioni.append("Regione ammessa (+20 punti)")
    
    # PUNTEGGIO ATECO: +15 punti
    if _verifica_ateco(profilo, bando):
        score += 15
        motivazioni.append("Attività economica (ATECO) compatibile (+15 punti)")
    else:
        motivazioni.append("ATECO non perfettamente allineato con le preferenze del bando")
    
    # PUNTEGGIO INVESTIMENTO: +10 punti
    investimento_score, investimento_msg = _valuta_investimento(profilo, bando)
    if investimento_score > 0:
        score += investimento_score
        motivazioni.append(investimento_msg)
    else:
        motivazioni.append(investimento_msg)
    
    # PUNTEGGIO ANNO COSTITUZIONE: +10 punti
    anni_score, anni_msg = _valuta_anni_costituzione(profilo, bando)
    if anni_score > 0:
        score += anni_score
        motivazioni.append(anni_msg)
    else:
        motivazioni.append(anni_msg)
    
    # BONUS FONDO PERDUTO: fino a +20 punti
    bonus_score, bonus_msg = _valuta_bonus_fondo_perduto(profilo, bando)
    if bonus_score > 0:
        score += bonus_score
        motivazioni.append(bonus_msg)
    
    # Normalizza score tra 0 e 100
    score = min(score, 100)
    
    return {
        "score": int(score),
        "motivazioni": motivazioni
    }


def _verifica_regione(profilo: Dict, bando: Dict) -> bool:
    """
    Verifica se la regione dell'azienda è tra le regioni ammesse.
    
    Args:
        profilo (Dict): Dati azienda
        bando (Dict): Dati bando
    
    Returns:
        bool: True se regione ammessa, False altrimenti
    """
    regione = profilo.get("regione", "").strip().upper()
    regioni_ammesse = bando.get("regioni_ammesse", [])
    
    # Normalizza regioni ammesse
    regioni_ammesse = [r.strip().upper() for r in regioni_ammesse]
    
    if not regioni_ammesse:
        return True  # Se non ci sono restrizioni, ammette tutto
    
    return regione in regioni_ammesse


def _verifica_ateco(profilo: Dict, bando: Dict) -> bool:
    """
    Verifica compatibilità ATECO tra profilo e bando.
    Supporta matching esatto o parziale (2-5 caratteri).
    
    Args:
        profilo (Dict): Dati azienda
        bando (Dict): Dati bando
    
    Returns:
        bool: True se ATECO compatibile
    """
    ateco_azienda = str(profilo.get("ateco", "")).strip()
    ateco_ammessi = bando.get("ateco_ammessi", [])
    
    if not ateco_ammessi:
        return True  # Se non ci sono restrizioni
    
    if not ateco_azienda:
        return False
    
    # Normalizza ATECO ammessi
    ateco_ammessi = [str(a).strip() for a in ateco_ammessi]
    
    # Verifica match esatto
    if ateco_azienda in ateco_ammessi:
        return True
    
    # Verifica match parziale (primi N caratteri)
    for ateco_bando in ateco_ammessi:
        min_len = min(len(ateco_azienda), len(ateco_bando))
        if ateco_azienda[:min_len] == ateco_bando[:min_len]:
            return True
    
    return False


def _valuta_investimento(profilo: Dict, bando: Dict) -> Tuple[int, str]:
    """
    Valuta l'investimento annuale dell'azienda rispetto ai criteri del bando.
    
    Args:
        profilo (Dict): Dati azienda
        bando (Dict): Dati bando
    
    Returns:
        Tuple[int, str]: (punti assegnati, messaggio motivazione)
    """
    investimento = profilo.get("investimento_annuale", 0)
    investimento_min = bando.get("investimento_min", 0)
    investimento_max = bando.get("investimento_max", float('inf'))
    
    try:
        investimento = float(investimento)
        investimento_min = float(investimento_min)
        investimento_max = float(investimento_max)
    except (ValueError, TypeError):
        return 0, "Dati investimento non validi"
    
    if investimento < investimento_min:
        return 0, f"Investimento insufficiente (min: €{investimento_min:,.0f})"
    
    if investimento > investimento_max:
        return 0, f"Investimento supera il massimo (max: €{investimento_max:,.0f})"
    
    return 10, f"Investimento ammissibile: €{investimento:,.0f} (+10 punti)"


def _valuta_anni_costituzione(profilo: Dict, bando: Dict) -> Tuple[int, str]:
    """
    Valuta l'anzianità aziendale rispetto ai criteri del bando.
    
    Args:
        profilo (Dict): Dati azienda
        bando (Dict): Dati bando
    
    Returns:
        Tuple[int, str]: (punti assegnati, messaggio motivazione)
    """
    anno_costituzione = profilo.get("anno_costituzione")
    anni_min = bando.get("anni_costituzione_min", 0)
    
    try:
        anno_costituzione = int(anno_costituzione)
        anni_min = int(anni_min)
    except (ValueError, TypeError):
        return 0, "Anno di costituzione non valido"
    
    anno_attuale = datetime.now().year
    anni_attivita = anno_attuale - anno_costituzione
    
    if anni_attivita < anni_min:
        return 0, f"Anzianità insufficiente ({anni_attivita} anni, min: {anni_min})"
    
    return 10, f"Azienda costituita nel {anno_costituzione} ({anni_attivita} anni) (+10 punti)"


def _valuta_bonus_fondo_perduto(profilo: Dict, bando: Dict) -> Tuple[int, str]:
    """
    Assegna bonus se l'azienda beneficia di fondo perduto e il bando lo richiede/premia.
    
    Args:
        profilo (Dict): Dati azienda
        bando (Dict): Dati bando
    
    Returns:
        Tuple[int, str]: (punti assegnati fino a 20, messaggio motivazione)
    """
    ha_fondo_perduto = profilo.get("fondo_perduto", False)
    bonus_richiesto = bando.get("bonus_fondo_perduto", False)
    
    # Se il bando non premia il fondo perduto
    if not bonus_richiesto:
        return 0, ""
    
    # Se l'azienda ha fondo perduto, assegna bonus
    if ha_fondo_perduto:
        return 20, "Beneficiario di finanziamento agevolato (+20 punti bonus)"
    
    return 0, ""


def calcola_score_batch(profili: List[Dict], bando: Dict) -> List[Dict]:
    """
    Calcola score per molteplici profili rispetto a un singolo bando.
    Utile per ranking di aziende.
    
    Args:
        profili (List[Dict]): Lista di profili aziendali
        bando (Dict): Dati bando
    
    Returns:
        List[Dict]: Lista di risultati ordinati per score decrescente
    """
    risultati = []
    
    for i, profilo in enumerate(profili):
        result = calcola_score(profilo, bando)
        result["id_profilo"] = i
        risultati.append(result)
    
    # Ordina per score decrescente
    risultati.sort(key=lambda x: x["score"], reverse=True)
    
    return risultati
