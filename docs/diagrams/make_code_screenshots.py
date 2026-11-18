"""Build syntax-highlighted "editor" pages of real code excerpts for the report.

    python docs/diagrams/make_code_screenshots.py
then each docs/diagrams/code/*.html is rendered to docs/screenshots/code_*.png by render.mjs
(run_all in this script does both).
Excerpts are cut from the actual source files between two marker lines, so the
screenshots always show the current code with its real line numbers.
"""
import html
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "code"
SHOTS = ROOT / "docs" / "screenshots"

# (output name, caption, file, language, start marker, end marker - inclusive)
SNIPPETS = [
    ("code_01_ddl", "PostgreSQL DDL – tables with PK, FK, UNIQUE, CHECK, DEFAULT",
     "database/postgres/01_schema.sql", "sql",
     "CREATE TABLE cards (", "        REFERENCES gates(gate_id) ON DELETE RESTRICT"),
    ("code_02_trigger", "PostgreSQL trigger – every card scan is validated",
     "database/postgres/02_functions_triggers.sql", "sql",
     "CREATE OR REPLACE FUNCTION fn_validate_access_log()", "    FOR EACH ROW EXECUTE FUNCTION fn_validate_access_log();"),
    ("code_03_function", "PostgreSQL stored function – report a tailgating incident",
     "database/postgres/02_functions_triggers.sql", "sql",
     "CREATE OR REPLACE FUNCTION fn_report_tailgating(", "$$;\n\n-- ====="),
    ("code_04_rbac", "PostgreSQL role-based access control – GRANTs per role",
     "database/postgres/03_roles.sql", "sql",
     "-- ---------------- Admin: everything ----------------", "-- NOTE: viewers get NO INSERT / UPDATE / DELETE and NO procedures."),
    ("code_05_recursive", "Recursive CTE – tailgating burst chains",
     "database/postgres/05_queries.sql", "sql",
     "-- Q15 RECURSIVE CTE", "HAVING COUNT(*) > 1;"),
    ("code_06_mongo_schema", "MongoDB collection creation – $jsonSchema validator",
     "backend/app/mongo_setup.py", "python",
     "VALIDATORS = {", '    REPORT: {'),
    ("code_07_mongo_aggregation", "MongoDB read with filters and aggregation pipeline",
     "backend/app/routers/observations.py", "python",
     '@router.get("")', '    return {"per_gate": per_gate, "per_method": per_method}'),
    ("code_08_integration", "Backend – SQL incident + MongoDB documents in one transaction",
     "backend/app/routers/incidents.py", "python",
     '@router.post("/report-tailgating", status_code=201)', '            "alert_id": alert["alert_id"]}'),
    ("code_09_db_roles", "Backend – every request runs with the user's database role",
     "backend/app/db.py", "python",
     'ROLE_TO_PG = {', '        yield conn'),
    ("code_10_auth", "Backend – login verified by PostgreSQL, role from membership",
     "backend/app/auth.py", "python",
     "def verify_credentials(", '    return None\n\n\ndef create_token'),
    ("code_11_nextjs", "Next.js – incidents page loading real data through the API",
     "frontend/src/app/(app)/incidents/page.tsx", "typescript",
     "function IncidentsInner() {", "  }\n\n  async function saveEdit"),
]


def excerpt(path: Path, start: str, end: str):
    text = path.read_text(encoding="utf-8")
    i = text.index(start)
    j = text.index(end, i) + len(end)
    chunk = text[i:j]
    # if the end marker spans into the next block, keep only up to its first line
    if "\n\n" in end:
        chunk = text[i:text.index(end, i) + len(end.split("\n")[0])]
    first_line = text[:i].count("\n") + 1
    return chunk.rstrip("\n"), first_line


def page(caption, rel, lang, code, first):
    nums = "\n".join(str(n) for n in range(first, first + code.count("\n") + 1))
    return f'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs2015.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
body{{margin:0;background:#0b1220;font-family:"Segoe UI",Arial,sans-serif;width:1240px}}
.win{{margin:22px;border-radius:10px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.45);border:1px solid #2b3445}}
.bar{{background:#1f2633;color:#cbd5e1;padding:9px 14px;font-size:14px;display:flex;align-items:center;gap:8px}}
.dot{{width:12px;height:12px;border-radius:50%;display:inline-block}}
.file{{margin-left:10px;color:#e2e8f0;font-family:Consolas,monospace}}
.cap{{margin-left:auto;color:#93c5fd;font-weight:600}}
.body{{display:flex;background:#1e1e1e}}
pre{{margin:0;padding:14px 0;font:14px/1.5 Consolas,"Cascadia Mono",monospace}}
.ln{{color:#6e7681;text-align:right;padding:14px 12px 14px 16px;user-select:none;border-right:1px solid #2d2d2d;background:#1a1a1a}}
code.hljs{{padding:0 18px !important;background:#1e1e1e !important;white-space:pre}}
</style></head><body><div class="win">
<div class="bar"><span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span>
<span class="dot" style="background:#28c840"></span><span class="file">{html.escape(rel)}</span><span class="cap">{html.escape(caption)}</span></div>
<div class="body"><pre class="ln">{nums}</pre><pre><code class="language-{lang}">{html.escape(code)}</code></pre></div>
</div><script>hljs.highlightAll();</script></body></html>'''


def run_all():
    OUT.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    for name, caption, rel, lang, start, end in SNIPPETS:
        code, first = excerpt(ROOT / rel, start, end)
        src = OUT / f"{name}.html"
        src.write_text(page(caption, rel, lang, code, first), encoding="utf-8")
        subprocess.run(["node", str(ROOT / "docs/diagrams/render.mjs"), str(src),
                        str(SHOTS / f"{name}.png"), "1284", "1.5"], check=True)


if __name__ == "__main__":
    run_all()
