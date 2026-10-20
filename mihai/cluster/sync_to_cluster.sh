#!/usr/bin/env bash
# Copy this working tree to the cluster's framework directory and record WHICH code was copied, because the cluster copy has no .git.
# Run on your Mac, with the SSH connection open (ControlMaster socket). Writes .sync-commit.json (git-ignored) with the commit, branch and
# whether the tree had uncommitted changes; the runner records it in every run manifest. See docs/system/cluster.md.
set -euo pipefail
cd "$(dirname "$0")/../.."
ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
HOST="${HOST:-cpsc4880_as4833@bouchet.ycrc.yale.edu}"
DEST="${DEST:-$ME/monitor-framework/}"
dirty=false
[[ -n "$(git status --porcelain)" ]] && dirty=true
printf '{"commit": "%s", "branch": "%s", "dirty": %s, "synced_at": "%s"}\n' "$(git rev-parse HEAD)" "$(git branch --show-current)" "$dirty" "$(date -u +%FT%TZ)" > .sync-commit.json
[[ "$dirty" == false ]] || echo "WARNING: the working tree has uncommitted changes; the manifest will say dirty=true" >&2
rsync -a --stats --exclude .git --exclude .venv --exclude cache --exclude rollouts_original_clean --exclude rollouts_main_only_clean \
    --exclude runs --exclude presence --exclude vendor/monitorbench_agent --exclude mihai/test_rollouts_2 --exclude __pycache__ \
    -e "ssh -o BatchMode=yes -o ControlPath=$HOME/.ssh/cm-%r@%h:%p" ./ "$HOST:$DEST" | grep -E "files transferred|Total transferred"
ssh -o BatchMode=yes -o ControlPath="$HOME/.ssh/cm-%r@%h:%p" "$HOST" "chmod +x $DEST/mihai/cluster/*.sh $DEST/mihai/cluster/*.sbatch $DEST/scripts/*.py"
cat .sync-commit.json
