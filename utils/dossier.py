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
GRIGIO      = colors.HexColor('#94a3b8')
GRIGIO_LIGHT= colors.HexColor('#f1f5f9')
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
    return m.get(str(semaforo).upper(), (GRIGIO, GRIGIO_LIGHT))


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
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=16,
                        textColor=VERDE, spaceAfter=6, spaceBefore=14)
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=12,
                          textColor=colors.HexColor('#1e293b'),
                          leading=16, spaceAfter=4, alignment=TA_JUSTIFY)
    note_style = ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=9.5,
                                textColor=colors.HexColor('#374151'),
                                leading=15, spaceAfter=4, alignment=TA_JUSTIFY)
    req_ok_style = ParagraphStyle('req_ok', fontName='Helvetica', fontSize=12,
                                  textColor=colors.HexColor('#166534'),
                                  leading=14, spaceAfter=2, bulletIndent=10, leftIndent=20)
    req_ko_style = ParagraphStyle('req_ko', fontName='Helvetica-Bold', fontSize=12,
                                  textColor=colors.HexColor('#9a3412'),
                                  leading=14, spaceAfter=2, bulletIndent=10, leftIndent=20)

    # ── HEADER ────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<font color="white"><b>BandoMatch AI</b></font>',
                  ParagraphStyle('lt', fontName='Helvetica-Bold', fontSize=24,
                                 textColor=BIANCO)),
        Paragraph(
            f'<font color="#94a3b8">Dossier Bandi Premium</font><br/>'
            f'<font color="#64748b" size="8">Generato il '
            f'{datetime.now().strftime("%d/%m/%Y %H:%M")}</font>',
            ParagraphStyle('rt', fontName='Helvetica', fontSize=12,
                           textColor=SLATE_400, alignment=TA_RIGHT)
        )
    ]]
    header_tbl = Table(header_data,
                       colWidths=[(PAGE_W - 2 * MARGIN) * f for f in [0.55, 0.45]])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('PADDING',    (0, 0), (-1, -1), 18),
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
        ('PADDING',     (0, 0), (-1, -1), 10),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1),
         [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(imp_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── RIEPILOGO NUMERICO ────────────────────────────────────────────────────
    bandi_verdi  = len([b for b in bandi_compatibili if str(b.get('semaforo', '')).upper() == 'VERDE'])
    bandi_gialli = len([b for b in bandi_compatibili if str(b.get('semaforo', '')).upper() == 'GIALLO'])
    valore_pot   = getattr(analisi, 'valore_potenziale', 0) or 0

    story.append(Paragraph('Riepilogo Analisi', h2))
    riepilogo_data = [[
        Paragraph(f'<b><font size="20" color="#22c55e">{bandi_verdi}</font></b><br/>'
                  f'<font size="7" color="#64748b">BANDI COMPATIBILI</font>',
                  styles['Normal']),
        Paragraph(f'<b><font size="20" color="#eab308">{bandi_gialli}</font></b><br/>'
                  f'<font size="7" color="#64748b">CONDIZIONALI</font>',
                  styles['Normal']),
        Paragraph(f'<b><font size="18" color="#3b82f6">{_fmt_euro(valore_pot)}</font></b><br/>'
                  f'<font size="7" color="#64748b">VALORE POTENZIALE</font>',
                  styles['Normal']),
    ]]
    riepilogo_tbl = Table(riepilogo_data,
                          colWidths=[(PAGE_W - 2 * MARGIN) / 3] * 3)
    riepilogo_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY_LIGHT),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',    (0, 0), (-1, -1), 16),
        ('GRID',       (0, 0), (-1, -1), 0.5, NAVY_MID),
    ]))
    story.append(riepilogo_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # ── LEGGENDA SEMAFORO ─────────────────────────────────────────────────────
    story.append(Paragraph('Leggenda Semaforo', h2))
    leggenda_data = [
        [Paragraph('<b>VERDE</b>', ParagraphStyle('l_v', fontName='Helvetica-Bold', textColor=VERDE)),
         Paragraph('<b>Compatibile:</b> L\'impresa soddisfa tutti i requisiti principali del bando.', body)],
        [Paragraph('<b>GIALLO</b>', ParagraphStyle('l_g', fontName='Helvetica-Bold', textColor=GIALLO)),
         Paragraph('<b>Condizionale:</b> L\'impresa potrebbe partecipare, ma mancano alcuni requisiti o ci sono avvertenze (es. bando in apertura, fondi in esaurimento).', body)],
        [Paragraph('<b>ROSSO</b>', ParagraphStyle('l_r', fontName='Helvetica-Bold', textColor=ROSSO)),
         Paragraph('<b>Non Idoneo:</b> L\'impresa non soddisfa uno o più requisiti bloccanti.', body)],
        [Paragraph('<b>GRIGIO</b>', ParagraphStyle('l_gr', fontName='Helvetica-Bold', textColor=GRIGIO)),
         Paragraph('<b>Dati Insufficienti:</b> Non ci sono abbastanza dati per valutare la compatibilità.', body)]
    ]
    leggenda_tbl = Table(leggenda_data, colWidths=[(PAGE_W - 2 * MARGIN) * 0.15, (PAGE_W - 2 * MARGIN) * 0.85])
    leggenda_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('PADDING',    (0, 0), (-1, -1), 12),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(leggenda_tbl)
    story.append(Spacer(1, 0.8 * cm))

    # ── SCHEDE DETTAGLIO (solo VERDI e GIALLI) ───────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('Schede Dettaglio Bandi', h2))
    story.append(Paragraph(
        'Di seguito le schede dettagliate per i bandi compatibili (VERDI) e condizionali (GIALLI) '
        'con il profilo della tua impresa.',
        body
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Filtra solo verdi e gialli
    bandi_filtrati = [b for b in bandi_compatibili if str(b.get('semaforo', '')).upper() in ('VERDE', 'GIALLO')]

    for i, b in enumerate(bandi_filtrati):
        sem     = str(b.get('semaforo', 'GRIGIO')).upper()
        col_s, col_sl = _semaforo_color(sem)
        titolo  = b.get('titolo', b.get('bando_nome', 'Bando senza titolo'))
        fonte   = b.get('fonte', b.get('ente', 'N/D'))
        desc    = b.get('descrizione') or 'Nessuna descrizione disponibile.'
        note_ai = b.get('note_ai') or b.get('note') or ''
        url     = b.get('url', '')
        
        # Gestione agevolazioni (da dict o da campi diretti)
        agev = b.get('agevolazioni', {})
        massimale = b.get('massimale_agevolazione') or agev.get('massimale_investimento') or agev.get('spesa_progetto_max') or 0
        perc_fp = b.get('percentuale_fondo_perduto') or agev.get('percentuale_fondo_perduto') or agev.get('percentuale_fondo_perduto_fino_120k') or 0
        
        score   = b.get('score') or b.get('punteggio') or 0
        regioni = b.get('regioni_ammesse') or []
        if isinstance(regioni, list):
            regioni_str = ', '.join(str(r) for r in regioni[:5]) or 'Nazionale'
        else:
            regioni_str = str(regioni) or 'Nazionale'

        # Intestazione scheda
        sh_tbl = Table(
            [[Paragraph(f'<b>{i + 1}. {str(titolo)[:70]}</b>',
                        ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=12,
                                       textColor=BIANCO)),
              Paragraph(f'<b>{sem.capitalize()}</b>',
                        ParagraphStyle('sem', fontName='Helvetica-Bold', fontSize=12,
                                       textColor=col_s, alignment=TA_RIGHT))]],
            colWidths=[(PAGE_W - 2 * MARGIN) * f for f in [0.75, 0.25]]
        )
        sh_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('PADDING',    (0, 0), (-1, -1), 14),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        # Dettagli
        det_rows = [
            ['Fonte / Ente',   fonte,
             'Score',          f'{score:.0f}%' if score else 'N/D'],
            ['Importo Massimo',_fmt_euro(massimale),
             '% Fondo Perduto',f'{perc_fp:.0f}%' if perc_fp else 'N/D'],
            ['Scadenza',       _fmt_data(b.get('data_scadenza') or b.get('stato_bando')),
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

        # Estrazione requisiti da checks
        checks = b.get('checks', {})
        req_ok = []
        req_ko = []
        
        if checks:
            for k, v in checks.items():
                if isinstance(v, dict):
                    motivo = v.get('motivo', '')
                    if v.get('ok') is True:
                        if v.get('warning') is True:
                            req_ko.append(f"Avvertenza: {motivo}")
                        else:
                            req_ok.append(motivo)
                    else:
                        req_ko.append(motivo)
        else:
            # Fallback se i dati arrivano già processati
            req_ok = b.get('requisiti_soddisfatti', [])
            req_ko = b.get('requisiti_mancanti', [])
            
            # Fallback ulteriore da semaforo_dettaglio
            sem_det = b.get('semaforo_dettaglio', {})
            if not req_ko and sem_det:
                req_ko.extend(sem_det.get('warning', []))
                req_ko.extend(sem_det.get('bloccanti_falliti', []))
                
            # Fallback da motivo_principale
            if not req_ko and sem == 'GIALLO' and b.get('motivo_principale'):
                req_ko.append(b.get('motivo_principale'))

        req_block = []
        
        if req_ok:
            req_block.append(Spacer(1, 0.2 * cm))
            req_block.append(Paragraph('<b>Requisiti Soddisfatti:</b>', ParagraphStyle('h_ok', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#166534'))))
            for req in req_ok:
                req_block.append(Paragraph(f"• {req}", req_ok_style))
                
        if sem == 'GIALLO' and req_ko:
            req_block.append(Spacer(1, 0.2 * cm))
            req_block.append(Paragraph('<b>GAP ANALYSIS — Cosa manca o a cosa fare attenzione:</b>', ParagraphStyle('h_ko', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#9a3412'))))
            for req in req_ko:
                req_block.append(Paragraph(f"• {req}", req_ko_style))
                
            # Suggerimento
            suggerimento = "Verifica i requisiti mancanti o le avvertenze prima di procedere. Potrebbe essere necessario attendere l'apertura del bando o integrare la documentazione."
            if note_ai:
                suggerimento = note_ai
                
            req_block.append(Spacer(1, 0.1 * cm))
            req_block.append(Paragraph(f"<i>Suggerimento: {suggerimento}</i>", ParagraphStyle('sugg', fontName='Helvetica-Oblique', fontSize=9.5, textColor=colors.HexColor('#b45309'))))

        link_para = Paragraph(
            (f'<link href="{url}"><font color="#3b82f6">'
             f'<u>Vai al bando ufficiale</u></font></link>' if url else ''),
            ParagraphStyle('link', fontName='Helvetica', fontSize=9, spaceAfter=4)
        )

        scheda = KeepTogether([
            sh_tbl,
            det_tbl,
            Spacer(1, 0.2 * cm),
            Paragraph(str(desc)[:600], body),
            *req_block,
            Spacer(1, 0.15 * cm),
            link_para,
            HRFlowable(width='100%', thickness=0.5,
                       color=colors.HexColor('#e2e8f0'),
                       spaceAfter=14, spaceBefore=6),
        ])
        story.append(scheda)

    # ── DISCLAIMER FINALE ─────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    disclaimer_testo = (
        "<b>Nota Legale:</b> Le informazioni contenute in questo dossier sono generate "
        "automaticamente da BandoMatch AI sulla base dei dati forniti e delle fonti pubbliche "
        "disponibili. Non costituiscono consulenza professionale, legale o finanziaria. "
        "Si raccomanda di verificare sempre i bandi ufficiali e di consultare un esperto "
        "prima di presentare qualsiasi domanda di agevolazione."
    )
    story.append(Paragraph(disclaimer_testo, note_style))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
