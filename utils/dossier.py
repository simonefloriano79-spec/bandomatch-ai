"""
BandoMatch AI — Generatore PDF Dossier Premium
Usa ReportLab per produrre un dossier professionale con i bandi compatibili.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas as pdfgen_canvas

# ── Palette colori BandoMatch AI ──────────────────────────────────────────────
NAVY        = colors.HexColor('#0f172a')
NAVY_LIGHT  = colors.HexColor('#1e293b')
NAVY_MID    = colors.HexColor('#334155')
VERDE       = colors.HexColor('#22c55e')
VERDE_LIGHT = colors.HexColor('#dcfce7')
GIALLO      = colors.HexColor('#eab308')
GIALLO_LIGHT= colors.HexColor('#fef9c3')
ROSSO       = colors.HexColor('#ef4444')
ROSSO_LIGHT = colors.HexColor('#fee2e2')
BIANCO      = colors.white
SLATE_400   = colors.HexColor('#94a3b8')
SLATE_600   = colors.HexColor('#475569')

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


def _fmt_euro(valore):
    """Formatta un valore float in stringa Euro leggibile."""
    if not valore:
        return 'N/D'
    if valore >= 1_000_000:
        return f'\u20ac{valore / 1_000_000:.1f}M'
    if valore >= 1_000:
        return f'\u20ac{valore / 1_000:.0f}K'
    return f'\u20ac{valore:.0f}'


def _fmt_data(dt):
    """Formatta una data datetime in stringa italiana."""
    if not dt:
        return 'N/D'
    if isinstance(dt, str):
        return dt[:10]
    return dt.strftime('%d/%m/%Y')


def _semaforo_color(semaforo: str):
    """Restituisce (colore_testo, colore_sfondo) dato il livello semaforo."""
    m = {
        'VERDE':  (VERDE,    VERDE_LIGHT),
        'GIALLO': (GIALLO,   GIALLO_LIGHT),
        'ROSSO':  (ROSSO,    ROSSO_LIGHT),
    }
    return m.get(str(semaforo).upper(), (SLATE_400, colors.HexColor('#f1f5f9')))


class _NumberedCanvas(pdfgen_canvas.Canvas):
    """Canvas personalizzato per numerazione pagine e footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self._draw_footer(i + 1, num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_num, num_pages):
        self.setStrokeColor(NAVY_MID)
        self.setLineWidth(0.5)
        self.line(MARGIN, 1.2 * cm, PAGE_W - MARGIN, 1.2 * cm)
        self.setFont('Helvetica', 6.5)
        self.setFillColor(SLATE_400)
        disclaimer = (
            'Documento generato da AI a scopo informativo. '
            'Verificare con un consulente prima di presentare domanda. '
            'BandoMatch AI non costituisce consulenza finanziaria o legale.'
        )
        self.drawString(MARGIN, 0.75 * cm, disclaimer)
        self.drawRightString(PAGE_W - MARGIN, 0.75 * cm,
                             f'Pagina {page_num} di {num_pages}')


