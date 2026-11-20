#!/usr/bin/env python3
"""Offline Linux controller. Python standard library only. No public downloads."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from artifact_policy import ArtifactPolicy, digest as file_digest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
VERSION = "2026-11-20-r3"
IMAGES = {"paperclip": "agentic-offline/paperclip:2026.1117.0", "postgres": "agentic-offline/postgres:17-alpine"}
EXPECTED_IMAGE_IDS = {}  # populated from shipped provenance/image-lock.json
OFFLINE = {
    "PAPERCLIP_TELEMETRY_DISABLED": "1", "DO_NOT_TRACK": "1",
    "OPENCODE_DISABLE_AUTOUPDATE": "1", "OPENCODE_DISABLE_MODELS_FETCH": "1",
    "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
    "OPENCODE_DISABLE_PROJECT_CONFIG": "1", "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1", "OPENCODE_DISABLE_FFF": "1",
    "PI_NATIVE_VARIANT": "baseline", "CI": "true", "NPM_CONFIG_OFFLINE": "true"
}

def fail(message):
    raise RuntimeError(message)

def run(argv, capture=False, env=None, check=True, timeout=None, stdin=None):
    return subprocess.run([str(a) for a in argv], text=True, capture_output=capture,
                          env=env, check=check, timeout=timeout, input=stdin)

def atomic_text(path, content, mode=0o600):
    path = pathlib.Path(path)
    if path.is_symlink(): fail("Inspect an existing managed-file symlink before replacement: " + str(path))
    if path.exists() and not path.is_file(): fail("Expected a managed regular file: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".writing-")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w") as stream: stream.write(content)
        os.replace(temporary, path)
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)

def write_json(path, value, mode=0o600):
    atomic_text(path, json.dumps(value, indent=2) + "\n", mode)

def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

def private_text(path, text):
    atomic_text(path, text, 0o600)

def safe_extract(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as t:
        # Runtime archives in this kit have relative symlinks only. Reject traversal.
        for m in t.getmembers():
            dest = (target / m.name).resolve()
            if not dest.is_relative_to(target.resolve()): fail("Archive path escapes destination: " + m.name)
            if m.isdev() or m.isfifo(): fail("Unexpected device in runtime archive")
            if m.issym() or m.islnk():
                link = (dest.parent / m.linkname).resolve() if m.issym() else (target / m.linkname).resolve()
                if not link.is_relative_to(target.resolve()): fail("Archive link escapes destination: " + m.name)
        if hasattr(tarfile, "data_filter"):
            t.extractall(target, filter="data")
        else:
            t.extractall(target)

def slug(value):
    result = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")[:55]
    if not result: fail("Name must contain an ASCII letter or number")
    return result

def checksum_verify():
    manifest = ROOT / "SHA256SUMS"
    if not manifest.exists(): fail("SHA256SUMS is missing; incomplete kit")
    count = 0
    for line in manifest.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT): fail("Invalid checksum manifest path")
        if not path.is_file(): fail("Missing payload: " + relative)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(block)
        if h.hexdigest() != digest: fail("Checksum mismatch: " + relative)
        count += 1
    print("PASS: SHA-256 verified for", count, "files", flush=True)

def default_config():
    return read_json(ROOT / "config/site.example.json")

def state_path(args):
    return pathlib.Path(args.state).expanduser().resolve()

def make_state(args):
    if os.getuid() == 0: fail("Run this controller as the intended ordinary Linux operator account")
    if pathlib.Path(args.state).expanduser().is_symlink(): fail("State root cannot be a symlink")
    state = state_path(args)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink(): fail("State root cannot be a symlink")
    marker = state / "agentic-install.json"
    if marker.is_symlink(): fail("Installation marker cannot be a symlink")
    if not marker.exists() and any(state.iterdir()):
        fail("State directory is not empty and has no kit marker; choose a new --state path")
    if not marker.exists():
        write_json(marker, {"kitVersion": VERSION, "created": dt.datetime.now(dt.timezone.utc).isoformat(), "uid": os.getuid(), "gid": os.getgid()})
    if read_json(marker).get("uid") != os.getuid() or state.stat().st_uid != os.getuid():
        fail("The state directory belongs to a different operator; run as its owner")
    for part in ["tools", "runtime/bin", "runtime/adapters", "runtime/certs", "runtime/playbooks", "home/agentic-config",
                 "home/agentic-config/omp", "home/agentic-config/omp-natives", "workspaces", "postgres", "reports", "backups"]:
        target = state / part
        if target.is_symlink() or not target.resolve().is_relative_to(state):
            fail("Managed state directory is a symlink or resolves outside the state: " + part)
        target.mkdir(parents=True, exist_ok=True)
    return state

def config_for(args):
    p = pathlib.Path(args.config).expanduser().resolve() if args.config else state_path(args) / "site.json"
    return read_json(p, default_config())

def validate_config(c, require_model=False):
    for key in ["paperclipPort", "postgresPort"]:
        v = c.get(key)
        if not isinstance(v, int) or not 1024 <= v <= 65535: fail(key + " must be an integer from 1024 to 65535")
    if c["paperclipPort"] == c["postgresPort"]: fail("The service ports must differ")
    names = [slug(p["name"]) for p in c.get("projects", [])]
    if len(names) != len(set(names)): fail("Project names must produce unique directory names")
    if require_model:
        m = c.get("model", {})
        for key in ["providerId", "baseUrl", "id", "smallModelId", "apiKeyEnv"]:
            if not isinstance(m.get(key), str) or not m[key] or "REPLACE_" in m[key]: fail("Set model." + key + " in private site.json")
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", m["providerId"]): fail("Invalid providerId")
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", m["apiKeyEnv"]): fail("Invalid apiKeyEnv")
        from urllib.parse import urlparse
        u = urlparse(m["baseUrl"])
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password: fail("Use an internal http(s) baseUrl without embedded credentials")
        if "apiKey" in m: fail("Use apiKeyEnv and an environment variable, not a plaintext key in site.json")
        if m.get("api", "openai-completions") not in ("openai-completions", "openai-responses", "anthropic-messages"):
            fail("model.api must be openai-completions, openai-responses or anthropic-messages; verify the actual endpoint protocol onsite")

def policy_for(args):
    path = config_for(args).get("artifactPlan")
    if not path:
        fail("Set site.artifactPlan after inspecting internal repositories. Read docs/PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md")
    return ArtifactPolicy.from_path(ROOT, path)

def installed_selection(args):
    return read_json(state_path(args) / "reports/artifact-selection.json", {})

def selected_images(args):
    entries = installed_selection(args).get("images", {})
    return {name: entries.get(name, {}).get("imageRef", ref) for name, ref in IMAGES.items()}

def selected_host_tool(args, name, default):
    chosen = installed_selection(args).get("files", {}).get(name, {})
    path = chosen.get("executionPath")
    if path:
        target = pathlib.Path(path)
        if not target.is_file() or file_digest(target) != chosen.get("executionSha256"):
            fail("Selected " + name + " executable changed or disappeared; inspect it, update the sourcing plan and configure")
        return target
    return default

def copy_managed_binary(src, dest, state):
    src, dest, state = pathlib.Path(src), pathlib.Path(dest), pathlib.Path(state)
    # The controller owns only its marked state; host paths are provisioned separately.
    if dest.is_symlink() or not dest.resolve().is_relative_to(state.resolve()):
        fail("Refusing to replace a symlink or path outside the managed state: " + str(dest))
    digest = file_digest(src)
    if dest.exists():
        if not dest.is_file(): fail("Expected an executable file: " + str(dest))
        if file_digest(dest) == digest:
            dest.chmod(0o755)
            return
        backup = state / "backups/runtime-replacements" / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4))
        backup.mkdir(parents=True, mode=0o700)
        shutil.copy2(dest, backup / dest.name)
        write_json(backup / "replacement.json", {"destination": str(dest), "beforeSha256": file_digest(dest),
                   "afterSha256": digest, "reason": "Managed runtime differs from the explicitly selected verified artifact",
                   "backup": str(backup / dest.name)})
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=dest.parent, prefix=dest.name + ".installing-")
    os.close(fd)
    try:
        shutil.copy2(src, temporary); os.chmod(temporary, 0o755); os.replace(temporary, dest)
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)

def write_managed_launcher(content, dest, state):
    with tempfile.TemporaryDirectory(dir=state / "runtime", prefix="launcher-install-") as tmp:
        source = pathlib.Path(tmp) / "launcher"
        source.write_text(content)
        copy_managed_binary(source, dest, state)

def prepare_runtime(state, policy):
    selection = policy.resolve()  # Validate every choice before changing managed executables.
    files = selection["files"]
    def copy_binary(src, dest): copy_managed_binary(src, dest, state)
    if files["docker"]["format"] == "executable":
        docker_path = pathlib.Path(files["docker"]["path"])
    else:
        with tempfile.TemporaryDirectory(dir=state / "tools", prefix="docker-install-") as tmp:
            safe_extract(files["docker"]["path"], pathlib.Path(tmp))
            copy_binary(pathlib.Path(tmp) / "docker/docker", state / "tools/docker/docker")
        docker_path = state / "tools/docker/docker"
    # Use existing/internal host executables in place; do not replace package-owned files.
    if files["compose"]["source"] in ("existing", "internal"):
        compose_path = pathlib.Path(files["compose"]["path"])
    else:
        compose_path = state / "tools/docker-compose"
        copy_binary(files["compose"]["path"], compose_path)
    for name, path in [("docker", docker_path), ("compose", compose_path)]:
        if not os.access(path, os.X_OK):
            fail("Selected host executable is not executable: " + name)
        files[name]["executionPath"] = str(path)
        files[name]["executionSha256"] = file_digest(path)
    for name, dest in [("omp", "omp-real"), ("herdr", "herdr")]:
        copy_binary(files[name]["path"], state / "runtime/bin" / dest)
    if files["opencode"]["format"] == "executable":
        copy_binary(files["opencode"]["path"], state / "runtime/bin/opencode")
    else:
        with tempfile.TemporaryDirectory(dir=state / "runtime", prefix="opencode-install-") as tmp:
            safe_extract(files["opencode"]["path"], pathlib.Path(tmp))
            copy_binary(pathlib.Path(tmp) / "opencode", state / "runtime/bin/opencode")
    adapter = state / "runtime/adapters/omp"
    if adapter.is_symlink(): fail("Refusing to replace an adapter symlink")
    if not (adapter / ".offline-kit-complete").exists():
        staged = pathlib.Path(tempfile.mkdtemp(dir=state / "runtime/adapters", prefix="omp-install-"))
        safe_extract(files["ompAdapter"]["path"], staged)
        # Accept either a flat archive or one versioned top directory.
        if not (staged / "package.json").exists():
            children = [p for p in staged.iterdir() if p.is_dir() and (p / "package.json").exists()]
            if len(children) != 1: fail("Unexpected OMP adapter archive layout")
            nested = children[0]
            for p in list(nested.iterdir()): p.rename(staged / p.name)
            nested.rmdir()
        if not (staged / "dist/server/index.js").exists(): fail("Adapter runtime is incomplete")
        (staged / ".offline-kit-complete").write_text("0.7.0-offline.1\n")
        if adapter.exists():
            backup = state / "backups" / ("omp-adapter-before-" + secrets.token_hex(8))
            adapter.rename(backup)
        staged.rename(adapter)
    wrapper = state / "runtime/bin/omp"
    write_managed_launcher('#!/bin/sh\nset -eu\nexport PI_NATIVE_VARIANT=baseline\nexport OMP_OFFLINE_CATALOG=1\nexport PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-/paperclip/agentic-config/omp}"\nexport PI_NATIVES_DIR="${PI_NATIVES_DIR:-/paperclip/agentic-config/omp-natives}"\nif [ -n "${AGENTIC_MODEL_API_KEY_ENV:-}" ]; then\n  TASK_KEY="$(printenv "$AGENTIC_MODEL_API_KEY_ENV" || true)"\n  if [ -z "$TASK_KEY" ]; then echo "Required internal model credential is absent" >&2; exit 2; fi\n  unset TASK_KEY\nfi\nexec "$(dirname "$0")/omp-real" --offline "$@"\n', wrapper, state)
    wrapper.chmod(0o755)
    playbooks = ROOT / "config/playbooks"
    if playbooks.exists():
        target = state / "runtime/playbooks"
        if target.is_symlink() or not target.resolve().is_relative_to(state):
            fail("Refusing a playbook directory outside the managed state")
        target.mkdir(parents=True, exist_ok=True)
        selection["preservedPlaybookOverrides"] = []
        for source in playbooks.iterdir():
            if not source.is_file(): continue
            dest = target / source.name
            if dest.is_symlink(): fail("Inspect the existing playbook symlink before configuration: " + str(dest))
            if not dest.exists():
                shutil.copy2(source, dest)
            elif file_digest(dest) != file_digest(source):
                selection["preservedPlaybookOverrides"].append(str(dest))
    selection["time"] = dt.datetime.now(dt.timezone.utc).isoformat()
    selection["runtimeExecutables"] = {name: file_digest(state / "runtime/bin" / name)
                                      for name in ("omp-real", "herdr", "opencode")}
    write_json(state / "artifact-plan.json", policy.plan)
    write_json(state / "reports/artifact-selection.json", selection)

def docker_environment(args):
    env = os.environ.copy()
    explicit = getattr(args, "docker_host", None)
    private = state_path(args) / "docker-host.txt"
    if explicit: env["DOCKER_HOST"] = explicit
    elif private.exists(): env["DOCKER_HOST"] = private.read_text().strip()
    if env.get("DOCKER_HOST"):
        env.pop("DOCKER_CONTEXT", None)
    else:
        binary = selected_host_tool(args, "docker", state_path(args) / "tools/docker/docker")
        client = str(binary) if binary.exists() else shutil.which("docker")
        if client:
            r = run([client, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture=True, env=env, check=False, timeout=10)
            if r.returncode == 0 and r.stdout.strip(): env["DOCKER_HOST"] = r.stdout.strip()
        env.pop("DOCKER_CONTEXT", None)
    host = env.get("DOCKER_HOST", "")
    if host and not host.startswith("unix://"): fail("This kit manages a local machine. Select a local Unix Docker socket with --docker-host")
    return env

def model_fingerprint(args):
    state = state_path(args)
    value = {"model": config_for(args).get("model"), "images": selected_images(args),
             "artifacts": installed_selection(args),
             "credentials": read_json(state / "model-secret.json", {})}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

def docker(args, *parts, capture=False, check=True, timeout=None, stdin=None):
    binary = selected_host_tool(args, "docker", state_path(args) / "tools/docker/docker")
    if not binary.exists():
        found = shutil.which("docker")
        if not found: fail("Docker unavailable. Run install or scripts/bootstrap-docker.sh first")
        binary = pathlib.Path(found)
    return run([binary, *parts], capture, docker_environment(args), check, timeout, stdin)

def docker_ready(args):
    r = docker(args, "info", "--format", "{{.ServerVersion}}", capture=True, check=False, timeout=15)
    if r.returncode:
        fail("No usable local Docker daemon. Inspect existing/internal runtime options, or use scripts/bootstrap-docker.sh --artifact-plan /absolute/private/artifact-plan.json --state " + str(state_path(args)))
    print("Docker server:", r.stdout.strip())

def compose(args, *parts, capture=False, check=True):
    state = state_path(args)
    binary = selected_host_tool(args, "compose", state / "tools/docker-compose")
    return run([binary, "--project-name", project_name(state), "--file", state / "compose.json", *parts], capture, docker_environment(args), check)

def project_name(state):
    return "agentic-" + hashlib.sha256(str(state).encode()).hexdigest()[:10]

def is_port_free(port):
    with socket.socket() as s:
        try: s.bind(("127.0.0.1", port)); return True
        except OSError: return False

def secrets_for(state):
    path = state / "secrets.json"
    data = read_json(path)
    if data is None:
        data = {key: secrets.token_hex(32) for key in ["postgresPassword", "jwtSecret", "toolActionSecret"]}
        write_json(path, data)
    return data

def write_runtime_config(args, require_model=False):
    state = make_state(args); c = config_for(args); validate_config(c, require_model)
    # A new configuration must be qualified again, even if an older route passed.
    (state / "reports/model-smoke.json").unlink(missing_ok=True)
    write_json(state / "site.json", c)
    s = secrets_for(state)
    env = dict(OFFLINE)
    env.update({
        "HOST": "127.0.0.1", "PORT": str(c["paperclipPort"]), "SERVE_UI": "true", "NODE_ENV": "production",
        "PAPERCLIP_DEPLOYMENT_MODE": "local_trusted", "PAPERCLIP_DEPLOYMENT_EXPOSURE": "private", "PAPERCLIP_BIND": "loopback",
        "PAPERCLIP_PUBLIC_URL": "http://127.0.0.1:" + str(c["paperclipPort"]),
        "PAPERCLIP_HOME": "/paperclip", "HOME": "/paperclip", "PAPERCLIP_CONFIG": "/paperclip/instances/default/config.json",
        "USER_UID": str(os.getuid()), "USER_GID": str(os.getgid()),
        "DATABASE_URL": "postgres://paperclip:" + s["postgresPassword"] + "@127.0.0.1:" + str(c["postgresPort"]) + "/paperclip",
        "PAPERCLIP_AGENT_JWT_SECRET": s["jwtSecret"], "PAPERCLIP_TOOL_ACTION_SIGNING_SECRET": s["toolActionSecret"],
        "PAPERCLIP_ENABLE_COMPANY_DELETION": "false", "PAPERCLIP_DB_BACKUP_ENABLED": "false",
        "PATH": "/opt/agentic/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PI_CODING_AGENT_DIR": "/paperclip/agentic-config/omp", "PI_NATIVES_DIR": "/paperclip/agentic-config/omp-natives",
        "OPENCODE_CONFIG": "/paperclip/agentic-config/opencode.json",
        "XDG_CONFIG_HOME": "/paperclip/agentic-config/xdg", "XDG_DATA_HOME": "/paperclip/agentic-data", "XDG_CACHE_HOME": "/paperclip/agentic-cache"
    })
    m = c.get("model", {})
    if m.get("id") and "REPLACE_" not in m["id"]:
        validate_config(c, True)
        keyname = m["apiKeyEnv"]
        prior = read_json(state / "model-secret.json", {})
        key = os.environ.get(keyname, prior.get(keyname))
        if not key: fail("Export " + keyname + " before configure; for a gateway without authentication set it to a non-secret placeholder")
        if "\n" in key or "\r" in key: fail("API key must not contain newlines")
        write_json(state / "model-secret.json", {keyname: key}); env[keyname] = key
        env["AGENTIC_MODEL_API_KEY_ENV"] = keyname
        model_id = m["providerId"] + "/" + m["id"]
        small = m["providerId"] + "/" + m["smallModelId"]
        models = {mid: {"name": mid, "limit": {"context": m.get("contextWindow", 65536), "output": m.get("maxTokens", 8192)}} for mid in set([m["id"], m["smallModelId"]])}
        sdk = {"openai-completions": "@ai-sdk/openai-compatible", "openai-responses": "@ai-sdk/openai", "anthropic-messages": "@ai-sdk/anthropic"}[m.get("api", "openai-completions")]
        provider = {m["providerId"]: {"npm": sdk, "name": "Internal model gateway", "options": {"baseURL": m["baseUrl"], "apiKey": "{env:" + keyname + "}"}, "models": models}}
        oc = {"model": model_id, "small_model": small, "enabled_providers": [m["providerId"]], "provider": provider,
              "autoupdate": False, "share": "disabled", "plugin": [], "mcp": {}, "lsp": False, "permission": "allow"}
        write_json(state / "home/agentic-config/opencode.json", oc)
        env["PAPERCLIP_OPENCODE_PROVIDERS"] = json.dumps(provider, separators=(",", ":"))
        env["PAPERCLIP_OPENCODE_SMALL_MODEL"] = small
        env["PAPERCLIP_OMP_OFFLINE_MODELS"] = json.dumps([m["providerId"] + "/" + mid for mid in models])
        # JSON is a YAML subset and avoids unsafe interpolation into YAML scalars.
        omp_models = {"providers": {m["providerId"]: {"baseUrl": m["baseUrl"], "api": m.get("api", "openai-completions"), "apiKey": keyname,
            "models": [{"id": mid, "name": mid, "contextWindow": m.get("contextWindow", 65536), "maxTokens": m.get("maxTokens", 8192)} for mid in models]}}}
        write_json(state / "home/agentic-config/omp/models.yml", omp_models)
        roles = ["default", "smol", "slow", "vision", "plan", "commit", "tiny", "memory", "task", "advisor", "widget", "judge"]
        omp_settings = {"modelRoles": {r: small if r in ("smol", "tiny") else model_id for r in roles},
            "retry": {"modelFallback": False, "fallbackChains": {r: [] for r in roles + ["web", "image", "speech", "dictation"]}},
            "telemetry": {"otlpExportEnabled": False}, "startup": {"checkUpdate": False, "setupWizard": False},
            "update": {"auto": False}, "marketplace": {"autoUpdate": "off"}}
        write_json(state / "home/agentic-config/omp/config.yml", omp_settings)
    if c.get("caCertPath"):
        ca = pathlib.Path(c["caCertPath"]).expanduser().resolve()
        if not ca.is_file(): fail("caCertPath must point to the approved internal CA PEM file")
        ca_dest = state / "runtime/certs/internal-ca.pem"
        ca_dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(ca_dest, ca.read_text(), 0o644)
        for key in ("NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "CURL_CA_BUNDLE", "GIT_SSL_CAINFO"):
            env[key] = "/opt/agentic/certs/internal-ca.pem"
    # Docker compose env_file format raw prevents $ expansion in credentials/JSON.
    private_text(state / "runtime.env", "".join(k + "=" + v + "\n" for k, v in sorted(env.items())))
    private_text(state / "postgres.env", "POSTGRES_USER=paperclip\nPOSTGRES_DB=paperclip\nPOSTGRES_PASSWORD=" + s["postgresPassword"] + "\n")
    resources = c.get("resources", {})
    images = selected_images(args)
    common = {"network_mode": "host", "restart": "unless-stopped", "pull_policy": "never", "security_opt": ["no-new-privileges:true"]}
    db = dict(common, image=images["postgres"], env_file=[{"path": str(state / "postgres.env"), "format": "raw"}],
        command=["postgres", "-c", "listen_addresses=127.0.0.1", "-p", str(c["postgresPort"])],
        volumes=[{"type": "bind", "source": str(state / "postgres"), "target": "/var/lib/postgresql/data"}],
        healthcheck={"test": ["CMD", "pg_isready", "-h", "127.0.0.1", "-p", str(c["postgresPort"]), "-U", "paperclip", "-d", "paperclip"], "interval": "3s", "timeout": "5s", "retries": 40},
        mem_limit=resources.get("postgresMemory", "2g"), cpus=resources.get("postgresCpus", 2), pids_limit=256)
    server = dict(common, image=images["paperclip"], env_file=[{"path": str(state / "runtime.env"), "format": "raw"}],
        volumes=[{"type": "bind", "source": str(state / "home"), "target": "/paperclip"},
                 {"type": "bind", "source": str(state / "runtime"), "target": "/opt/agentic", "read_only": True},
                 {"type": "bind", "source": str(state / "workspaces"), "target": "/workspaces"}],
        depends_on={"db": {"condition": "service_healthy"}}, stop_grace_period="90s", pids_limit=2048,
        mem_limit=resources.get("paperclipMemory", "12g"), cpus=resources.get("paperclipCpus", 4))
    write_json(state / "compose.json", {"services": {"db": db, "server": server}})
    print("Configuration saved privately; model values and credentials were not printed.")

def load_images(args):
    lock = read_json(ROOT / "provenance/image-lock.json", {})
    selections = installed_selection(args).get("images", {})
    if not selections: fail("No recorded artifact selection; configure with a private-first artifactPlan")
    images = selected_images(args)
    for name, filename in [("paperclip", "paperclip-2026.1117.0-linux-amd64.tar"), ("postgres", "postgres-17-alpine-linux-amd64.tar")]:
        expected = lock.get(name, {}).get("configDigest")
        current = docker(args, "image", "inspect", "--format", "{{.Id}}", images[name], capture=True, check=False)
        if current.returncode == 0:
            if expected and current.stdout.strip() != expected: fail("Existing selected image has unexpected content: " + name)
            continue
        source = selections[name]["source"]
        if source == "existing":
            fail("Selected existing image is not cached: " + name + ". Inspect the sourcing plan; no silent fallback")
        if source == "internal":
            # Registry hosts were explicitly allowlisted when the sourcing plan was validated.
            print("Importing selected internal image:", name, flush=True)
            docker(args, "pull", "--quiet", "--platform", "linux/amd64", images[name])
        elif source == "kit":
            print("Loading documented kit fallback image:", name, flush=True)
            docker(args, "load", "--input", PAYLOAD / "images" / filename)
        else:
            fail("Invalid recorded image source: " + name)
        actual = docker(args, "image", "inspect", "--format", "{{.Id}}", images[name], capture=True).stdout.strip()
        if expected and actual != expected: fail("Loaded image digest mismatch: " + name)

def api(args, method, path, body=None):
    port = config_for(args)["paperclipPort"]
    req = urllib.request.Request("http://127.0.0.1:" + str(port) + "/api" + path,
        data=None if body is None else json.dumps(body).encode(), method=method, headers={"Content-Type": "application/json"})
    # Avoid sending loopback operations through a corporate HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=30) as response:
            raw = response.read(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        # Error body can contain configuration; never dump it to shared console.
        state = state_path(args); private_text(state / "reports/last-api-error.txt", e.read().decode(errors="replace"))
        fail("API " + method + " " + path + " returned HTTP " + str(e.code) + "; private error report saved")

def start(args):
    state = state_path(args)
    if not (state / "compose.json").exists(): fail("Run install first")
    docker_ready(args)
    existing = compose(args, "ps", "--quiet", capture=True, check=False)
    if not existing.stdout.strip():
        for key in ("paperclipPort", "postgresPort"):
            if not is_port_free(config_for(args)[key]): fail(key + " is already occupied; choose a free port in site.json and configure")
    compose(args, "up", "--detach", "--pull", "never", "--no-build")
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            health = api(args, "GET", "/health")
            own = docker(args, "inspect", "--format", "{{.State.Running}}", container_id(args), capture=True, check=False)
            if health and health.get("status") == "ok" and health.get("deploymentMode") == "local_trusted" and health.get("commit") == "c0f132898d2a2677312d8c72096187b27a3d9a38" and health.get("startupRecovery", {}).get("phase") == "ready" and own.stdout.strip() == "true":
                write_json(state / "reports/last-health.json", health)
                print("Paperclip is responding at http://127.0.0.1:" + str(config_for(args)["paperclipPort"])); return
        except (RuntimeError, urllib.error.URLError, TimeoutError, OSError): pass
        time.sleep(2)
    fail("Paperclip did not become healthy in 240s. Inspect './install.sh logs'; no success has been recorded")

def container_id(args, service="server"):
    cid = compose(args, "ps", "--quiet", service, capture=True).stdout.strip()
    if not cid: fail(service + " container is not running")
    return cid

def exec_worker(args, command, timeout=180, capture=True, extra_env=None, cwd="/workspaces"):
    state = state_path(args); uid = read_json(state / "agentic-install.json")["uid"]
    options = ["exec", "--user", str(uid), "--workdir", cwd]
    for key, value in (extra_env or {}).items(): options += ["--env", key + "=" + value]
    return docker(args, *options, container_id(args), *command, capture=capture, check=False, timeout=timeout)

def model_smoke(args):
    validate_config(config_for(args), True)
    m = config_for(args)["model"]
    model = m["providerId"] + "/" + m["id"]
    prompt = "Respond with exactly INTERNAL_MODEL_OK. Do not use tools or change files."
    made = exec_worker(args, ["mkdir", "-p", "/workspaces/.model-smoke"])
    if made.returncode: fail("Could not create the isolated model smoke directory")
    result = exec_worker(args, ["/opt/agentic/bin/opencode", "run", "--format", "json", "--model", model, prompt],
        extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps({"permission": "deny"})}, cwd="/workspaces/.model-smoke")
    texts = []
    for line in result.stdout.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if event.get("type") == "text" and isinstance(event.get("part"), dict):
            texts.append(event["part"].get("text", ""))
    report = {"time": dt.datetime.now(dt.timezone.utc).isoformat(), "scope": "Actual internal model through bundled OpenCode; no tools, no Paperclip task yet", "exitCode": result.returncode,
        "passed": result.returncode == 0 and "".join(texts).strip() == "INTERNAL_MODEL_OK", "fingerprint": model_fingerprint(args), "stdout": result.stdout, "stderr": result.stderr}
    write_json(state_path(args) / "reports/model-smoke.json", report)
    if not report["passed"]: fail("Internal model smoke failed; inspect private reports/model-smoke.json")
    print("PASS: bundled OpenCode completed an actual request to the configured internal model")

def import_projects(args):
    state = state_path(args)
    for p in config_for(args).get("projects", []):
        name = slug(p["name"]); dest = state / "workspaces" / name
        if dest.exists():
            if not (dest / ".git").exists(): fail("Existing destination is not a Git checkout: " + str(dest))
            continue
        source = p.get("localPath")
        url = p.get("repoUrl")
        from urllib.parse import urlparse
        for key in ("repoUrl", "internalRemoteUrl"):
            if p.get(key):
                parsed = urlparse(p[key])
                if parsed.scheme not in ("http", "https", "ssh") or not parsed.hostname or parsed.password or (parsed.username and parsed.scheme != "ssh"):
                    fail(key + " must be an explicit internal URL without embedded tokens/passwords")
        if bool(source) == bool(url): fail("Each project needs exactly one localPath or internal repoUrl")
        command = ["run", "--rm", "--pull", "never", "--user", str(os.getuid()) + ":" + str(os.getgid()), "--entrypoint", "/usr/bin/git",
                   "--mount", "type=bind,src=" + str(state / "workspaces") + ",dst=/workspaces"]
        if source:
            src = pathlib.Path(source).expanduser().resolve()
            if not src.is_dir() or not (src / ".git").exists(): fail("localPath must be a Git working tree: " + str(src))
            if not (src / ".git").is_dir(): fail("localPath is a linked worktree; use its main checkout or an internal repoUrl")
            command += ["--network", "none", "--mount", "type=bind,src=" + str(src) + ",dst=/source,readonly", selected_images(args)["paperclip"],
                        "-c", "safe.directory=/source", "clone", "--no-local", "/source", "/workspaces/" + name]
        else:
            if not str(url).startswith(("http://", "https://", "ssh://")): fail("Use a credential-free explicit internal repo URL")
            ca = state / "runtime/certs/internal-ca.pem"
            if ca.exists(): command += ["--mount", "type=bind,src=" + str(ca) + ",dst=/internal-ca.pem,readonly", "--env", "GIT_SSL_CAINFO=/internal-ca.pem"]
            if str(url).startswith("ssh://"):
                fail("For authenticated SSH repositories, clone with the existing host credential setup first, then register localPath. The kit does not mount your SSH agent automatically")
            command += ["--network", "host", selected_images(args)["paperclip"], "clone", str(url), "/workspaces/" + name]
        docker(args, *command)
        # A local clone's /source remote does not exist in the long-lived worker.
        if source:
            exec_worker(args, ["git", "-C", "/workspaces/" + name, "remote", "remove", "origin"])
        if p.get("internalRemoteUrl"):
            result = exec_worker(args, ["git", "-C", "/workspaces/" + name, "remote", "add", "origin", p["internalRemoteUrl"]])
            if result.returncode: fail("Could not set project internal remote")
        print("Imported committed Git content into isolated workspace:", name)

def seed(args):
    c = config_for(args); validate_config(c, True); state = state_path(args)
    smoke = read_json(state / "reports/model-smoke.json", {})
    if not smoke.get("passed") or smoke.get("fingerprint") != model_fingerprint(args): fail("Run model-smoke for this exact configuration before seed")
    import_projects(args)
    # Local path installation loads bundled dist and node_modules, with no npm operation.
    installed = api(args, "POST", "/adapters/install", {"packageName": "/opt/agentic/adapters/omp", "isLocalPath": True})
    write_json(state / "reports/omp-adapter-registration.json", installed)
    companies = api(args, "GET", "/companies")
    if not isinstance(companies, list): fail("Unexpected companies response; inspect pinned API docs")
    matches = [x for x in companies if x["name"] == c["company"]]
    if len(matches) > 1: fail("More than one company matches; choose a unique name")
    company = matches[0] if matches else api(args, "POST", "/companies", {"name": c["company"], "description": "Disconnected multi-project agent operations"})
    cid = company["id"]
    if company.get("requireBoardApprovalForNewAgents"): fail("This existing company requires hiring approvals; preserve its policy and complete hires through its approval workflow")
    existing_projects = api(args, "GET", "/companies/" + cid + "/projects")
    for p in c.get("projects", []):
        name = slug(p["name"])
        existing = next((x for x in existing_projects if x["name"] == p["name"]), None)
        if existing:
            workspaces = api(args, "GET", "/projects/" + existing["id"] + "/workspaces")
            if not any(w.get("cwd") == "/workspaces/" + name for w in workspaces):
                fail("Existing project points to another workspace: " + p["name"] + ". Review it; no automatic overwrite was performed")
            continue
        api(args, "POST", "/companies/" + cid + "/projects", {"name": p["name"], "workspace": {"name": name, "sourceType": "local_path", "cwd": "/workspaces/" + name, "isPrimary": True},
            "executionWorkspacePolicy": {"enabled": True, "defaultMode": "isolated_workspace", "sharedWorkspaceConcurrency": "serialize", "workspaceStrategy": {"type": "git_worktree", "worktreeParentDir": "/workspaces/.worktrees/" + name}}})
    agents = api(args, "GET", "/companies/" + cid + "/agents")
    model = c["model"]["providerId"] + "/" + c["model"]["id"]
    registered = []
    for a in c.get("agents", []):
        found = next((x for x in agents if x["name"] == a["name"]), None)
        if found:
            expected_type = "omp_local" if a.get("worker") == "omp" else "opencode_local"
            if found.get("adapterType") != expected_type or found.get("adapterConfig", {}).get("model") != model:
                fail("Existing agent differs from requested configuration: " + a["name"] + ". Review it; no automatic overwrite was performed")
            registered.append(found); continue
        worker = a.get("worker", "opencode")
        if worker not in ("opencode", "omp"): fail("worker must be opencode or omp")
        cfg = {"command": "/opt/agentic/bin/" + worker, "model": model, "cwd": "/workspaces", "timeoutSec": 1800, "graceSec": 30,
               "instructionsFilePath": "/opt/agentic/playbooks/" + slug(a.get("playbook", "implementer")) + ".md"}
        if worker == "opencode": cfg["dangerouslySkipPermissions"] = True
        else: cfg.update({"agentDir": "/paperclip/agentic-config/omp", "profile": None, "approvalMode": "yolo"})
        created = api(args, "POST", "/companies/" + cid + "/agents", {"name": a["name"], "role": a.get("role", "engineer"), "adapterType": "opencode_local" if worker == "opencode" else "omp_local", "runner": "legacy", "adapterConfig": cfg,
            "runtimeConfig": {"heartbeat": {"enabled": False, "intervalSec": 0, "wakeOnDemand": False, "maxConcurrentRuns": 1}}, "permissions": {"canCreateAgents": False}})
        registered.append(created)
    write_json(state / "reports/seed.json", {"companyId": cid, "agents": [{"id": a["id"], "name": a["name"], "lifecycleState": a.get("lifecycleState", "unknown")} for a in registered], "taskWakesEnabledForNewAgents": False, "lifecycleProbesMayRun": True, "qualifiedForProductionTasks": False})
    print("Registered company, projects and agents with task-triggered and periodic wakes disabled. Paperclip may still run lifecycle/hello qualification probes.")

def enable_agent(args):
    if not args.agent_id: fail("enable-agent requires --agent-id UUID after successful acceptance")
    if not args.acceptance_report: fail("enable-agent requires --acceptance-report PATH recording a passed real task/review and resource decision")
    evidence = pathlib.Path(args.acceptance_report).expanduser().resolve()
    if not evidence.is_file() or evidence.stat().st_size == 0: fail("Acceptance report missing")
    a = api(args, "GET", "/agents/" + args.agent_id)
    cfg = a.get("runtimeConfig", {})
    cfg["heartbeat"] = {**cfg.get("heartbeat", {}), "enabled": False, "intervalSec": 0, "wakeOnDemand": True, "maxConcurrentRuns": 1}
    api(args, "PATCH", "/agents/" + args.agent_id, {"runtimeConfig": cfg})
    print("Enabled on-demand execution for one agent; periodic heartbeats remain off.")

def backup(args):
    state = state_path(args); stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = state / "backups" / stamp; out.mkdir(mode=0o700)
    c = config_for(args); dbid = container_id(args, "db")
    # Stop only this kit's server so files and database describe a quiescent state.
    running = bool(compose(args, "ps", "--status", "running", "--quiet", "server", capture=True).stdout.strip())
    if running: compose(args, "stop", "server")
    try:
        with (out / "paperclip.sql").open("wb") as f:
            binary = selected_host_tool(args, "docker", state / "tools/docker/docker")
            if not binary.is_file():
                found = shutil.which("docker")
                if not found: fail("Selected Docker client is unavailable for backup")
                binary = pathlib.Path(found)
            subprocess.run([str(binary), "exec", dbid, "sh", "-c", 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump "$@"', "sh", "-h", "127.0.0.1", "-p", str(c["postgresPort"]), "-U", "paperclip", "-d", "paperclip", "--no-owner", "--no-acl"], stdout=f, env=docker_environment(args), check=True)
        with tarfile.open(out / "state-files.tar.gz", "w:gz") as t:
            for name in ["home", "workspaces", "site.json", "artifact-plan.json", "secrets.json", "model-secret.json", "runtime.env", "postgres.env", "agentic-install.json", "compose.json", "reports"]:
                p = state / name
                if p.exists(): t.add(p, arcname=name)
        write_json(out / "backup.json", {"time": stamp, "kitVersion": VERSION, "containsSecrets": True, "database": "pg_dump", "serverQuiesced": True})
    finally:
        if running: compose(args, "start", "server")
    print("Created private, database-consistent backup:", out)

def verify(args):
    state = state_path(args); results = []
    try: results.append({"check": "Paperclip health", "passed": bool(api(args, "GET", "/health"))})
    except Exception as e: results.append({"check": "Paperclip health", "passed": False, "error": str(e)})
    for binary in ("opencode", "omp-real", "herdr"):
        r = exec_worker(args, ["/opt/agentic/bin/" + binary, "--version"], timeout=60)
        results.append({"check": binary + " version execution", "passed": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()})
    lock = read_json(ROOT / "provenance/image-lock.json", {})
    for name, ref in selected_images(args).items():
        r = docker(args, "image", "inspect", "--format", "{{.Id}}", ref, capture=True, check=False)
        results.append({"check": name + " image ID", "passed": r.returncode == 0 and r.stdout.strip() == lock.get(name, {}).get("configDigest"), "actual": r.stdout.strip()})
    for name, expected in installed_selection(args).get("runtimeExecutables", {}).items():
        path = state / "runtime/bin" / name
        results.append({"check": name + " managed file identity", "passed": path.is_file() and file_digest(path) == expected})
    report = {"time": dt.datetime.now(dt.timezone.utc).isoformat(), "scope": "Health, packaged binary execution, image IDs only. See AIRGAP_ACCEPTANCE.md for target integration acceptance.", "checks": results}
    write_json(state / "reports/controller-verify.json", report)
    for r in results: print(("PASS" if r["passed"] else "FAIL") + ": " + r["check"])
    if not all(r["passed"] for r in results): fail("Some checks failed; private report saved")

def preflight(args):
    if os.getuid() == 0: fail("Run the controller as the intended ordinary Linux operator account. Only the optional private-daemon bootstrap uses sudo")
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"): fail("This kit is built for Linux x86-64 only")
    cpuinfo = pathlib.Path("/proc/cpuinfo")
    if cpuinfo.exists():
        flags = next((line.split(":", 1)[1].split() for line in cpuinfo.read_text().splitlines() if line.startswith("flags")), [])
        missing = sorted(set(["cx16", "lahf_lm", "popcnt", "sse4_1", "sse4_2", "ssse3", "pni"]) - set(flags))
        if missing: fail("OMP baseline needs x86-64-v2; CPU flags missing: " + ", ".join(missing))
    if sys.version_info < (3, 9): fail("Python 3.9+ is required by the controller")
    c = config_for(args); validate_config(c)
    parent = state_path(args)
    while not parent.exists(): parent = parent.parent
    free = shutil.disk_usage(parent).free
    print("Linux x86-64 confirmed; Python", platform.python_version(), "; free disk", round(free / 1024**3, 1), "GiB")
    print("Host prerequisites: Docker-compatible Linux kernel; root/sudo only if no usable daemon; Python3.9+; tar. Model/GPU memory is additional.")
    if free < 35 * 1024**3: fail("At least 35 GiB free on the state filesystem is required; 60 GiB recommended for source builds")
    print("Configured loopback ports:", c["paperclipPort"], "and", c["postgresPort"])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "checksums", "sources", "install", "configure", "start", "stop", "status", "logs", "verify", "model-smoke", "seed", "enable-agent", "backup", "shell"])
    parser.add_argument("--state", default=os.environ.get("AGENTIC_STATE", str(pathlib.Path.home() / ".local/share/agentic-stack")))
    parser.add_argument("--config"); parser.add_argument("--docker-host")
    parser.add_argument("--agent-id"); parser.add_argument("--acceptance-report")
    args = parser.parse_args()
    if args.config and args.command not in ("install", "configure", "preflight", "checksums", "sources"):
        installed = read_json(state_path(args) / "site.json")
        if installed != config_for(args): fail("The supplied site file differs from the installed configuration. Run configure and start first")
    if args.command == "preflight": preflight(args)
    elif args.command == "checksums": checksum_verify()
    elif args.command == "sources":
        selection = policy_for(args).resolve()
        for kind in ("files", "images"):
            for name, entry in selection[kind].items():
                print(name + ": " + entry["source"])
        print("PASS: sourcing decisions and file identities validated; image identity is checked at import")
    elif args.command == "install":
        preflight(args); checksum_verify(); policy = policy_for(args); state = make_state(args)
        prepare_runtime(state, policy); write_runtime_config(args); docker_ready(args)
        compose(args, "config", "--quiet"); load_images(args); start(args)
    elif args.command == "configure":
        policy = policy_for(args); state = make_state(args); prepare_runtime(state, policy); write_runtime_config(args, True)
        docker_ready(args); compose(args, "config", "--quiet"); load_images(args)
        print("Run start to recreate the service with the new configuration; then model-smoke and seed.")
    elif args.command == "start": start(args)
    elif args.command == "stop": compose(args, "stop")
    elif args.command == "status":
        compose(args, "ps"); print("Local UI: http://127.0.0.1:" + str(config_for(args)["paperclipPort"]))
    elif args.command == "logs": compose(args, "logs", "--tail", "100")
    elif args.command == "verify": verify(args)
    elif args.command == "model-smoke": model_smoke(args)
    elif args.command == "seed": seed(args)
    elif args.command == "enable-agent": enable_agent(args)
    elif args.command == "backup": backup(args)
    elif args.command == "shell":
        docker(args, "exec", "--interactive", "--tty", "--user", str(os.getuid()), "--workdir", "/workspaces", container_id(args), "/bin/bash")

if __name__ == "__main__":
    try: main()
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        print("ERROR:", str(exc), file=sys.stderr); sys.exit(1)
