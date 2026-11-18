"""Generate the GateSentry ER diagram (Chen notation) as SVG/HTML.

    python docs/diagrams/make_er_diagram.py      -> docs/diagrams/er_diagram.html
    node docs/diagrams/render.mjs docs/diagrams/er_diagram.html docs/er_diagram.png 2150

Notation
* rectangle = entity, ellipse = attribute, underlined = key attribute
* double ellipse = multivalued attribute, ellipse with child ellipses = composite attribute
* diamond = relationship, double line = total participation, single line = partial
* 1 / N = cardinality.  Foreign keys are NOT drawn as attributes (they are the relationships).
Participation drawn here is exactly what the database enforces.
"""
import math
from pathlib import Path

W, H = 2150, 1450
PG = ("#dbeafe", "#1d4ed8")       # entity fill / stroke (PostgreSQL)
MG = ("#dcfce7", "#15803d")       # entity fill / stroke (MongoDB)
out: list[str] = []
lines: list[str] = []             # drawn first, so shapes sit on top


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;")


def line(p, q, double=False):
    (x1, y1), (x2, y2) = p, q
    if not double:
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="ln"/>')
        return
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    ox, oy = -dy / L * 3.2, dx / L * 3.2
    for s in (1, -1):
        lines.append(f'<line x1="{x1 + s * ox:.1f}" y1="{y1 + s * oy:.1f}" '
                     f'x2="{x2 + s * ox:.1f}" y2="{y2 + s * oy:.1f}" class="ln"/>')


def entity(name, x, y, colors):
    fill, stroke = colors
    out.append(f'<rect x="{x - 95}" y="{y - 29}" width="190" height="58" rx="4" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>'
               f'<text x="{x}" y="{y + 7}" class="ent">{esc(name)}</text>')
    return (x, y)


def attr(label, x, y, owner, key=False, multi=False, small=False):
    rx = 10 + 4.6 * len(label)
    ry = 18 if not small else 16
    line((x, y), owner)
    cls = "attr-s" if small else "attr"
    if multi:
        out.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx + 5}" ry="{ry + 5}" class="ov"/>')
    out.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" class="ov"/>')
    deco = ' text-decoration="underline"' if key else ""
    weight = ' font-weight="700"' if key else ""
    out.append(f'<text x="{x}" y="{y + 5}" class="{cls}"{deco}{weight}>{esc(label)}</text>')
    return (x, y)


def rel(label, x, y):
    out.append(f'<polygon points="{x},{y - 38} {x + 66},{y} {x},{y + 38} {x - 66},{y}" '
               f'fill="#ede9fe" stroke="#6d28d9" stroke-width="2.2"/>'
               f'<text x="{x}" y="{y + 5}" class="rel">{esc(label)}</text>')
    return (x, y)


def card(ent, dia, text, along=118, side=16):
    """cardinality label placed on the entity end of a relationship line"""
    (x1, y1), (x2, y2) = ent, dia
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    px, py = x1 + ux * along - uy * side, y1 + uy * along + ux * side
    out.append(f'<text x="{px:.0f}" y="{py + 7:.0f}" class="card">{text}</text>')


def connect(e1, r, e2, c1, c2, total1, total2, a1=118, a2=118):
    line(e1, r, total1)
    line(r, e2, total2)
    card(e1, r, c1, a1)
    card(e2, r, c2, a2)


# ---------------- regions ----------------
out.append('<rect x="18" y="86" width="1352" height="1350" rx="14" class="region pg"/>'
           '<text x="40" y="122" class="region-t" fill="#1d4ed8">PostgreSQL 18 – relational tables</text>')
out.append('<rect x="1386" y="86" width="746" height="1350" rx="14" class="region mg"/>'
           '<text x="1408" y="122" class="region-t" fill="#15803d">MongoDB – document collections</text>')

# ---------------- entities ----------------
E = entity("Employees", 215, 310, PG)
C = entity("Cards", 700, 310, PG)
G = entity("Gates", 1170, 310, PG)
A = entity("Access_Logs", 935, 670, PG)
I = entity("Incidents", 935, 1020, PG)
O = entity("Observations", 1625, 520, MG)
R = entity("Report", 1625, 880, MG)
L_ = entity("Alerts", 1625, 1200, MG)

# ---------------- relationships ----------------
r_has = rel("has", 457, 310)
r_gen = rel("generates", 795, 490)
r_at = rel("at", 1075, 490)
r_det = rel("detects", 935, 845)
r_obs = rel("has", 1290, 700)
r_rep = rel("has", 1290, 900)
r_alt = rel("has", 1290, 1120)

connect(E, r_has, C, "1", "N", True, True)        # every employee owns >= 1 card, every card has an owner
connect(C, r_gen, A, "1", "N", False, True, 95, 110)   # a log needs a card; a card may have no logs yet
connect(G, r_at, A, "1", "N", False, True, 95, 110)    # a log needs a gate; a gate may have no logs yet
connect(A, r_det, I, "1", "N", False, True, 62, 62)    # an incident needs a scan
connect(I, r_obs, O, "1", "N", False, True, 130, 130)  # every document needs an incident_id
connect(I, r_rep, R, "1", "N", False, True, 130, 130)
connect(I, r_alt, L_, "1", "N", False, True, 130, 130)

# ---------------- attributes: PostgreSQL ----------------
attr("emp_id", 80, 195, E, key=True)
attr("name", 205, 175, E)
attr("department", 335, 200, E)
attr("phone", 200, 440, E)

attr("card_id", 560, 190, C, key=True)
attr("card_no", 700, 172, C)
attr("issue_date", 845, 190, C)
attr("expiry_date", 560, 430, C)
attr("status", 655, 470, C)

