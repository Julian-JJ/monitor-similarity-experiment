"""Plot the compact summary, without reading any raw reasoning text."""
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib

matplotlib.use('Agg')  # Draw to files without opening a desktop window.
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

folder = Path(sys.argv[1])
rows = json.loads((folder / 'summary.json').read_text())['measurements']
x = [r['target'] / 1000 for r in rows]
fig = plt.figure(figsize=(12, 7.8), layout='constrained')
grid = fig.add_gridspec(2, 2, height_ratios=[2.2, 1.2])
timing = fig.add_subplot(grid[0, 0])
memory = fig.add_subplot(grid[0, 1])
checks = fig.add_subplot(grid[1, :])

def values(key, scale=1):
    return [r[key] / scale if r.get(key) is not None else np.nan for r in rows]

timing.plot(x, values('first_call_seconds'), 'o--', color='#94a3b8', label='First call in process')
timing.plot(x, values('warm_mean_seconds'), 'o-', color='#2563eb', label='Mean of two warm calls')
timing.set(title='Runtime per reasoning check', ylabel='Seconds', xlabel='Full prompt length (thousands of tokens)')
timing.legend(frameon=False)
memory.plot(x, values('peak_reserved_bytes', 2**30), 'o--', color='#94a3b8', label='Reserved by PyTorch')
memory.plot(x, values('peak_allocated_bytes', 2**30), 'o-', color='#059669', label='Peak allocated')
memory.set(title='Peak GPU memory, including model weights', ylabel='GiB', xlabel='Full prompt length (thousands of tokens)')
memory.legend(frameon=False)
for ax in [timing, memory]:
    ax.axvline(40, color='#64748b', linewidth=1, linestyle=':')
    ax.text(40, 0.6, ' default 40k', transform=ax.get_xaxis_transform(), va='top', color='#64748b', fontsize=9)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.18)
    ax.spines[['top', 'right']].set_visible(False)

names = ['synthetic_beginning', 'synthetic_middle', 'synthetic_end', 'synthetic_absent']
labels = ['Evidence near beginning', 'Evidence near middle', 'Evidence near end', 'Clean control left unflagged']
matrix = np.full((4, len(rows)), np.nan)
probabilities = np.full_like(matrix, np.nan)
for j, row in enumerate(rows):
    for item in row['synthetic']:
        matrix[names.index(item['id']), j] = int(item['correct'])
        probabilities[names.index(item['id']), j] = item['p_A']
cmap = ListedColormap(['#fed7aa', '#a7f3d0'])
cmap.set_bad('#e2e8f0')
checks.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect='auto', interpolation='nearest')
checks.set_xticks(range(len(rows)), [f'{r["target"] / 1000:g}k' for r in rows])
checks.set_yticks(range(4), labels)
checks.set_title('Controlled checks using the highest-probability answer: one synthetic scenario', loc='left', pad=12)
for i in range(4):
    for j in range(len(rows)):
        text = 'Not run' if np.isnan(matrix[i, j]) else (
            ('OK' if matrix[i, j] else 'Miss') + f'\nA={probabilities[i, j]:.2f}')
        checks.text(j, i, text, ha='center', va='center', fontsize=8)
checks.tick_params(length=0)
for spine in checks.spines.values():
    spine.set_visible(False)
fig.suptitle('GLiDE-9B: reasoning length pilot on one Blackwell GPU', fontsize=16)
fig.supxlabel('Cells show decision correctness and model P(A). Synthetic checks are not benchmark accuracy.\n'
              'Memory excludes some driver overhead.', fontsize=9, color='#475569')
fig.savefig(folder / 'length-pilot.png', dpi=180)
fig.savefig(folder / 'length-pilot.svg')
