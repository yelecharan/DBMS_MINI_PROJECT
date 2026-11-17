"""Build the university DOCX/PDF and a clean ER overview from this report packet."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
MD = ROOT / "DBMS_Project_Report.md"

def plain_markdown(value):
    value = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', value)
    return re.sub(r'\*\*|`|\*', '', value)

def add_page_number(paragraph):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Page ")
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = " PAGE "
    separate = OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, end])

def make_docx(text):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(.75); sec.bottom_margin = Inches(.7)
    sec.left_margin = Inches(.8); sec.right_margin = Inches(.8)
    styles = doc.styles
    styles['Normal'].font.name = 'Aptos'; styles['Normal'].font.size = Pt(10)
    styles['Normal'].paragraph_format.space_after = Pt(5)
    for nm, size, color in [('Title', 28, '000000'), ('Heading 1', 17, '12304A'), ('Heading 2', 13, '167D8D'), ('Heading 3', 11, '167D8D')]:
        styles[nm].font.name = 'Aptos Display'; styles[nm].font.size = Pt(size); styles[nm].font.color.rgb = RGBColor.from_string(color)
    footer = sec.footer.paragraphs[0]; add_page_number(footer)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("GATESENTRY\n").bold = True
    p.runs[0].font.size = Pt(17); p.runs[0].font.color.rgb = RGBColor(22,125,141)
    title = doc.add_paragraph("GateSentry DBMS Project Report", style='Title'); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("Explainable, Privacy-First Office Tailgating Detection\nand Incident Intelligence System")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("\n\nStudents\n[STUDENT NAME] — [STUDENT SRN]\n[TEAM MEMBER DETAILS]").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("\n\nDepartment / Institution: [INSTITUTION DETAILS]\nAcademic Year: 2026–2027").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()
    doc.add_heading('Table of Contents', 1)
    p = doc.add_paragraph()
    fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'TOC \\o "1-3" \\h \\z \\u'); p._p.addnext(fld)
    doc.add_paragraph('In Word, update the table to refresh page numbers.')
    doc.add_page_break()
    lines = text.splitlines(); in_code = False; code = []; i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            if in_code:
                p = doc.add_paragraph(); r = p.add_run('\n'.join(code)); r.font.name = 'Consolas'; r.font.size = Pt(8)
                in_code = False; code = []
            else: in_code = True
            i += 1; continue
        if in_code: code.append(line); i += 1; continue
        if line.startswith('|'):
            rows=[]
            while i < len(lines) and lines[i].startswith('|'):
                row=[c.strip() for c in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r':?-{3,}:?', c or '-') for c in row): rows.append(row)
                i+=1
            if rows:
                table=doc.add_table(rows=0, cols=max(map(len,rows))); table.style='Light Shading Accent 1'
                for row in rows:
                    cells=table.add_row().cells
                    for j,val in enumerate(row): cells[j].text=plain_markdown(val)
            continue
        if line.startswith('# '): doc.add_heading(line[2:], 1)
        elif line.startswith('## '): doc.add_heading(line[3:], 2)
        elif line.startswith('### '): doc.add_heading(line[4:], 3)
        elif line.startswith('- '): doc.add_paragraph(plain_markdown(line[2:]), style='List Bullet')
        elif line.strip(): doc.add_paragraph(plain_markdown(line.strip()))
        i+=1
    doc.save(ROOT / 'DBMS_Project_Report.docx')

def make_pdf(text):
    out=ROOT/'DBMS_Project_Report.pdf'
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CoverTitle', parent=styles['Title'], fontSize=23, leading=29, textColor=colors.HexColor('#12304a'), alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], textColor=colors.HexColor('#167d8d'), spaceBefore=10))
    story=[Spacer(1,48*mm),Paragraph('GATESENTRY',styles['CoverTitle']),Paragraph('DBMS PROJECT REPORT',styles['CoverTitle']),Paragraph('Explainable, Privacy-First Office Tailgating Detection and Incident Intelligence System',styles['BodyText']),Spacer(1,30*mm),Paragraph('Students',styles['Heading2']),Paragraph('[STUDENT NAME] — [STUDENT SRN]<br/>[TEAM MEMBER DETAILS]',styles['BodyText']),Spacer(1,30*mm),Paragraph('Institution: [INSTITUTION DETAILS]<br/>Academic Year: 2026–2027',styles['BodyText']),PageBreak(),Paragraph('Table of Contents',styles['Heading1'])]
    heads=re.findall(r'^#{1,3} .+$',text,re.M)
    for h in heads: story.append(Paragraph(h.lstrip('# ').replace('&','&amp;'), styles['BodyText']))
    story.append(PageBreak())
    lines=text.splitlines(); i=0; in_code=False; buf=[]
    while i<len(lines):
        line=lines[i]
        if line.startswith('```'):
            if in_code:
                story.append(Preformatted('\n'.join(buf), ParagraphStyle('Code',fontName='Courier',fontSize=7,leading=9,backColor=colors.HexColor('#f1f5f9')))); buf=[];in_code=False
            else: in_code=True
            i+=1;continue
        if in_code: buf.append(line);i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                row=[c.strip().replace('**','').replace('`','') for c in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r':?-{3,}:?',c or '-') for c in row): rows.append([Paragraph(plain_markdown(c).replace('&','&amp;'),styles['BodyText']) for c in row])
                i+=1
            if rows:
                t=Table(rows,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcecf0')),('GRID',(0,0),(-1,-1),.35,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,5));
            continue
        if line.startswith('# '): story.append(Paragraph(line[2:],styles['Heading1']))
        elif line.startswith('## '): story.append(Paragraph(line[3:],styles['H2x']))
        elif line.startswith('### '): story.append(Paragraph(line[4:],styles['Heading3']))
        elif line.startswith('- '): story.append(Paragraph('- '+plain_markdown(line[2:]).replace('&','&amp;'),styles['BodyText']))
        elif line.strip(): story.append(Paragraph(plain_markdown(line.strip()).replace('&','&amp;'),styles['BodyText']))
        i+=1
    def page(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.grey);canvas.drawCentredString(A4[0]/2,12*mm,f'GateSentry  •  {doc.page}');canvas.restoreState()
    pdf=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,topMargin=16*mm,bottomMargin=20*mm)
    pdf.title='GateSentry DBMS Project Report';pdf.author='GateSentry project team'
    pdf.build(story,onFirstPage=page,onLaterPages=page)

def make_er_png():
    entities=[
      ('users','PK id  |  UK email','incidents.assigned_to; incident_actions.actor_id; audit_logs.actor_user_id'),
      ('employees','PK id  |  UK employee_code, email','access_credentials.employee_id'),
      ('sites','PK id  |  UK site_name','zones.site_id'),
      ('zones','PK id  |  FK site_id, parent_zone_id','gates.zone_id; parent_zone_id references zones.id'),
      ('gates','PK id  |  FK zone_id  |  UK gate_code','cameras.gate_id; access_events.gate_id; gate_sessions.gate_id'),
      ('cameras','PK id  |  FK gate_id  |  UK camera_code','camera_observations.camera_id'),
      ('access_credentials','PK id  |  FK employee_id  |  UK credential_hash','access_events.credential_id'),
      ('access_events','PK id  |  FK gate_id, credential_id','gate session correlation uses gate_id and event_timestamp'),
      ('gate_sessions','PK id  |  FK gate_id','camera_observations.gate_session_id; incidents.gate_session_id'),
      ('camera_observations','PK id  |  FK gate_id, camera_id, gate_session_id','anonymous tracker_id; confidence threshold'),
      ('incidents','PK id  |  FK gate_id, gate_session_id, assigned_to','incident_actions.incident_id; evidence_assets.incident_id'),
      ('incident_actions','PK id  |  FK incident_id, actor_id','investigation history for incidents'),
      ('evidence_assets','PK id  |  FK incident_id','redacted evidence reference and retention metadata'),
      ('audit_logs','PK id  |  FK actor_user_id','actor, entity, before/after values and time'),
      ('detection_rules','PK id  |  FK gate_id (optional)','gate-scoped or system-wide detection parameters'),
      ('incident_vector_outbox','PK event_id  |  FK incident_id','pending/retry/lease status for Qdrant snapshots'),
    ]
    W,H=2220,1750; im=Image.new('RGB',(W,H),'#f8fafc');d=ImageDraw.Draw(im)
    try: title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',38); font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22); small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    except OSError: title=font=small=ImageFont.load_default()
    d.text((65,30),'GateSentry Entity Relationship Diagram',font=title,fill='#12304a')
    boxw=675;boxh=230;gapx=35;gapy=35;x0=50;y0=105
    for idx,(name,keys,refs) in enumerate(entities):
        row,col=divmod(idx,3);x=x0+col*(boxw+gapx);y=y0+row*(boxh+gapy)
        d.rounded_rectangle((x,y,x+boxw,y+boxh),radius=14,fill='white',outline='#167d8d',width=3)
        d.rounded_rectangle((x,y,x+boxw,y+52),radius=12,fill='#dcecf0',outline='#167d8d',width=1)
        d.text((x+17,y+10),name.upper(),font=font,fill='#12304a')
        d.text((x+17,y+76),keys,font=small,fill='#334155')
        words=refs.split(); lines=[]; line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if len(candidate)>65 and line: lines.append(line);line=word
            else: line=candidate
        if line: lines.append(line)
        for li,content in enumerate(lines[:3]): d.text((x+17,y+122+li*25),content,font=small,fill='#64748b')
    d.text((50,1680),'FK descriptions point to the related table or explain its referencing rows.',font=small,fill='#334155')
    d.text((50,1712),'See ER_Diagram.mmd for the full relationship notation and Database_Design.md for design notes.',font=small,fill='#334155')
    im.save(ROOT/'ER_Diagram.png')

if __name__=='__main__':
    try:
        make_docx(MD.read_text(encoding='utf-8'));make_pdf(MD.read_text(encoding='utf-8'));make_er_png()
        print('Created DOCX, PDF and ER PNG')
    except Exception as e:
        raise SystemExit(f'Build failed: {e}')
