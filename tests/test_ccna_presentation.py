"""Synthetic public fixtures; private CCNA conversation is never a test artifact."""
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anki_generator as engine


def test_collapsible_explanation_and_safe_semantic_highlights():
    value = '<details open onclick="bad()"><summary>Explicação</summary><div class="k-h unknown">Conceito</div><span class="k-key">22</span><code class="k-cmd">show ip ssh</code><script>bad()</script></details>'
    safe, _ = engine.sanitize_html(value, set())
    assert '<details><summary>Explicação</summary>' in safe
    assert '<div class="k-h">' in safe and '<span class="k-key">22</span>' in safe
    assert '<code class="k-cmd">' in safe
    assert 'onclick' not in safe and 'unknown' not in safe and 'bad()' not in safe
    assert '<details open' not in safe


def test_generated_package_keeps_collapsed_explanation_and_cli(tmp_path):
    content = '<b>Correct answer:</b> B. 22<details><summary>Explicação detalhada</summary><p>O SSH usa a porta <span class="k-key">22</span>.</p><pre><code>R1(config)# ip ssh version 2\nR1# show ip ssh</code></pre></details>'
    cards = engine.parse_cards(json.dumps([{'id_conceito': 'sample_ssh', 'pergunta': 'Which port does SSH use?\nA. 21\nB. 22', 'resposta': content, 'tags': []}]), {})
    target = tmp_path / 'sample.apkg'
    engine.write_apkg(cards, {}, 'Synthetic', target, 'paper')
    with zipfile.ZipFile(target) as archive:
        db = tmp_path / 'collection.anki2'
        db.write_bytes(archive.read('collection.anki2'))
    with sqlite3.connect(db) as con:
        fields = con.execute('select flds from notes').fetchone()[0]
        models = con.execute('select models from col').fetchone()[0]
    assert '<details><summary>' in fields and 'class="k-key"' in fields
    assert 'version 2\nR1#' in fields
    assert 'summary' in models and '.k-key' in models
