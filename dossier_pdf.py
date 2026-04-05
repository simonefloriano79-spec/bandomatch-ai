"""
BandoMatch AI — Generatore Dossier PDF
Genera un Dossier di Affinità professionale in PDF per ogni analisi,
scaricabile dopo il pagamento. Include:
- Profilo impresa estratto dalla visura
- Semafori dettagliati per ogni bando compatibile
- Simulatore punteggio con suggerimenti
- Piano d'azione personalizzato
- Istruzioni per la domanda
"""

import os
import io
import json
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import (
    HexColor, white, black, Color
)
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

logger = logging.getLogger(__name__)

# ── Colori Brand BandoMatch AI ─────────────────────────────────────────────────
VIOLA = HexColor("#7C3AED")
VIOLA_CHIARO = HexColor("#A78BFA")
VERDE = HexColor("#10B981")
GIALLO = HexColor("#F59E0B")
ROSSO = HexColor("#EF4444")
GRIGIO = HexColor("#6B7280")
GRIGIO_CHIARO = HexColor("#F3F4F6")
GRIGIO_SCURO = HexColor("#1F2937")
BLU_NOTTE = HexColor("#0F172A")
BIANCO = white

SEMAFORO_COLORI = {
    "verde": VERDE,
    "giallo": GIALLO,
    "rosso": ROSSO,
    "grigio": GRIGIO
}

SEMAFORO_EMOJI = {
    "verde": "✅",
    "giallo": "⚠️",
    "rosso": "❌",
    "grigio": "❓"
}

SEMAFORO_TESTO = {
    "verde": "COMPATIBILE",
    "giallo": "PARZIALMENTE COMPATIBILE",
    "rosso": "NON COMPATIBILE",
    "grigio": "DATI INSUFFICIENTI"
}


def _stili():
    """Definisce gli stili tipografici del documento."""
    styles = getSampleStyleSheet()

    stili = {
        "titolo_doc": ParagraphStyle(
            "titolo_doc",
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=BIANCO,
            alignment=TA_CENTER,
            spaceAfter=6
        ),
        "sottotitolo_doc": ParagraphStyle(
            "sottotitolo_doc",
            fontName="Helvetica",
            fontSize=12,
            textColor=VIOLA_CHIARO,
            alignment=TA_CENTER,
            spaceAfter=4
        ),
        "sezione": ParagraphStyle(
            "sezione",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=VIOLA,
            spaceBefore=16,
            spaceAfter=8,
            borderPad=4
        ),
        "corpo": ParagraphStyle(
            "corpo",
            fontName="Helvetica",
            fontSize=10,
            textColor=GRIGIO_SCURO,
            spaceAfter=4,
            leading=14,
            alignment=TA_JUSTIFY
        ),
        "corpo_bold": ParagraphStyle(
            "corpo_bold",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=GRIGIO_SCURO,
            spaceAfter=4
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica",
            fontSize=9,
            textColor=GRIGIO,
            spaceAfter=2
        ),
        "valore": ParagraphStyle(
            "valore",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=GRIGIO_SCURO,
            spaceAfter=6
        ),
        "bando_titolo": ParagraphStyle(
            "bando_titolo",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=GRIGIO_SCURO,
            spaceAfter=4
        ),
        "suggerimento": ParagraphStyle(
            "suggerimento",
            fontName="Helvetica",
            fontSize=9,
            textColor=HexColor("#374151"),
            spaceAfter=3,
            leftIndent=12,
            leading=13
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=GRIGIO,
            alignment=TA_CENTER
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=GRIGIO,
            alignment=TA_JUSTIFY,
            leading=11
        )
    }
    return stili


