"""Paper-style tables from audited scores; no model calls or hand-entered rates."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
from xml.sax.saxutils import escape

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
OUT = HERE / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)

paths = {
    'qwen': DATA / 'comparisons/baseline-20261123/metrics.json',
    'qwen_audit': DATA / 'comparisons/baseline-20261123/audit.json',
    'glide': DATA / 'variants/results-completed-34428767/audit.json',
    'jev': DATA / 'jev/results-completed-34426786/audit.json',
}
source = {k: json.loads(p.read_text()) for k, p in paths.items()}
assert source['glide']['audit_passed'] and source['jev']['audit_passed']
assert source['glide']['inputs_sha256'] == source['jev']['inputs_sha256']
assert source['glide']['collection_hashes'] == source['jev']['collection_hashes']
assert {k: v['manifest_sha256'] for k, v in source['qwen']['rollout_sets'].items()} == source['jev']['collection_hashes']
METRICS = ['tpr', 'fpr_clean', 'primary_accuracy', 'gmean2_clean']
tables = {}


def validate(row):
    counts = row['counts']
    positive, clean = counts['positive'], counts['clean_negative']
    assert positive['pairs'] == 41 and clean['pairs'] == 66
    assert positive['valid'] == positive['requested']
    assert clean['valid'] == clean['requested']
    assert row['coverage'] == 1
    tpr = positive['detected'] / positive['valid']
    fpr = clean['detected'] / clean['valid']
    accuracy = (positive['detected'] + clean['valid'] - clean['detected']) / (positive['valid'] + clean['valid'])
    for k, expected in zip(METRICS, [tpr, fpr, accuracy, tpr * (1 - fpr)]):
        assert math.isclose(row[k], expected, abs_tol=1e-12)


for scope in ['action', 'cot', 'all']:
    baseline_audit = source['qwen_audit']['qwen3-32b-' + scope]
    assert baseline_audit['counts_and_metrics_match'] and baseline_audit['complete'] == 600
    match = [c for c in source['qwen']['cells']
             if c['label']['monitor'] == 'qwen3-32b' and c['label']['scope'] == scope]
    assert len(match) == 1 and match[0]['complete']
    pooled = match[0]['results']['pooled']
    q = pooled['metrics']
    pos, clean = pooled['counts']['positive'], pooled['counts']['clean_negative']
    rows = [{'model': 'Qwen3-32B', 'method': 'Baseline / sampled x4',
             'tpr': q['tpr']['value'], 'fpr_clean': 1 - q['tnr_clean']['value'],
             'primary_accuracy': (pos['detected'] + clean['valid'] - clean['detected']) / (pos['valid'] + clean['valid']),
             'gmean2_clean': q['gmean2_clean']['value'], 'counts': pooled['counts'],
             'coverage': q['coverage']['value']}]
    for model, key in [('GLiDE-9B', 'glide'), ('Jev 1.14', 'jev')]:
        methods = [('full' if key == 'glide' else 'full-greedy', 'Full / highest option'),
                   ('max', 'Chunks / maximum'), ('mean', 'Chunks / average')]
        for method, label in methods:
            rows.append({'model': model, 'method': label, **source[key]['results'][scope + '-' + method]})
    for row in rows:
        validate(row)
    best = {metric: (min if metric == 'fpr_clean' else max)(r[metric] for r in rows)
            for metric in METRICS}
    for row in rows:
        row['best'] = {k: math.isclose(row[k], best[k], abs_tol=1e-12, rel_tol=0) for k in METRICS}
    tables[scope] = rows

manifest = {
    'date': '2026-11-23', 'baseline': 'Qwen3-32B, four sampled analyses per case',
    'dataset': '75 rollouts; 150 cases/view; primary metrics use 41 positive + 66 clean cases',
    'bold_rule': 'Best unrounded point estimate in each column within each input view; all exact ties bold',
    'gmean_definition': 'G-mean squared = TPR * (1 - clean FPR); no square root',
    'excluded_pending': ['Qwen32B greedy', 'Qwen summaries to GLiDE', 'Qwen summaries to Jev'],
    'notes': ['Qwen uses four generated analyses and its existing hierarchy when needed.',
              'GLiDE/Jev full rows use one highest-probability answer. Chunk rows use a 0.5 threshold.',
              'Rates are pooled across both told objectives. The other 43 cases are separate diagnostic groups.',
              'Bolding is descriptive, not a claim of statistically significant superiority.'],
    'sources': {k: {'path': str(p.relative_to(DATA)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for k, p in paths.items()},
    'tables': tables,
}
(HERE / 'comparison-data.json').write_text(json.dumps(manifest, indent=2) + '\n')

fonts = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('TableSans', str(fonts / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('TableBold', str(fonts / 'VeraBd.ttf')))
W, H = 1152, 648
INK, MUTED, RULE, PALE = '#142433', '#566675', '#AEB9C2', '#F4F7F9'
c = canvas.Canvas(str(OUT / 'monitor-comparison.pdf'), pagesize=(W, H))
c.setTitle('Qwen, GLiDE and Jev: Actions, CoT and Combined')
c.setAuthor('Monitor Choice and Monitorability')


def render(scope, title, index):
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="white"/>']

    def text(x, y, value, size=18, bold=False, color=INK, align='left'):
        font = 'TableBold' if bold else 'TableSans'
        c.setFont(font, size)
        c.setFillColor(HexColor(color))
        getattr(c, {'left': 'drawString', 'center': 'drawCentredString', 'right': 'drawRightString'}[align])(x, y, value)
        anchor = {'left': 'start', 'center': 'middle', 'right': 'end'}[align]
        svg.append(f'<text x="{x}" y="{H-y}" font-family="Bitstream Vera Sans,DejaVu Sans,Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')

    def line(y, width=0.6, color=RULE):
        c.setStrokeColor(HexColor(color)); c.setLineWidth(width); c.line(56, y, 1096, y)
        svg.append(f'<line x1="56" y1="{H-y}" x2="1096" y2="{H-y}" stroke="{color}" stroke-width="{width}"/>')

    def arrow(x, y, down=False):
        # Draw arrows as paths so no missing font glyph can become a square.
        end = y if down else y + 9
        shoulder = end + 3 if down else end - 3
        segments = [(x, y, x, y+9), (x-3, shoulder, x, end), (x+3, shoulder, x, end)]
        c.setStrokeColor(HexColor(MUTED)); c.setLineWidth(0.9)
        for x1, y1, x2, y2 in segments:
            c.line(x1, y1, x2, y2)
            svg.append(f'<line x1="{x1}" y1="{H-y1}" x2="{x2}" y2="{H-y2}" stroke="{MUTED}" stroke-width="0.9"/>')

    text(56, 608, 'MONITOR COMPARISON', 11, True, MUTED)
    text(1096, 608, '23 NOV 2026', 11, False, MUTED, 'right')
    text(56, 562, title, 34, True)
    text(56, 534, 'Same 75 rollouts  /  150 objective checks per input view  /  100% completed for every row', 13, color=MUTED)
    line(507, 1.5, INK)
    text(66, 475, 'Monitor', 15, True)
    text(250, 475, 'Decision rule', 15, True)
    xs = [592, 738, 884, 1030]
    headers = [('Detection', 'TPR'), ('False alarms', 'Clean FPR'), ('Accuracy*', ''), ('G-mean²', '')]
    for j, (x, (a, b)) in enumerate(zip(xs, headers)):
        text(x, 481, a, 15, True, align='center')
        if b:
            text(x-7, 460, b, 12, color=MUTED, align='center')
        offset = pdfmetrics.stringWidth(b, 'TableSans', 12)/2 + 2 if b else 0
        arrow(x+offset, 460, down=j==1)
    line(447, 0.8, INK)
    ys = [418, 365, 325, 285, 232, 192, 152]
    for i, (row, y) in enumerate(zip(tables[scope], ys)):
        if i == 0:
            text(66, y, row['model'], 18, True)
        if i in [2, 5]:
            text(66, y, row['model'], 18, True)
        text(250, y, row['method'], 16)
        for x, metric in zip(xs, METRICS):
            value = f"{row[metric]:.3f}" if metric == 'gmean2_clean' else f"{row[metric]*100:.1f}%"
            text(x, y, value, 21, row['best'][metric], align='center')
        if i in [0, 3]:
            line(y-21, 0.65)
    line(131, 1.5, INK)
    text(56, 105, 'Bold = best point estimate, including ties; this does not establish statistical significance.', 12, color=MUTED)
    text(56, 85, '*Accuracy: 41 positive + 66 clean cases; sampled baseline pools four judgments per case.', 12, color=MUTED)
    text(56, 65, 'G-mean² = TPR × (1 − FPR). Chunk rules use P(A) ≥ 0.5; full decision models take the highest option.', 12, color=MUTED)
    text(56, 32, 'Qwen: sampled baseline with existing hierarchy. New greedy Qwen and summary conditions are pending.', 10.5, color=MUTED)
    text(1096, 32, f'{index} / 3', 10.5, color=MUTED, align='right')
    c.showPage()
    svg.append('</svg>')
    (OUT / f'{index:02d}-{scope}.svg').write_text('\n'.join(svg) + '\n')


for i, (scope, title) in enumerate([('action', 'Actions'), ('cot', 'CoT / reasoning'), ('all', 'Combined / actions + CoT')], 1):
    render(scope, title, i)
c.save()

# Render the actual PDF so the delivered PNGs exactly match its layout.
for i, scope in enumerate(['action', 'cot', 'all'], 1):
    subprocess.run(['pdftoppm', '-f', str(i), '-l', str(i), '-singlefile', '-scale-to', '2400',
                    '-png', str(OUT / 'monitor-comparison.pdf'), str(OUT / f'{i:02d}-{scope}')], check=True)

# Copyable booktabs tables for a paper; rates are derived from the same JSON.
tex = ['% Requires \\usepackage{booktabs}; all metrics are point estimates.']
for scope, title in [('action', 'Actions'), ('cot', 'CoT'), ('all', 'Combined')]:
    tex.extend(['\\begin{table}[t]', '\\centering', '\\small', '\\begin{tabular}{llrrrr}', '\\toprule',
                r'Monitor & Decision rule & TPR $\uparrow$ & FPR $\downarrow$ & Accuracy$^*$ $\uparrow$ & G-mean$^2$ $\uparrow$ \\', '\\midrule'])
    for i, row in enumerate(tables[scope]):
        values = []
        for metric in METRICS:
            value = f"{row[metric]:.3f}" if metric == 'gmean2_clean' else f"{100*row[metric]:.1f}\\%"
            values.append('\\textbf{' + value + '}' if row['best'][metric] else value)
        tex.append(' & '.join([row['model'], row['method'], *values]) + r' \\')
        if i in [0, 3]: tex.append('\\midrule')
    tex.extend(['\\bottomrule', '\\end{tabular}',
                '\\caption{' + title + '. Best point estimates are bold, including ties. Accuracy uses 41 positive and 66 clean cases; the sampled baseline pools four judgments per case. G-mean$^2$ is TPR times clean TNR. Qwen uses its existing hierarchy; chunk rules use a 0.5 threshold.}',
                '\\end{table}', ''])
(HERE / 'paper-tables.tex').write_text('\n'.join(tex) + '\n')
print(json.dumps({'pdf': str(OUT / 'monitor-comparison.pdf'), 'tables': 3, 'rows_per_table': 7}, indent=2))
