#!/usr/bin/env bash
# Install a separate, explicitly selected Docker daemon. Reuse existing/internal first.
set -euo pipefail
TASK_KIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
TASK_PYTHON="$TASK_KIT_ROOT/scripts/python.sh"
TASK_STATE="${AGENTIC_STATE:-$HOME/.local/share/agentic-stack}"
TASK_PLAN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --state) [[ $# -ge 2 ]] || exit 2; TASK_STATE="$2"; shift 2 ;;
    --artifact-plan) [[ $# -ge 2 ]] || exit 2; TASK_PLAN="$2"; shift 2 ;;
    *) echo 'Usage: bootstrap-docker.sh --artifact-plan ABSOLUTE_JSON [--state ABSOLUTE_PATH]' >&2; exit 2 ;;
  esac
done
if [[ -z "$TASK_PLAN" ]]; then
  echo 'Inspect existing/internal Docker first. A private-first --artifact-plan is required for private-daemon bootstrap.' >&2
  exit 2
fi
TASK_ARCHIVE="$("$TASK_PYTHON" "$TASK_KIT_ROOT/scripts/artifact_policy.py" --plan "$TASK_PLAN" --file dockerDaemon)"
TASK_STATE="$("$TASK_PYTHON" -c 'import os,sys;print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "$TASK_STATE")"
TASK_UID="$(id -u)"; TASK_GID="$(id -g)"
TASK_ID="$("$TASK_PYTHON" -c 'import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:10])' "$TASK_STATE")"
TASK_RUNTIME="/opt/agentic-docker-$TASK_ID"
TASK_SOCKET="/run/agentic-docker-$TASK_ID/docker.sock"
TASK_SERVICE="agentic-docker-$TASK_ID"
if [[ "$TASK_UID" == 0 ]]; then
  echo 'Run this script as the intended ordinary operator account; it uses sudo for the separate service.' >&2
  exit 2
fi
"$TASK_PYTHON" - <<'PY'
import shutil
free=shutil.disk_usage('/var/lib').free
if free<40*1024**3:raise SystemExit('Private Docker needs at least40 GiB free on /var/lib; use an existing daemon or another prepared filesystem')
PY
if ! command -v sudo >/dev/null; then echo 'No sudo. Use an existing Docker daemon or have the host administrator run the documented private-daemon procedure.' >&2; exit 1; fi
if ! command -v systemctl >/dev/null || [[ ! -d /run/systemd/system ]]; then
  echo 'Automatic private-daemon bootstrap requires systemd. An existing Docker daemon works without this helper.' >&2
  exit 1
fi
"$TASK_KIT_ROOT/install.sh" checksums
# Validate the dedicated state before the first privileged mutation.
"$TASK_PYTHON" - "$TASK_STATE" <<'PY'
import pathlib,json,os,sys,datetime
p=pathlib.Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True,mode=0o700)
if p.stat().st_uid!=os.getuid():raise SystemExit('State directory belongs to another operator')
marker=p/'agentic-install.json'
if marker.exists():
 if json.loads(marker.read_text()).get('uid')!=os.getuid():raise SystemExit('Installation marker belongs to another operator')
elif any(p.iterdir()):raise SystemExit('Refusing to initialize an unrelated nonempty state directory')
else:
 marker.write_text(json.dumps({'kitVersion':'2026-11-20-r2','created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uid':os.getuid(),'gid':os.getgid()},indent=2)+'\n');marker.chmod(0o600)
p.chmod(0o700)
PY
if [[ -e "/etc/systemd/system/$TASK_SERVICE.service" ]]; then
  echo "Existing private service $TASK_SERVICE detected; starting it without rewriting its configuration."
  sudo -n systemctl start "$TASK_SERVICE.service"
else
  if sudo -n test -e "$TASK_RUNTIME"; then
    echo "An existing runtime directory has no corresponding service: $TASK_RUNTIME. Inspect it before any replacement." >&2
    exit 1
  fi
  TASK_TEMP="$(mktemp -d)"
  trap 'rm -rf -- "$TASK_TEMP"' EXIT
  tar -xzf "$TASK_ARCHIVE" -C "$TASK_TEMP"
  sudo -n install -d -m 0755 "$TASK_RUNTIME"
  sudo -n cp -a "$TASK_TEMP/docker/." "$TASK_RUNTIME/"
  sudo -n chown -R root:root "$TASK_RUNTIME"
  cat > "$TASK_TEMP/service" <<EOF
[Unit]
Description=Private Docker for offline agent operations $TASK_ID
After=network.target

[Service]
Type=notify
Environment=PATH=$TASK_RUNTIME:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RuntimeDirectory=agentic-docker-$TASK_ID
RuntimeDirectoryMode=0755
ExecStart=$TASK_RUNTIME/dockerd --host=unix://$TASK_SOCKET --group=0 --data-root=/var/lib/agentic-docker-$TASK_ID --exec-root=/run/agentic-docker-$TASK_ID/exec --pidfile=/run/agentic-docker-$TASK_ID/docker.pid --storage-driver=overlay2 --iptables=false --ip6tables=false --bridge=none --ip-forward=false --ip-masq=false
ExecStartPost=/bin/chown $TASK_UID:$TASK_GID $TASK_SOCKET
ExecStartPost=/bin/chmod 0600 $TASK_SOCKET
Restart=on-failure
RestartSec=3
TimeoutStartSec=0
TimeoutStopSec=120
Delegate=yes
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
  sudo -n install -m 0644 "$TASK_TEMP/service" "/etc/systemd/system/$TASK_SERVICE.service"
  sudo -n systemctl daemon-reload
  sudo -n systemctl enable --now "$TASK_SERVICE.service"
fi
mkdir -p "$TASK_STATE"
chmod 0700 "$TASK_STATE"
printf '%s\n' "unix://$TASK_SOCKET" > "$TASK_STATE/docker-host.txt"
chmod 0600 "$TASK_STATE/docker-host.txt"
"$TASK_PYTHON" - "$TASK_KIT_ROOT/scripts" "$TASK_PLAN" "$TASK_KIT_ROOT" "$TASK_STATE" "$TASK_RUNTIME" <<'PY'
import json,os,pathlib,sys
sys.path.insert(0,sys.argv[1])
from artifact_policy import ArtifactPolicy
selection=ArtifactPolicy.from_path(sys.argv[3],sys.argv[2]).resolve_file("dockerDaemon")
selection["installedRuntimePath"]=sys.argv[5]
p=pathlib.Path(sys.argv[4])/"docker-bootstrap-source.json"
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,"w") as stream:json.dump(selection,stream,indent=2);stream.write("\n")
os.chmod(p,0o600)
PY
for TASK_TRY in $(seq 1 30); do
  if "$TASK_RUNTIME/docker" --host "unix://$TASK_SOCKET" info >/dev/null 2>&1; then
    echo "Private daemon ready. Run $TASK_KIT_ROOT/install.sh install --config /absolute/private/site.json --state $TASK_STATE"
    exit 0
  fi
  sleep 1
done
echo "Private daemon did not become ready. Inspect: sudo journalctl -u $TASK_SERVICE.service" >&2
exit 1