attr("gate_id", 1035, 190, G, key=True)
attr("gate_name", 1170, 172, G)
attr("location", 1300, 195, G)
attr("type", 1310, 320, G)
attr("status", 1270, 420, G)

attr("scan_id", 755, 705, A, key=True)
attr("scan_time", 1140, 635, A)
attr("access_result", 1150, 712, A)

attr("incident_id", 745, 975, I, key=True)
attr("detected_time", 750, 1075, I)
attr("severity", 880, 1145, I)
attr("status", 1025, 1145, I)

# ---------------- attributes: MongoDB ----------------
X1, X2 = 1840, 2040
obs = [("obs_id", True), ("method", False), ("observed_count", False), ("authorized_count", False),
       ("timestamp", False), ("observed_by", False)]
for k, (n, key) in enumerate(obs):
    attr(n, X1, 345 + 40 * k, O, key=key)
loc = attr("location", X1, 600, O)
for k, n in enumerate(["gate_id", "gate_name", "scan_id"]):
    attr(n, X2, 560 + 40 * k, loc, small=True)
attr("tags", X1, 665, O, multi=True)

attr("report_id", X1, 760, R, key=True)
attr("description", X1, 800, R)
attr("timestamp", X1, 840, R)
rb = attr("reported_by", X1, 890, R)
for k, n in enumerate(["username", "role"]):
    attr(n, X2, 865 + 46 * k, rb, small=True)
att = attr("attachments", X1, 965, R, multi=True)
for k, n in enumerate(["file_name", "file_type", "note"]):
    attr(n, X2, 945 + 38 * k, att, small=True)

for k, (n, key) in enumerate([("alert_id", True), ("alert_time", False), ("alert_type", False),
                              ("severity", False), ("message", False), ("ack_status", False)]):
    attr(n, X1, 1070 + 40 * k, L_, key=key)
attr("recipients", X1, 1318, L_, multi=True)
ack = attr("acknowledged", X1, 1380, L_)
for k, n in enumerate(["by", "at", "comment"]):
    attr(n, X2, 1335 + 40 * k, ack, small=True)

# ---------------- legend ----------------
lg = ['<rect x="40" y="1160" width="740" height="260" rx="10" fill="#fff" stroke="#cbd5e1"/>',
      '<text x="60" y="1192" class="lg-t">Legend</text>',
      '<rect x="60" y="1210" width="70" height="30" rx="3" fill="#dbeafe" stroke="#1d4ed8" stroke-width="2"/>',
      '<text x="145" y="1231" class="lg">Entity (PostgreSQL)</text>',
      '<rect x="330" y="1210" width="70" height="30" rx="3" fill="#dcfce7" stroke="#15803d" stroke-width="2"/>',
      '<text x="415" y="1231" class="lg">Entity (MongoDB)</text>',
      '<ellipse cx="95" cy="1268" rx="35" ry="15" class="ov"/><text x="145" y="1273" class="lg">Attribute</text>',
      '<ellipse cx="365" cy="1268" rx="35" ry="15" class="ov"/>'
      '<text x="365" y="1273" class="attr-s" text-decoration="underline" font-weight="700">key</text>'
      '<text x="415" y="1273" class="lg">Key attribute (PK)</text>',
      '<ellipse cx="95" cy="1310" rx="40" ry="20" class="ov"/><ellipse cx="95" cy="1310" rx="35" ry="15" class="ov"/>'
      '<text x="145" y="1315" class="lg">Multivalued (array)</text>',
      '<polygon points="365,1292 400,1310 365,1328 330,1310" fill="#ede9fe" stroke="#6d28d9" stroke-width="2"/>'
      '<text x="415" y="1315" class="lg">Relationship</text>',
      '<line x1="62" y1="1352" x2="128" y2="1352" class="ln"/><line x1="62" y1="1358" x2="128" y2="1358" class="ln"/>'
      '<text x="145" y="1360" class="lg">Total participation</text>',
      '<line x1="332" y1="1355" x2="398" y2="1355" class="ln"/><text x="415" y="1360" class="lg">Partial participation</text>',
      '<text x="60" y="1400" class="lg">1 / N = cardinality · composite = ellipse with child ellipses · '
      'FKs are shown as relationships, not attributes</text>']
out.extend(lg)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       '<style>'
       '.ln{stroke:#334155;stroke-width:1.6}'
       '.ov{fill:#fff;stroke:#64748b;stroke-width:1.6}'
       '.ent{font:700 21px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#0f172a}'
       '.rel{font:italic 600 16px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#4c1d95}'
       '.attr{font:15px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#0f172a}'
       '.attr-s{font:13px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#334155}'
       '.card{font:700 20px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#b91c1c}'
       '.region{fill:none;stroke-width:2;stroke-dasharray:10 6}.pg{stroke:#93c5fd}.mg{stroke:#86efac}'
       '.region-t{font:700 19px Segoe UI,Arial,sans-serif}'
       '.title{font:700 30px Segoe UI,Arial,sans-serif;text-anchor:middle;fill:#0f172a}'
       '.lg-t{font:700 17px Segoe UI,Arial,sans-serif;fill:#0f172a}.lg{font:14px Segoe UI,Arial,sans-serif;fill:#0f172a}'
       '</style>'
       '<rect width="100%" height="100%" fill="#ffffff"/>'
       f'<text x="{W / 2}" y="52" class="title">GateSentry – ER Diagram (Tailgating Detection)</text>'
       + "".join(lines) + "".join(out) + '</svg>')

here = Path(__file__).parent
(here / "er_diagram.svg").write_text(svg, encoding="utf-8")
(here / "er_diagram.html").write_text(
    f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0;background:#fff}}</style>'
    f'</head><body>{svg}</body></html>', encoding="utf-8")
print("wrote", here / "er_diagram.svg")