def genera_dossier(utente, analisi, bandi_compatibili: list) -> bytes:
    """
    Genera il PDF Dossier Premium per BandoMatch AI.

    Args:
        utente:            oggetto Utente SQLAlchemy (.email, .piano, .profilo_aziendale)
        analisi:           oggetto Analisi SQLAlchemy (ragione_sociale, ateco, regione, ecc.)
        bandi_compatibili: lista di dict con chiavi:
                           titolo, fonte, semaforo, score, massimale_agevolazione,
                           percentuale_fondo_perduto, data_scadenza, descrizione,
                           url, note_ai

    Returns:
        bytes: contenuto del PDF pronto per essere inviato come risposta HTTP
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=2.2 * cm,
        title='Dossier Bandi — BandoMatch AI',
        author='BandoMatch AI',
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Stili personalizzati ──────────────────────────────────────────────────
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=14,
                        textColor=VERDE, spaceAfter=6, spaceBefore=14)
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=9,
                          textColor=colors.HexColor('#1e293b'),
                          leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
    note_style = ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8.5,
                                textColor=colors.HexColor('#374151'),
                                leading=13, spaceAfter=4, alignment=TA_JUSTIFY)

    # ── HEADER ────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<font color="white"><b>BandoMatch AI</b></font>',
                  ParagraphStyle('lt', fontName='Helvetica-Bold', fontSize=18,
                                 textColor=BIANCO)),
        Paragraph(
            f'<font color="#94a3b8">Dossier Bandi Premium</font><br/>'
            f'<font color="#64748b" size="8">Generato il '
            f'{datetime.now().strftime("%d/%m/%Y %H:%M")}</font>',
            ParagraphStyle('rt', fontName='Helvetica', fontSize=10,
                           textColor=SLATE_400, alignment=TA_RIGHT)
        )
    ]]
    header_tbl = Table(header_data,
                       colWidths=[(PAGE_W - 2 * MARGIN) * f for f in [0.55, 0.45]])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('PADDING',    (0, 0), (-1, -1), 14),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width='100%', thickness=3, color=VERDE, spaceAfter=10))

    # ── PROFILO IMPRESA ───────────────────────────────────────────────────────
    ragione_sociale = (getattr(analisi, 'ragione_sociale', None) or
                       (utente.profilo_aziendale.azienda
                        if utente.profilo_aziendale else 'N/D'))
    ateco           = (getattr(analisi, 'ateco', None) or
                       (utente.profilo_aziendale.ateco
                        if utente.profilo_aziendale else 'N/D'))
    regione         = (getattr(analisi, 'regione', None) or
                       (utente.profilo_aziendale.regione
                        if utente.profilo_aziendale else 'N/D'))
    forma_giuridica = getattr(analisi, 'forma_giuridica', None) or 'N/D'
    eta_mesi        = getattr(analisi, 'eta_mesi', None)
    eta_str         = (f'{eta_mesi // 12} anni' if eta_mesi and eta_mesi >= 12
                       else (f'{eta_mesi} mesi' if eta_mesi else 'N/D'))
    capitale        = getattr(analisi, 'capitale_sociale', None)

    story.append(Paragraph('Profilo Impresa', h2))
    impresa_rows = [
        ['Ragione Sociale', ragione_sociale,     'Codice ATECO',    ateco],
        ['Regione',         regione,             'Forma Giuridica', forma_giuridica],
        ['Eta\' Impresa',   eta_str,             'Capitale Sociale',_fmt_euro(capitale)],
        ['Email Utente',    utente.email,        'Piano',           utente.piano.upper()],
    ]
    imp_tbl = Table(impresa_rows,
                    colWidths=[(PAGE_W - 2 * MARGIN) * f
                               for f in [0.22, 0.28, 0.22, 0.28]])
    imp_tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (0, -1), NAVY_LIGHT),
        ('BACKGROUND',  (2, 0), (2, -1), NAVY_LIGHT),
        ('TEXTCOLOR',   (0, 0), (0, -1), SLATE_400),
        ('TEXTCOLOR',   (2, 0), (2, -1), SLATE_400),
        ('TEXTCOLOR',   (1, 0), (1, -1), NAVY),
        ('TEXTCOLOR',   (3, 0), (3, -1), NAVY),
        ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',    (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTNAME',    (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME',    (3, 0), (3, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 0), (-1, -1), 8.5),
        ('PADDING',     (0, 0), (-1, -1), 7),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1),
         [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(imp_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── RIEPILOGO NUMERICO ────────────────────────────────────────────────────
    bandi_verdi  = getattr(analisi, 'bandi_verdi',  0) or 0
    bandi_gialli = getattr(analisi, 'bandi_gialli', 0) or 0
    bandi_rossi  = getattr(analisi, 'bandi_rossi',  0) or 0
    valore_pot   = getattr(analisi, 'valore_potenziale', 0) or 0

    story.append(Paragraph('Riepilogo Analisi', h2))
    riepilogo_data = [[
        Paragraph(f'<b><font size="20" color="#22c55e">{bandi_verdi}</font></b><br/>'
                  f'<font size="7" color="#64748b">BANDI COMPATIBILI</font>',
                  styles['Normal']),
        Paragraph(f'<b><font size="20" color="#eab308">{bandi_gialli}</font></b><br/>'
                  f'<font size="7" color="#64748b">CONDIZIONALI</font>',
                  styles['Normal']),
        Paragraph(f'<b><font size="20" color="#ef4444">{bandi_rossi}</font></b><br/>'
                  f'<font size="7" color="#64748b">NON IDONEI</font>',
                  styles['Normal']),
        Paragraph(f'<b><font size="18" color="#3b82f6">{_fmt_euro(valore_pot)}</font></b><br/>'
                  f'<font size="7" color="#64748b">VALORE POTENZIALE</font>',
                  styles['Normal']),
    ]]
    riepilogo_tbl = Table(riepilogo_data,
                          colWidths=[(PAGE_W - 2 * MARGIN) / 4] * 4)
    riepilogo_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY_LIGHT),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',    (0, 0), (-1, -1), 12),
        ('GRID',       (0, 0), (-1, -1), 0.5, NAVY_MID),
    ]))
    story.append(riepilogo_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # ── TABELLA RIEPILOGATIVA BANDI ───────────────────────────────────────────
    story.append(Paragraph('Tabella Bandi Compatibili', h2))

    col_w = [(PAGE_W - 2 * MARGIN) * f
             for f in [0.35, 0.13, 0.15, 0.15, 0.10, 0.12]]
    th_style = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8,
                              textColor=BIANCO)
    tc_style = ParagraphStyle('tc', fontName='Helvetica', fontSize=8,
                              alignment=TA_CENTER)

    table_rows = [[
        Paragraph('<b>Bando</b>', th_style),
        Paragraph('<b>Semaforo</b>', th_style),
        Paragraph('<b>Importo Max</b>', th_style),
        Paragraph('<b>Scadenza</b>', th_style),
        Paragraph('<b>% F.P.</b>', th_style),
        Paragraph('<b>Score</b>', th_style),
    ]]

    for b in bandi_compatibili:
        sem    = str(b.get('semaforo', 'GRIGIO')).upper()
        col_s, _ = _semaforo_color(sem)
        perc_fp  = b.get('percentuale_fondo_perduto') or 0
        score    = b.get('score') or b.get('punteggio') or 0
        table_rows.append([
            Paragraph(str(b.get('titolo', 'N/D'))[:80],
                      ParagraphStyle('td', fontName='Helvetica', fontSize=8,
                                     leading=11)),
            Paragraph(sem.capitalize(),
                      ParagraphStyle('tds', fontName='Helvetica-Bold', fontSize=8,
                                     textColor=col_s, alignment=TA_CENTER)),
            Paragraph(_fmt_euro(b.get('massimale_agevolazione')), tc_style),
            Paragraph(_fmt_data(b.get('data_scadenza')), tc_style),
            Paragraph(f'{perc_fp:.0f}%' if perc_fp else 'N/D', tc_style),
            Paragraph(f'{score:.0f}%' if score else 'N/D',
                      ParagraphStyle('tdscore', fontName='Helvetica-Bold', fontSize=8,
                                     textColor=VERDE if score >= 70 else GIALLO,
                                     alignment=TA_CENTER)),
        ])

    tbl = Table(table_rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 8),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',       (0, 0), (-1, -1), 6),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Totale finanziamento potenziale
    bandi_verdi_list = [b for b in bandi_compatibili
                        if str(b.get('semaforo', '')).upper() == 'VERDE']
    totale = sum(b.get('massimale_agevolazione') or 0 for b in bandi_verdi_list)
    tot_tbl = Table(
        [[Paragraph(
            f'<b>Totale finanziamento potenziale (bandi verdi): {_fmt_euro(totale)}</b>',
            ParagraphStyle('tot', fontName='Helvetica-Bold', fontSize=10,
                           textColor=BIANCO, alignment=TA_RIGHT)
        )]],
        colWidths=[PAGE_W - 2 * MARGIN]
    )
    tot_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), VERDE),
        ('PADDING',    (0, 0), (-1, -1), 10),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 0.8 * cm))

    # ── SCHEDE DETTAGLIO (max 5 bandi) ───────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('Schede Dettaglio Bandi', h2))
    story.append(Paragraph(
        'Di seguito le schede dettagliate per i principali bandi compatibili '
        'con il profilo della tua impresa.',
        body
    ))
    story.append(Spacer(1, 0.3 * cm))

    for i, b in enumerate(bandi_compatibili[:5]):
        sem     = str(b.get('semaforo', 'GRIGIO')).upper()
        col_s, col_sl = _semaforo_color(sem)
        titolo  = b.get('titolo', 'Bando senza titolo')
        fonte   = b.get('fonte', 'N/D')
        desc    = b.get('descrizione') or 'Nessuna descrizione disponibile.'
        note_ai = b.get('note_ai') or b.get('note') or ''
        url     = b.get('url', '')
        perc_fp = b.get('percentuale_fondo_perduto') or 0
        score   = b.get('score') or b.get('punteggio') or 0
        regioni = b.get('regioni_ammesse') or []
        if isinstance(regioni, list):
            regioni_str = ', '.join(str(r) for r in regioni[:5]) or 'Nazionale'
        else:
            regioni_str = str(regioni) or 'Nazionale'

        # Intestazione scheda
        sh_tbl = Table(
            [[Paragraph(f'<b>{i + 1}. {str(titolo)[:70]}</b>',
                        ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=11,
                                       textColor=BIANCO)),
              Paragraph(f'<b>{sem.capitalize()}</b>',
                        ParagraphStyle('sem', fontName='Helvetica-Bold', fontSize=10,
                                       textColor=col_s, alignment=TA_RIGHT))]],
            colWidths=[(PAGE_W - 2 * MARGIN) * f for f in [0.75, 0.25]]
        )
        sh_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('PADDING',    (0, 0), (-1, -1), 10),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        # Dettagli
        det_rows = [
            ['Fonte / Ente',   fonte,
             'Score',          f'{score:.0f}%' if score else 'N/D'],
            ['Importo Massimo',_fmt_euro(b.get('massimale_agevolazione')),
             '% Fondo Perduto',f'{perc_fp:.0f}%' if perc_fp else 'N/D'],
            ['Scadenza',       _fmt_data(b.get('data_scadenza')),
             'Regioni Ammesse',regioni_str[:60]],
        ]
        det_tbl = Table(det_rows,
                        colWidths=[(PAGE_W - 2 * MARGIN) * f
                                   for f in [0.22, 0.28, 0.22, 0.28]])
        det_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f1f5f9')),
            ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',   (2, 0), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR',  (0, 0), (0, -1), SLATE_600),
            ('TEXTCOLOR',  (2, 0), (2, -1), SLATE_600),
            ('FONTSIZE',   (0, 0), (-1, -1), 8.5),
            ('PADDING',    (0, 0), (-1, -1), 7),
            ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        # Note AI
        note_block = []
        if note_ai:
            note_tbl = Table(
                [[Paragraph(f'<b>Note AI:</b> {str(note_ai)[:400]}', note_style)]],
                colWidths=[PAGE_W - 2 * MARGIN]
            )
            note_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
                ('PADDING',    (0, 0), (-1, -1), 8),
                ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#fde68a')),
            ]))
            note_block = [Spacer(1, 0.2 * cm), note_tbl]

        link_para = Paragraph(
            (f'<link href="{url}"><font color="#3b82f6">'
             f'<u>Vai al bando ufficiale</u></font></link>' if url else ''),
            ParagraphStyle('link', fontName='Helvetica', fontSize=8, spaceAfter=4)
        )

        scheda = KeepTogether([
            sh_tbl,
            det_tbl,
            Spacer(1, 0.2 * cm),
            Paragraph(str(desc)[:600], body),
            *note_block,
            Spacer(1, 0.15 * cm),
            link_para,
            HRFlowable(width='100%', thickness=0.5,
                       color=colors.HexColor('#e2e8f0'),
                       spaceAfter=14, spaceBefore=6),
        ])
        story.append(scheda)

    # ── DISCLAIMER FINALE ─────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    disc_tbl = Table(
        [[Paragraph(
            '<b>DISCLAIMER</b><br/>'
            'Documento generato da AI a scopo informativo. '
            'Verificare con un consulente prima di presentare domanda. '
            'BandoMatch AI non costituisce consulenza finanziaria o legale. '
            'I dati sui bandi sono aggiornati alla data di generazione del documento '
            'e potrebbero non riflettere variazioni successive.',
            ParagraphStyle('disc', fontName='Helvetica', fontSize=7.5,
                           textColor=SLATE_600, leading=12, alignment=TA_JUSTIFY)
        )]],
        colWidths=[PAGE_W - 2 * MARGIN]
    )
    disc_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('PADDING',    (0, 0), (-1, -1), 10),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
    ]))
    story.append(disc_tbl)

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf.read()
