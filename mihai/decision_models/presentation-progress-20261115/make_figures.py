"""Render presentation figures from audited results; no model inference."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Render files without opening a display on the cluster.
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / 'comparison.json').read_text())
NAVY, TEAL, ORANGE = '#304E78', '#008C86', '#CB6B27'
INK, GRAY, GRID = '#172B40', '#526579', '#E4EBF1'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 16,
                     'text.color': INK, 'axes.labelcolor': INK,
                     'xtick.color': GRAY, 'ytick.color': INK,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})

def base(title, subtitle):
    fig = plt.figure(figsize=(16, 9), facecolor='white')
    fig.text(.055, .92, title, fontsize=28, weight='bold')
    fig.text(.055, .865, subtitle, fontsize=17, color=GRAY)
    return fig

def clean(ax):
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.tick_params(length=0, pad=10)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color=GRID)

def save(fig, name):
    for extension in ['png', 'svg', 'pdf']:
        fig.savefig(HERE / f'{name}.{extension}', dpi=200, facecolor='white')
    plt.close(fig)

rows = []
for scope in ['action', 'cot', 'all']:
    for model, method in [('Qwen3-32B', 'four independent sampled analyses'),
                          ('GLiDE-9B', 'sampled'), ('GLiDE-9B', 'greedy')]:
        matches = [r for r in D['rows'] if (r['scope'], r['model'], r['method']) == (scope, model, method)]
        rows.extend(matches)
y = [8, 7, 6, 4.5, 3.5, 2.5, 1]
labels = []
colors = []
for r in rows:
    scope = {'action': 'Actions', 'cot': 'CoT', 'all': 'Combined'}[r['scope']]
    method = 'Qwen32B, sampled' if r['model'] == 'Qwen3-32B' else 'GLiDE, ' + ('most likely' if r['method'] == 'greedy' else 'sampled')
    labels.append(f'{scope}  /  {method}')
    colors.append(NAVY if r['model'] == 'Qwen3-32B' else ORANGE if r['method'] == 'greedy' else TEAL)
fig = base('GLiDE’s decision rule matters most on reasoning',
           'Same 75 rollouts • 150 monitoring cases per input type • Observed results on three tasks')
for i, (key, title) in enumerate([('detection', 'Detection ↑'), ('clean_false_alarm', 'Clean false alarms ↓')]):
    ax = fig.add_axes([.32 + i*.285, .225, .24, .55])
    values = [r[key]*100 for r in rows]
    ax.barh(y, values, height=.55, color=colors)
    for yy, value in zip(y, values):
        ax.text(value+1.8, yy, f'{value:.1f}%', va='center', fontsize=15, weight='bold')
    ax.set_xlim(0, 119); ax.set_xticks([0, 25, 50, 75, 100]); ax.xaxis.set_major_formatter(PercentFormatter())
    ax.set_ylim(.2, 8.8); ax.set_yticks(y)
    ax.set_yticklabels(labels if i == 0 else ['']*7, fontsize=15)
    ax.set_title(title, loc='left', fontsize=19, weight='bold', pad=20)
    clean(ax)
    if i == 1:
        ax.text(1.2, 1.055, 'G-mean² ↑', transform=ax.transAxes, ha='center', fontsize=18, weight='bold')
        for yy, r in zip(y, rows):
            ax.text(1.2, yy, f"{r['gmean2']:.3f}", transform=ax.get_yaxis_transform(), ha='center', va='center', fontsize=17, weight='bold')
fig.text(.055, .143, 'Actions: similar overall scores.   CoT: sampling misses more positives; most-likely decisions improve recall.', fontsize=17, weight='bold')
fig.text(.055, .096, 'G-mean² = detection × (1 − false alarms). Main groups: 41 positive + 66 clean cases; sampled rules use four answers each.', fontsize=13, color=GRAY)
fig.text(.055, .063, 'Qwen generates four analyses; GLiDE draws four labels from one probability vector. No Qwen most-likely or GLiDE combined run.', fontsize=13, color=GRAY)
save(fig, '01-detection-and-false-alarms')

fig = base('Full reasoning fits; reliable detection is the next question',
           'GLiDE completed all 150 CoT cases after resuming • Full inputs, without hierarchical summaries')
ax = fig.add_axes([.22, .27, .34, .48])
t = D['timing']
values = [t['glide_gpu_job_seconds']['action']/60, t['qwen_approximate_seconds_by_scope']['action']/60,
          t['glide_gpu_job_seconds']['cot']/60, t['qwen_approximate_seconds_by_scope']['cot']/60,
          t['qwen_approximate_seconds_by_scope']['all']/60]
ys = [5.5, 4.6, 3.2, 2.3, .9]
ax.barh(ys, values, color=[TEAL,NAVY,TEAL,NAVY,NAVY], height=.55)
for yy, v, approx in zip(ys, values, [False,True,False,True,True]):
    ax.text(v+3, yy, ('≈ ' if approx else '') + f'{v:.1f} min', va='center', fontsize=16, weight='bold')
ax.set_yticks(ys); ax.set_yticklabels(['Actions / GLiDE','Actions / Qwen32B','CoT / GLiDE','CoT / Qwen32B','Combined / Qwen32B'], fontsize=15)
ax.set_xlim(0, 220); ax.set_xticks([0,50,100,150,200]); ax.set_ylim(.2,6.2)
ax.set_xlabel('Recorded runtime (minutes)', fontsize=15)
ax.set_title('Observed evaluation time', loc='left', fontsize=20, weight='bold', pad=20)
clean(ax)
fig.text(.65, .74, '216,463 tokens', fontsize=30, color=TEAL, weight='bold')
fig.text(.65, .695, 'Longest full CoT prompt evaluated', fontsize=17)
fig.text(.65, .59, '150 / 150 cases', fontsize=30, color=TEAL, weight='bold')
fig.text(.65, .545, '75 rollouts × two target objectives', fontsize=17)
fig.text(.65, .44, '93.1 GiB reserved', fontsize=27, color=TEAL, weight='bold')
fig.text(.65, .395, 'Peak GPU reservation; 50.5 GiB allocated', fontsize=16)
fig.text(.65, .31, 'Long inputs fit.\nReliable use of evidence still needs testing.', fontsize=16, weight='bold', linespacing=1.4)
fig.text(.055, .16, 'Runtime compares the systems we ran, not model speed under identical conditions. GLiDE combined is untested.', fontsize=15, weight='bold')
fig.text(.055, .112, 'GLiDE: RTX PRO 6000, serial calls; both decision rules share inference. CoT includes 27m interrupted + 39m continuation.', fontsize=13, color=GRAY)
fig.text(.055, .078, 'Qwen: H200, up to 32 concurrent judgments, four analyses and hierarchy. Scope times are approximate because work overlapped.', fontsize=13, color=GRAY)
fig.text(.055, .044, 'Source: audited saved evaluations, November 15, 2026. Zero final case errors; the initial process exit remains unexplained.', fontsize=13, color=GRAY)
save(fig, '02-runtime-and-context')
