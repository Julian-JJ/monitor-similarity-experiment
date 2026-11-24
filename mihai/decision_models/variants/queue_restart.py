"""Queue the user-authorized DAG, with durable one-shot receipts and success gates."""
import json,shlex,subprocess
from pathlib import Path
root=Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
release=root/'releases/decision-variants-d98ee84c398bee9b'
logs=root/'logs'; py=root/'envs/monitor-research/bin/python'
sha='d98ee84c398bee9b90f66132b15a8c5fd53476d97534a0d5a1f9569cbde0a616'

def submit(label,kind,dependency,stages,limit,smoke=False):
    resources=['--partition=devel','--cpus-per-task=4','--mem=48G'] if kind=='cpu' else (
       ['--partition=gpu_h200','--gpus=h200:1','--cpus-per-task=6','--mem=96G'] if kind=='qwen' else
       ['--partition=gpu_rtx6000','--gpus=rtx_pro_6000_blackwell:1','--cpus-per-task=4','--mem=96G'])
    name='decision-variants-20261123-v3-'+label
    label='v3-'+label
    args=[*resources,'--account=cpsc4880','--nodes=1','--ntasks=1','--no-requeue',
          '--time='+limit,'--kill-on-invalid-dep=yes',
          '--output='+str(logs/f'decision-variants-{label}-%j.log')]
    if dependency: args.append('--dependency='+dependency)
    if len(stages)==1:
        args += ['/nfs/roberts/project/cpsc4880/cpsc4880_mae73/releases/decision-variants-launcher-9d68d6231103ec24/run.sbatch',stages[0],str(release/'config.json'),str(root)]
        if smoke:args.append('smoke')
    else:
        commands=[shlex.join(['bash','/nfs/roberts/project/cpsc4880/cpsc4880_mae73/releases/decision-variants-launcher-9d68d6231103ec24/run.sbatch',s,str(release/'config.json'),str(root)]+(['smoke'] if smoke else [])) for s in stages]
        wrapped='failed=0\n'+'\n'.join(c+' || failed=1' for c in commands)+'\nexit "$failed"\n'
        args += ['--wrap='+wrapped]
    spec={'logs':str(logs),'name':name,'source_manifest_sha256':sha,'launcher_sha256':'9d68d6231103ec247ae99193a6990df22dd568cab11f750f475e1dc3e873ea3a','arguments':args}
    path=logs/f'decision-variants-{label}-spec.json';path.write_text(json.dumps(spec,indent=2)+'\n')
    result=subprocess.run([str(py),'-B',str(logs/'submit_job.py'),str(path)],check=True,capture_output=True,text=True,timeout=60)
    receipt=json.loads(result.stdout);receipt=receipt.get('existing_receipt',receipt)
    print(json.dumps({'stage':label,'job_id':receipt['job_id'],'dependency':dependency}),flush=True)
    return receipt['job_id']

qsmoke=submit('qwen-smoke-cpu6','qwen',None,['qwen'],'02:00:00',True)
gsmoke=submit('glide-smoke','glide','afterok:'+qsmoke,['glide-chunks','glide-full','glide-summaries'],'02:00:00',True)
qfull=submit('qwen-production','qwen','afterok:'+qsmoke,['qwen'],'12:00:00')
gfull=submit('glide-production','glide','afterok:'+gsmoke,['glide-chunks','glide-full'],'06:00:00')
gsummaries=submit('glide-summaries','glide','afterok:'+gsmoke+',afterany:'+qfull,['glide-summaries'],'03:00:00')
score=submit('score','cpu','afterany:'+':'.join([qfull,gfull,gsummaries]),['score'],'01:00:00')
