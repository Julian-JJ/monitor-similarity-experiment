"""Create a slide-ready table from verified metrics, without model inference."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
D = json.loads((HERE.parent / 'comparison.json').read_text())
INK, GRAY, TEAL = '#172B40', '#607285', '#008C86'
plt.rcParams.update({'font.family':'DejaVu Sans','text.color':INK,
                     'svg.fonttype':'none','pdf.fonttype':42})
rows=[]
for scope in ['action','cot','all']:
    for model, method in [('Qwen3-32B','four independent sampled analyses'),('GLiDE-9B','sampled'),('GLiDE-9B','greedy')]:
        match=[r for r in D['rows'] if (r['scope'],r['model'],r['method'])==(scope,model,method)]
        if not match: continue
        r=match[0]
        c=r['points']['pooled']['counts']
        tp, positives=c['positive']['detected'],c['positive']['valid']
        fp, negatives=c['clean_negative']['detected'],c['clean_negative']['valid']
        assert abs((tp+negatives-fp)/(positives+negatives)-r['positive_and_clean_accuracy']) < 1e-12
        rows.append([{'action':'Actions','cot':'CoT','all':'Combined'}[scope],
                     'Qwen32B' if model=='Qwen3-32B' else 'GLiDE',
                     'Most likely' if method=='greedy' else 'Sampled',
                     f"{r['detection']*100:.1f}%", f"{r['clean_false_alarm']*100:.1f}%",
                     f"{r['positive_and_clean_accuracy']*100:.1f}%", f"{r['gmean2']:.3f}"])
rows.append(['Combined','GLiDE','Not tested','—','—','—','—'])
fig=plt.figure(figsize=(16,9),facecolor='white')
fig.text(.065,.915,'Monitor results at a glance',fontsize=32,weight='bold')
fig.text(.065,.85,'TPR = detection rate  •  FPR = false-alarm rate on clean cases',fontsize=22,color=GRAY)
ax=fig.add_axes([.065,.265,.87,.51]); ax.axis('off')
table=ax.table(cellText=rows,colLabels=['Input','Monitor','Answer rule','TPR ↑','FPR ↓','Accuracy* ↑','G-mean² ↑'],
               colWidths=[.13,.145,.17,.13,.13,.155,.14],cellLoc='center',bbox=[0,0,1,1])
table.auto_set_font_size(False); table.set_fontsize(20)
for (row,col),cell in table.get_celld().items():
    cell.set_linewidth(0)
    cell.PAD=.08
    if row==0:
        cell.set_facecolor('#172B40'); cell.get_text().set_color('white'); cell.get_text().set_weight('bold')
    else:
        cell.set_facecolor('#F1F5F8' if row<=3 or row>=7 else '#FFFFFF')
        cell.get_text().set_color(GRAY if row==8 else INK)
        if col==1 and rows[row-1][1]=='GLiDE' and row!=8: cell.get_text().set_color(TEAL)
        if col>=3 and row!=8: cell.get_text().set_weight('bold')
fig.text(.065,.19,'*Accuracy = correct answers on 41 positive + 66 clean cases, pooled across both objectives.',fontsize=17,color=GRAY)
fig.text(.065,.145,'Sampled: 428 answers across those cases. Most likely: 107 answers. Other scoring groups excluded.',fontsize=17,color=GRAY)
fig.text(.065,.10,'Same 75 rollouts. Qwen generates four analyses; GLiDE samples four labels from one probability vector.',fontsize=17,color=GRAY)
fig.text(.065,.055,'G-mean² = TPR × (1 − FPR). Different input processing; no matching most-likely Qwen evaluation.',fontsize=17,color=GRAY)
for ext in ['png','svg','pdf']:
    fig.savefig(HERE/f'03-results-table.{ext}',dpi=200,facecolor='white')
(HERE/'results-table.json').write_text(json.dumps({'columns':['Input','Monitor','Answer rule','TPR','FPR','Accuracy_positive_and_clean','Gmean2'],'rows':rows},indent=2)+'\n')
