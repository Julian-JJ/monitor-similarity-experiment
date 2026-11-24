"""Simplified figures from the audited comparison; no inference."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
D = json.loads((HERE.parent / 'comparison.json').read_text())
NAVY, TEAL, ORANGE = '#304E78', '#008C86', '#CB6B27'
INK, GRAY, GRID = '#172B40', '#607285', '#E7EDF2'
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':20,
                    'text.color':INK, 'axes.labelcolor':GRAY, 'xtick.color':INK,
                    'ytick.color':GRAY, 'svg.fonttype':'none', 'pdf.fonttype':42})

def figure(title, subtitle):
    fig = plt.figure(figsize=(16,9),facecolor='white')
    fig.text(.07,.91,title,fontsize=30,weight='bold')
    fig.text(.07,.85,subtitle,fontsize=21,color=GRAY)
    return fig

def clean(ax, direction):
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.tick_params(length=0,pad=13)
    ax.set_axisbelow(True)
    ax.grid(axis=direction,color=GRID)

def save(fig,name):
    for ext in ['png','svg','pdf']:
        fig.savefig(HERE / f'{name}.{ext}',dpi=200,facecolor='white')
    plt.close(fig)

fig=figure('On reasoning, the answer rule changes the result',
           'Monitor score (G-mean²) balances detection and false alarms. Higher is better.')
ax=fig.add_axes([.11,.25,.80,.44])
methods=[('Qwen3-32B','four independent sampled analyses','Qwen32B · sampled',NAVY),
         ('GLiDE-9B','sampled','GLiDE · sampled',TEAL),
         ('GLiDE-9B','greedy','GLiDE · most likely',ORANGE)]
for j,(model,method,label,color) in enumerate(methods):
    values=[next(r['gmean2'] for r in D['rows'] if (r['scope'],r['model'],r['method'])==(scope,model,method)) for scope in ['action','cot']]
    xs=[x+(j-1)*.23 for x in [0,1]]
    ax.bar(xs,values,width=.19,color=color)
    for x,v in zip(xs,values): ax.text(x,v+.025,f'{v:.3f}',ha='center',fontsize=23,weight='bold')
ax.set_ylim(0,1); ax.set_xlim(-.55,1.55)
ax.set_yticks([0,.5,1]); ax.set_yticklabels(['0','0.5','1.0'])
ax.set_xticks([0,1]); ax.set_xticklabels(['Actions','Reasoning (CoT)'],fontsize=25,weight='bold')
clean(ax,'y')
fig.legend(handles=[Patch(color=m[3],label=m[2]) for m in methods],loc='upper center',bbox_to_anchor=(.52,.79),ncol=3,frameon=False,fontsize=20,handlelength=1)
fig.text(.07,.12,'Same 75 rollouts. Qwen’s most-likely rule and GLiDE’s combined input are not yet tested.',fontsize=17,color=GRAY)
fig.text(.07,.075,'Qwen generates four analyses; GLiDE samples four labels from one probability vector.',fontsize=17,color=GRAY)
save(fig,'01-monitor-quality-simple')

fig=figure('GLiDE took less time in our evaluated setup',
           'Total evaluation time in minutes • Shorter is better')
ax=fig.add_axes([.20,.29,.66,.39])
t=D['timing']
for scope,y in [('action',1),('cot',0)]:
    glide=t['glide_gpu_job_seconds'][scope]/60
    qwen=t['qwen_approximate_seconds_by_scope'][scope]/60
    for yy,v,color,approx in [(y+.16,glide,TEAL,False),(y-.16,qwen,NAVY,True)]:
        ax.barh(yy,v,height=.25,color=color)
        label=f'{v:.0f} min' if not approx else f'≈ {v:.0f} min'
        ax.text(v+3,yy,label,va='center',fontsize=24,weight='bold')
ax.set_ylim(-.5,1.5); ax.set_xlim(0,195)
ax.set_yticks([1,0]); ax.set_yticklabels(['Actions','Reasoning\n(CoT)'],fontsize=24)
ax.set_xticks([0,50,100,150]); clean(ax,'x')
fig.legend(handles=[Patch(color=TEAL,label='GLiDE'),Patch(color=NAVY,label='Qwen32B')],loc='upper center',bbox_to_anchor=(.52,.79),ncol=2,frameon=False,fontsize=22,handlelength=1)
fig.text(.07,.19,'Full GLiDE CoT: 150 / 150 cases completed · Up to 216k input tokens',fontsize=22,weight='bold')
fig.text(.07,.12,'Different GPUs and procedures: observed runtime, not a controlled model-speed comparison.',fontsize=17,color=GRAY)
fig.text(.07,.075,'Qwen times are estimates; GLiDE CoT includes the interrupted run and continuation.',fontsize=17,color=GRAY)
save(fig,'02-runtime-simple')