def _header_pagina(canvas, doc):
    """Disegna l'header su ogni pagina."""
    canvas.saveState()
    # Barra viola in alto
    canvas.setFillColor(VIOLA)
    canvas.rect(0, A4[1] - 1.2 * cm, A4[0], 1.2 * cm, fill=1, stroke=0)
    # Logo testuale
    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(BIANCO)
    canvas.drawString(1.5 * cm, A4[1] - 0.85 * cm, "BandoMatch AI")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(VIOLA_CHIARO)
    canvas.drawRightString(A4[0] - 1.5 * cm, A4[1] - 0.85 * cm,
                           f"Dossier di Affinità — {datetime.now().strftime('%d/%m/%Y')}")
    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIGIO)
    canvas.drawCentredString(A4[0] / 2, 0.8 * cm,
                             f"Pagina {doc.page} — Documento riservato — bandomatch.ai")
    canvas.restoreState()


def genera_dossier(
    dati_impresa: dict,
    risultati_matching: list[dict],
    simulatore: dict = None,
    output_path: str = None
) -> bytes:
    """
    Genera il Dossier PDF completo.

    Args:
        dati_impresa: dati estratti dalla visura camerale
        risultati_matching: lista risultati del matching con semafori
        simulatore: dati del simulatore punteggio (opzionale)
        output_path: percorso file di output (opzionale, altrimenti restituisce bytes)

    Returns:
        bytes del PDF generato
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=1.5 * cm
    )

    stili = _stili()
    elementi = []

    # ── COPERTINA ──────────────────────────────────────────────────────────────
    elementi.append(Spacer(1, 1 * cm))

    # Box copertina
    nome_impresa = dati_impresa.get("ragione_sociale", "Impresa")
    data_gen = datetime.now().strftime("%d %B %Y")

    copertina_data = [
        [Paragraph("DOSSIER DI AFFINITÀ", stili["titolo_doc"])],
        [Paragraph("Finanziamenti Pubblici Compatibili", stili["sottotitolo_doc"])],
        [Spacer(1, 0.3 * cm)],
        [Paragraph(f"<b>{nome_impresa}</b>", ParagraphStyle(
            "nome_imp", fontName="Helvetica-Bold", fontSize=16,
            textColor=BIANCO, alignment=TA_CENTER
        ))],
        [Paragraph(f"Generato il {data_gen}", ParagraphStyle(
            "data_gen", fontName="Helvetica", fontSize=10,
            textColor=VIOLA_CHIARO, alignment=TA_CENTER
        ))]
    ]

    tabella_copertina = Table(copertina_data, colWidths=[17 * cm])
    tabella_copertina.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLU_NOTTE),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    elementi.append(tabella_copertina)
    elementi.append(Spacer(1, 0.5 * cm))

    # Statistiche rapide
    n_verdi = sum(1 for r in risultati_matching if r.get("semaforo") == "verde")
    n_gialli = sum(1 for r in risultati_matching if r.get("semaforo") == "giallo")
    n_rossi = sum(1 for r in risultati_matching if r.get("semaforo") == "rosso")
    valore_potenziale = sum(
        r.get("massimale_euro", 0) or 0
        for r in risultati_matching
        if r.get("semaforo") in ["verde", "giallo"]
    )

    stats_data = [
        [
            Paragraph(f"<b>{n_verdi}</b><br/>Compatibili", ParagraphStyle(
                "stat", fontName="Helvetica-Bold", fontSize=18,
                textColor=VERDE, alignment=TA_CENTER
            )),
            Paragraph(f"<b>{n_gialli}</b><br/>Parziali", ParagraphStyle(
                "stat", fontName="Helvetica-Bold", fontSize=18,
                textColor=GIALLO, alignment=TA_CENTER
            )),
            Paragraph(f"<b>{n_rossi}</b><br/>Non compatibili", ParagraphStyle(
                "stat", fontName="Helvetica-Bold", fontSize=18,
                textColor=ROSSO, alignment=TA_CENTER
            )),
            Paragraph(f"<b>€{valore_potenziale:,.0f}</b><br/>Valore potenziale", ParagraphStyle(
                "stat", fontName="Helvetica-Bold", fontSize=14,
                textColor=VIOLA, alignment=TA_CENTER
            ))
        ]
    ]

    tabella_stats = Table(stats_data, colWidths=[4.25 * cm] * 4)
    tabella_stats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIGIO_CHIARO),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    elementi.append(tabella_stats)
    elementi.append(Spacer(1, 0.5 * cm))

    # ── SEZIONE 1: PROFILO IMPRESA ─────────────────────────────────────────────
    elementi.append(HRFlowable(width="100%", thickness=2, color=VIOLA, spaceAfter=4))
    elementi.append(Paragraph("1. PROFILO IMPRESA", stili["sezione"]))

    campi_impresa = [
        ("Ragione Sociale", dati_impresa.get("ragione_sociale", "N/D")),
        ("Codice Fiscale / P.IVA", dati_impresa.get("codice_fiscale", "N/D")),
        ("Forma Giuridica", dati_impresa.get("forma_giuridica", "N/D")),
        ("Sede Legale", f"{dati_impresa.get('comune', 'N/D')} ({dati_impresa.get('provincia', 'N/D')}) — {dati_impresa.get('regione', 'N/D')}"),
        ("Codice ATECO", dati_impresa.get("codice_ateco", "N/D")),
        ("Settore", dati_impresa.get("settore_ateco", "N/D")),
        ("Data Costituzione", dati_impresa.get("data_costituzione", "N/D")),
        ("Numero Soci", str(len(dati_impresa.get("soci", [])))),
    ]

    profilo_rows = []
    for i in range(0, len(campi_impresa), 2):
        row = []
        for j in range(2):
            if i + j < len(campi_impresa):
                label, valore = campi_impresa[i + j]
                cell = [
                    Paragraph(label, stili["label"]),
                    Paragraph(str(valore), stili["valore"])
                ]
                row.append(cell)
            else:
                row.append("")
        profilo_rows.append(row)

    tabella_profilo = Table(profilo_rows, colWidths=[8.5 * cm, 8.5 * cm])
    tabella_profilo.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), GRIGIO_CHIARO),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
    ]))
    elementi.append(tabella_profilo)

    # Soci
    soci = dati_impresa.get("soci", [])
    if soci:
        elementi.append(Spacer(1, 0.3 * cm))
        elementi.append(Paragraph("Composizione Societaria:", stili["corpo_bold"]))
        soci_data = [["Nome", "Quota %", "Età", "Ruolo"]]
        for socio in soci:
            soci_data.append([
                socio.get("nome", "N/D"),
                f"{socio.get('quota_percentuale', 0):.1f}%",
                str(socio.get("eta", "N/D")),
                socio.get("carica", "Socio")
            ])
        tabella_soci = Table(soci_data, colWidths=[7 * cm, 3 * cm, 3 * cm, 4 * cm])
        tabella_soci.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VIOLA),
            ("TEXTCOLOR", (0, 0), (-1, 0), BIANCO),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BIANCO, GRIGIO_CHIARO]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementi.append(tabella_soci)

    # ── SEZIONE 2: SIMULATORE PUNTEGGIO ───────────────────────────────────────
    if simulatore:
        elementi.append(Spacer(1, 0.3 * cm))
        elementi.append(HRFlowable(width="100%", thickness=2, color=VIOLA, spaceAfter=4))
        elementi.append(Paragraph("2. PUNTEGGIO DI BANCABILITÀ", stili["sezione"]))

        score = simulatore.get("score_percentuale", 0)
        livello = simulatore.get("livello", "N/D")

        # Barra punteggio
        colore_score = VERDE if score >= 70 else (GIALLO if score >= 40 else ROSSO)
        score_data = [[
            Paragraph(f"<b>{score:.0f}/100</b>", ParagraphStyle(
                "score_num", fontName="Helvetica-Bold", fontSize=28,
                textColor=colore_score, alignment=TA_CENTER
            )),
            Paragraph(
                f"<b>Livello: {livello}</b><br/>"
                f"Il tuo profilo aziendale ha un punteggio di bancabilità di <b>{score:.0f} punti su 100</b>. "
                f"Questo indica la tua compatibilità media con i bandi di finanziamento pubblico disponibili.",
                stili["corpo"]
            )
        ]]
        tabella_score = Table(score_data, colWidths=[4 * cm, 13 * cm])
        tabella_score.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), GRIGIO_CHIARO),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        elementi.append(tabella_score)

        # Suggerimenti per migliorare
        suggerimenti = simulatore.get("suggerimenti_miglioramento", [])
        if suggerimenti:
            elementi.append(Spacer(1, 0.2 * cm))
            elementi.append(Paragraph("Come migliorare il tuo punteggio:", stili["corpo_bold"]))
            for sug in suggerimenti[:5]:
                elementi.append(Paragraph(f"• {sug}", stili["suggerimento"]))

    # ── SEZIONE 3: ANALISI BANDI ───────────────────────────────────────────────
    elementi.append(Spacer(1, 0.3 * cm))
    elementi.append(HRFlowable(width="100%", thickness=2, color=VIOLA, spaceAfter=4))
    n_sezione = 3 if simulatore else 2
    elementi.append(Paragraph(f"{n_sezione}. ANALISI BANDI COMPATIBILI", stili["sezione"]))

    # Prima i verdi, poi i gialli, poi gli altri
    ordine = {"verde": 0, "giallo": 1, "grigio": 2, "rosso": 3}
    risultati_ordinati = sorted(
        risultati_matching,
        key=lambda r: ordine.get(r.get("semaforo", "grigio"), 99)
    )

    for i, risultato in enumerate(risultati_ordinati):
        semaforo = risultato.get("semaforo", "grigio")
        colore = SEMAFORO_COLORI.get(semaforo, GRIGIO)
        testo_semaforo = SEMAFORO_TESTO.get(semaforo, "N/D")

        bando_info = risultato.get("bando", {})
        nome_bando = bando_info.get("nome", risultato.get("nome_bando", f"Bando {i+1}"))
        score_bando = risultato.get("score", 0)
        motivi = risultato.get("motivi_match", [])
        blocchi = risultato.get("blocchi", [])
        massimale = bando_info.get("massimale_euro") or risultato.get("massimale_euro")
        fondo_perduto = bando_info.get("percentuale_fondo_perduto") or risultato.get("percentuale_fondo_perduto")
        scadenza = bando_info.get("scadenza") or risultato.get("scadenza")
        url = bando_info.get("url_ufficiale") or risultato.get("url_ufficiale", "")

        # Card bando
        header_bando = [[
            Paragraph(f"<b>{nome_bando}</b>", stili["bando_titolo"]),
            Paragraph(
                f"<b>{testo_semaforo}</b>",
                ParagraphStyle(
                    "semaforo_label", fontName="Helvetica-Bold", fontSize=11,
                    textColor=colore, alignment=TA_RIGHT
                )
            )
        ]]
        tabella_header = Table(header_bando, colWidths=[12 * cm, 5 * cm])
        tabella_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, -1), 2, colore),
            ("BACKGROUND", (0, 0), (-1, -1), GRIGIO_CHIARO),
        ]))

        # Dettagli bando
        dettagli = []
        if massimale:
            dettagli.append(f"Massimale: €{massimale:,.0f}")
        if fondo_perduto:
            dettagli.append(f"Fondo perduto: {fondo_perduto}%")
        if scadenza:
            dettagli.append(f"Scadenza: {scadenza}")
        if score_bando:
            dettagli.append(f"Score compatibilità: {score_bando:.0f}%")

        testo_dettagli = " | ".join(dettagli) if dettagli else "Dettagli non disponibili"

        corpo_bando = [[Paragraph(testo_dettagli, stili["corpo"])]]

        if motivi:
            punti_positivi = "\n".join([f"✓ {m}" for m in motivi[:3]])
            corpo_bando.append([Paragraph(
                f"<b>Punti di forza:</b><br/>" + "<br/>".join([f"✓ {m}" for m in motivi[:3]]),
                stili["suggerimento"]
            )])

        if blocchi:
            corpo_bando.append([Paragraph(
                f"<b>Criticità:</b><br/>" + "<br/>".join([f"✗ {b}" for b in blocchi[:3]]),
                ParagraphStyle(
                    "blocchi", fontName="Helvetica", fontSize=9,
                    textColor=ROSSO, spaceAfter=3, leftIndent=12, leading=13
                )
            )])

        if url:
            corpo_bando.append([Paragraph(
                f"<b>Link ufficiale:</b> {url}",
                ParagraphStyle(
                    "link", fontName="Helvetica", fontSize=8,
                    textColor=VIOLA, spaceAfter=3, leftIndent=12
                )
            )])

        tabella_corpo = Table(corpo_bando, colWidths=[17 * cm])
        tabella_corpo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BIANCO),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
        ]))

        elementi.append(KeepTogether([tabella_header, tabella_corpo, Spacer(1, 0.3 * cm)]))

    # ── SEZIONE 4: PIANO D'AZIONE ──────────────────────────────────────────────
    elementi.append(PageBreak())
    n_sezione += 1
    elementi.append(HRFlowable(width="100%", thickness=2, color=VIOLA, spaceAfter=4))
    elementi.append(Paragraph(f"{n_sezione}. PIANO D'AZIONE CONSIGLIATO", stili["sezione"]))

    azioni = [
        ("Immediato (entro 7 giorni)", [
            "Raccogliere tutta la documentazione societaria aggiornata (visura, bilanci, statuto)",
            "Verificare la posizione debitoria con l'Agenzia delle Entrate (estratto conto fiscale)",
            "Controllare eventuali aiuti de minimis ricevuti negli ultimi 3 anni",
            "Aprire un conto corrente dedicato al progetto (requisito per molti bandi)"
        ]),
        ("Breve termine (entro 30 giorni)", [
            "Preparare un business plan sintetico (5-10 pagine) con piano finanziario",
            "Richiedere preventivi per le spese ammissibili (almeno 3 per voce)",
            "Verificare i requisiti specifici del bando verde con un consulente",
            "Registrarsi ai portali regionali per ricevere notifiche sui nuovi bandi"
        ]),
        ("Medio termine (entro 90 giorni)", [
            "Presentare la domanda per il bando con semaforo verde",
            "Monitorare l'apertura dei bandi con semaforo giallo",
            "Valutare modifiche societarie per migliorare la compatibilità futura",
            "Impostare un sistema di monitoraggio continuo con BandoMatch AI"
        ])
    ]

    for titolo_fase, azioni_fase in azioni:
        elementi.append(Paragraph(f"<b>{titolo_fase}</b>", stili["corpo_bold"]))
        for azione in azioni_fase:
            elementi.append(Paragraph(f"□ {azione}", stili["suggerimento"]))
        elementi.append(Spacer(1, 0.2 * cm))

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    elementi.append(Spacer(1, 0.5 * cm))
    elementi.append(HRFlowable(width="100%", thickness=1, color=GRIGIO, spaceAfter=4))
    elementi.append(Paragraph(
        "DISCLAIMER: Questo documento è generato automaticamente da BandoMatch AI sulla base dei dati "
        "estratti dalla visura camerale fornita. Le informazioni sui bandi sono aggiornate alla data di "
        "generazione del documento. BandoMatch AI non garantisce l'accuratezza delle informazioni né "
        "l'esito positivo delle domande di finanziamento. Si raccomanda di verificare sempre i requisiti "
        "ufficiali sui siti istituzionali e di consultare un professionista abilitato prima di presentare "
        "qualsiasi domanda. BandoMatch AI non è responsabile per decisioni prese sulla base di questo documento.",
        stili["disclaimer"]
    ))

    # ── BUILD PDF ──────────────────────────────────────────────────────────────
    doc.build(elementi, onFirstPage=_header_pagina, onLaterPages=_header_pagina)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"Dossier PDF salvato: {output_path} ({len(pdf_bytes):,} bytes)")

    return pdf_bytes


def genera_dossier_demo(nome_impresa: str = "TECH SOLUTIONS SRL") -> bytes:
    """Genera un dossier demo con dati di esempio."""
    dati_impresa = {
        "ragione_sociale": nome_impresa,
        "codice_fiscale": "01234567890",
        "forma_giuridica": "SRL",
        "comune": "Pescara",
        "provincia": "PE",
        "regione": "Abruzzo",
        "codice_ateco": "62.01.00",
        "settore_ateco": "Produzione di software non connesso all'edizione",
        "data_costituzione": "2022-03-15",
        "soci": [
            {"nome": "Mario Rossi", "quota_percentuale": 60.0, "eta": 32, "carica": "Amministratore Unico"},
            {"nome": "Laura Bianchi", "quota_percentuale": 40.0, "eta": 28, "carica": "Socia"}
        ]
    }

    risultati = [
        {
            "semaforo": "verde",
            "nome_bando": "Resto al Sud 2.0",
            "score": 92,
            "massimale_euro": 200000,
            "percentuale_fondo_perduto": 70,
            "scadenza": "sportello",
            "url_ufficiale": "https://www.invitalia.it/incentivi-e-strumenti/resto-al-sud-20",
            "motivi_match": ["Età soci compatibile (18-45 anni)", "Regione Abruzzo ammessa", "Settore ICT ammesso"],
            "blocchi": [],
            "bando": {"nome": "Resto al Sud 2.0", "massimale_euro": 200000}
        },
        {
            "semaforo": "giallo",
            "nome_bando": "PR FESR Abruzzo — Digitalizzazione PMI",
            "score": 65,
            "massimale_euro": 100000,
            "percentuale_fondo_perduto": 50,
            "scadenza": "2025-12-31",
            "url_ufficiale": "https://www.regione.abruzzo.it",
            "motivi_match": ["Settore digitale compatibile", "Sede in Abruzzo"],
            "blocchi": ["Impresa costituita da meno di 24 mesi — verifica requisito anzianità"],
            "bando": {"nome": "PR FESR Abruzzo", "massimale_euro": 100000}
        },
        {
            "semaforo": "rosso",
            "nome_bando": "Decontribuzione Sud 2025",
            "score": 15,
            "massimale_euro": 50000,
            "percentuale_fondo_perduto": 30,
            "scadenza": "2025-06-30",
            "motivi_match": [],
            "blocchi": ["Settore ICT non incluso tra i beneficiari", "Requisito dipendenti non soddisfatto"],
            "bando": {"nome": "Decontribuzione Sud", "massimale_euro": 50000}
        }
    ]

    simulatore = {
        "score_percentuale": 73,
        "livello": "BUONO",
        "suggerimenti_miglioramento": [
            "Aumenta il fatturato dichiarato (attualmente sotto soglia per alcuni bandi)",
            "Aggiungi un socio under 35 per accedere ai bandi giovani imprenditori",
            "Ottieni la certificazione ISO 9001 per sbloccare bandi qualità"
        ]
    }

    return genera_dossier(dati_impresa, risultati, simulatore)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Generazione dossier demo...")
    pdf = genera_dossier_demo()
    with open("/tmp/dossier_demo.pdf", "wb") as f:
        f.write(pdf)
    print(f"Dossier generato: /tmp/dossier_demo.pdf ({len(pdf):,} bytes)")
