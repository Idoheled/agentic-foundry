#!/usr/bin/env python3
"""Evidence-bound Claude -> manual handoff -> OMP upgrade, Python 3.9+ stdlib."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
OMP_GATES = ("profile-rehearsal", "internal-model", "tool-roundtrip", "session-resume",
             "existing-skills-hooks-brain", "canonical-command")
STACK_GATES = ("native-tools", "client-model-tool-loops", "native-skills-hooks",
               "orchestration", "multi-project", "recovery", "canonical-commands")

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def fact(value, label):
    require(isinstance(value, str) and value.strip() and "REPLACE_" not in value,
            label + " needs an actual inspection finding")

def absolute(value, label, exists=False):
    require(isinstance(value, str) and value.startswith("/") and ".." not in Path(value).parts,
            label + " must be an explicit normalized absolute path")
    require("REPLACE_" not in value and "\x00" not in value, label + " contains a placeholder or NUL")
    path = Path(value)
    if exists:
        require(path.is_file(), label + " file is unavailable")
    return path

def safe_parents(path):
    for item in (Path(path), *Path(path).parents):
        require(not item.is_symlink(), "Refusing symlink in private workflow path: " + str(item))

def write(path, value):
    path = Path(path)
    safe_parents(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def binding(path):
    path = absolute(str(path), "bound evidence", True)
    require(not path.is_symlink(), "Evidence file must not be a symlink")
    return {"path": str(path), "sha256": sha(path)}

def check_binding(item):
    require(binding(item["path"]) == item, "Bound input/evidence changed: " + item["path"])

def identity(path):
    path = absolute(str(path), "command", True)
    require(os.access(path, os.X_OK), "Command is not executable: " + str(path))
    info = path.lstat()
    return {"path": str(path), "resolved": str(path.resolve()), "sha256": sha(path),
            "link": os.readlink(path) if path.is_symlink() else None,
            "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}

def default_state():
    return str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) /
               "agentic-stack/upgrade-r4")

@contextlib.contextmanager
def locked(state, create=False):
    state = absolute(str(state), "workflow state")
    safe_parents(state)
    if not state.exists():
        require(create, "Begin the Claude phase first; workflow state does not exist")
        state.mkdir(parents=True, mode=0o700)
    require(state.is_dir() and state.stat().st_uid == os.getuid(), "Workflow state must belong to this operator")
    require(stat.S_IMODE(state.stat().st_mode) & 0o077 == 0, "Workflow state must be private (mode 0700)")
    if create:
        require(not any(state.iterdir()), "Preserving an existing workflow; use status and resume it")
    lock = state / "workflow.lock"
    safe_parents(lock)
    fd = os.open(lock, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield state

def load(state):
    value = read(state / "workflow.json")
    require(value.get("schemaVersion") == 1 and value.get("operatorUid") == os.getuid(),
            "Workflow belongs to a different operator or schema")
    require(Path(value["kitRoot"]).resolve() == ROOT, "Use the same extracted kit directory recorded by begin")
    check_binding(value["plan"])
    check_binding(value["preservationPlan"])
    for item in value.get("kitBindings", []):
        check_binding(item)
    return value

def save(state, value):
    value["updatedAt"] = now()
    write(state / "workflow.json", value)

def boot(script, *args):
    return [str(ROOT / "scripts/python.sh"), str(ROOT / "scripts" / script), *map(str, args)]

def run_private(state, name, argv, cwd=None, timeout=7200, environment=None):
    directory = state / "runs" / (name + "-" + secrets.token_hex(6))
    directory.mkdir(parents=True, mode=0o700)
    log = directory / "output.log"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if environment:
        env.update(environment)
    with log.open("xb") as output:
        os.chmod(log, 0o600)
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            finally:
                # A terminated parent can leave a TERM-ignoring child behind.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            code = 124
            output.write(b"\nWorkflow command exceeded its declared timeout.\n")
    return {"name": name, "at": now(), "exitCode": code, "passed": code == 0, "log": binding(log)}

def preserve(state, value, label):
    check_binding(value["preservationPlan"])
    report = state / "reports" / (label + "-preservation-" + secrets.token_hex(4) + ".json")
    report.parent.mkdir(exist_ok=True, mode=0o700)
    result = run_private(state, label + "-preservation", boot("profile-preservation.py", "verify",
                         "--state", state / "preservation", "--report", report, "--phase", label))
    value["lastPreservation"] = result
    if report.exists():
        value["lastPreservationReport"] = binding(report)
    save(state, value)
    require(result["passed"], "Preservation check failed. Inspect the private report/log; do not reset the baseline")
    return binding(report)

def site_inputs(path, phase, only):
    path = absolute(str(path), "installation site", True)
    site = read(path)
    require(site.get("schemaVersion") == 1, "Unsupported installation schema")
    require(site.get("retireOldTools", False) is False,
            "Defer retirement to phase completion after real model/profile checks")
    inputs = [binding(path)]
    if only in ("all", "host", "profiles"):
        host = site.get("host", {})
        plan = read(absolute(host.get("plan"), "host.plan", True))
        inputs.append(binding(host["plan"]))
        if host.get("catalog"):
            inputs.append(binding(host["catalog"]))
        require(host.get("mode") == "system", "This native-upgrade workflow requires system mode; explicitly adapt it for a user-only host")
        if phase == "omp":
            require(set(plan.get("tools", {})) == {"omp"}, "Phase 1 may install only OMP")
        else:
            require("omp" not in plan.get("tools", {}), "Preserve the running qualified OMP; omit it from the phase-2 host plan")
    if phase == "omp":
        require(only == "host", "Phase 1 is the OMP host upgrade only")
        require(not site.get("modelSmoke", False), "Phase 1 must not launch the core stack")
        for name in ("native", "core", "clients", "profiles"):
            require(not isinstance(site.get(name), dict) or site[name].get("enabled", True) is False,
                    "Phase 1 cannot enable " + name)
    for key in ("native", "profiles"):
        section = site.get(key, {})
        if section.get("enabled", True) and section.get("plan"):
            inputs.append(binding(section["plan"]))
    if site.get("core", {}).get("enabled", True) and site.get("core", {}).get("config"):
        config = site["core"]["config"]
        inputs.append(binding(config))
        artifact = read(config).get("artifactPlan")
        if artifact:
            inputs.append(binding(artifact))
    return site, inputs

def host_args(site, command, receipt):
    host = site["host"]
    return boot("hostctl.py", command, "--catalog", host.get("catalog", ROOT / "config/host-catalog.json"),
                "--payload-root", ROOT, "--plan", host["plan"], "--state", host["state"],
                "--mode", host["mode"], "--receipt", receipt)

def host_record(site, inputs, receipt_path):
    path = absolute(receipt_path, "host receipt", True)
    require(not path.is_symlink() and path.resolve().is_relative_to(Path(site["host"]["state"]).resolve()),
            "Host receipt is outside the selected host state")
    receipt = read(path)
    require(receipt.get("status") == "installed_and_verified" and receipt.get("verification", {}).get("passed") is True,
            "Host installation has blockers or did not verify")
    require(receipt.get("operatorUid") == os.getuid(), "Host receipt belongs to another operator")
    require(receipt.get("mode") == site["host"]["mode"] and
            receipt.get("planSha256") == sha(site["host"]["plan"]) and
            receipt.get("catalogSha256") == sha(site["host"].get("catalog", ROOT / "config/host-catalog.json")) and
            set(receipt["tools"]) == set(read(site["host"]["plan"])["tools"]),
            "Host receipt does not match the exact selected plan, catalog, mode and tools")
    return {"site": site, "inputs": inputs, "receipt": str(path), "tools": sorted(receipt["tools"])}

def verified_host(state, record, label, retire=False):
    for item in record["inputs"]:
        check_binding(item)
    for command in (("verify", "retire", "verify") if retire else ("verify",)):
        result = run_private(state, label + "-" + command, host_args(record["site"], command, record["receipt"]))
        require(result["passed"], "Host " + command + " failed; inspect " + result["log"]["path"])
    return read(record["receipt"])

def host_module():
    spec = importlib.util.spec_from_file_location("upgrade_hostctl", ROOT / "scripts/hostctl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def host_instance(site):
    settings = site["host"]
    return host_module().Host(argparse.Namespace(mode=settings["mode"], prefix=None,
        state=settings["state"], operator_home=str(Path.home()), operator_uid=os.getuid(),
        operator_gid=os.getgid(), package_owners=None,
        catalog=settings.get("catalog", str(ROOT / "config/host-catalog.json")),
        plan=settings["plan"], payload_root=str(ROOT)))

def readonly_host(record):
    for item in record["inputs"]:
        check_binding(item)
    result = host_instance(record["site"]).verify_receipt(read(record["receipt"]))
    require(result["passed"], "Qualified installed runtime tree/entry point changed or no longer works")
    return result

def checked_gate(record, name):
    require(record.get("passed") is True, "Missing or failed executed gate: " + name)
    for key in ("log", "proof", "spec"):
        check_binding(record[key])
    for item in record.get("evidenceFiles", []):
        check_binding(item)

def canonical_bindings(receipt, omp_context=None):
    result = {}
    for name, tool in receipt["tools"].items():
        for command in tool["selection"].get("commands", {}):
            found = shutil.which(command)
            require(found, "Canonical command is missing from this operator's PATH: " + command)
            actions = [item for item in receipt["actions"] if item["tool"] == name and item["command"] == command]
            staged = tool["staged"]
            candidates = [item["path"] for item in actions]
            if staged.get("reuse"):
                candidates.append(staged["executables"][command]["path"])
            require(any(Path(candidate).exists() and os.path.samefile(found, candidate) for candidate in candidates),
                    "Canonical command still resolves to an unqualified/old location: " + command)
            result[command] = identity(found)
    if omp_context:
        require("omp" in result and os.path.samefile(result["omp"]["path"], omp_context["command"]),
                "Recorded OMP launch command does not match the qualified canonical command")
    return result

def stable_omp(value):
    check_binding(value["phase1Receipt"])
    readonly_host(value["phase1Install"]["host"])
    expected = value.get("qualifiedOmp")
    require(expected and identity(expected["path"]) == expected, "Qualified OMP changed; do not continue with another binary/profile")
    found = shutil.which("omp")
    require(found and os.path.samefile(found, expected["path"]), "The new shell's omp command resolves elsewhere; inspect PATH and wrappers")

def begin(state, plan_path):
    require(os.getuid() != 0, "Start as the ordinary operator; use existing sudo only in the native installers")
    plan_path = absolute(str(plan_path), "upgrade plan", True)
    plan = read(plan_path)
    require(plan.get("schemaVersion") == 1, "Upgrade plan schemaVersion must be 1")
    fact(plan.get("evidence"), "upgrade discovery")
    fact(plan.get("profileDiscovery"), "effective profiles/project/brain discovery")
    context = plan.get("ompContext", {})
    absolute(context.get("command"), "future canonical OMP command")
    cwd = absolute(context.get("cwd"), "preserved OMP launch cwd")
    require(cwd.is_dir(), "Preserved OMP working directory is unavailable")
    args = context.get("arguments", [])
    require(isinstance(args, list) and all(isinstance(x, str) and "\x00" not in x for x in args),
            "ompContext.arguments must be an argv array of inspected profile/config flags")
    banned = ("-p", "--print", "--help", "--version", "--approval-mode", "--resume", "--continue",
              "-r", "-c", "--session", "--session-dir", "--mode", "--cwd", "--no-session", "--export", "--restore", "--goal")
    require(not any(x in banned or any(x.startswith(k + "=") for k in banned if k.startswith("--")) for x in args),
            "OMP context must not contain execution, approval, help or resume flags")
    old = plan.get("existingOmp", {})
    old_identity = identity(old.get("command", ""))
    fact(old.get("version"), "existing OMP version")
    fact(plan.get("expectedOmpVersion"), "selected OMP version")
    preservation = absolute(plan.get("preservationPlan"), "preservation plan", True)
    saved_plan = state / "upgrade-plan.json"
    write(saved_plan, plan)
    value = {"schemaVersion": 1, "operatorUid": os.getuid(), "createdAt": now(), "kitRoot": str(ROOT),
             "stage": "phase1", "plan": binding(saved_plan), "sourcePlan": binding(plan_path),
             "preservationPlan": binding(preservation), "ompContext": context,
             "expectedOmpVersion": plan["expectedOmpVersion"], "originalOmp": old_identity,
             "checks": {"omp": {}, "stack": {}}, "phase2Runs": []}
    value["kitBindings"] = [binding(ROOT / "SHA256SUMS"), binding(Path(__file__).resolve())]
    save(state, value)
    result = run_private(state, "baseline-snapshot", boot("profile-preservation.py", "snapshot", "--plan", preservation,
                        "--state", state / "preservation"))
    value["baseline"] = result
    save(state, value)
    require(result["passed"], "Baseline snapshot failed. No host installer was invoked; inspect private log")
    return {"stage": "phase1", "state": str(state), "baseline": result}

def install(state, value, site_path, phase, only):
    require(value["stage"] == ("phase1" if phase == "omp" else "phase2"), "Wrong phase: use the explicit manual Claude-to-OMP handoff")
    if phase == "stack":
        stable_omp(value)
    else:
        checked_gate(value["checks"]["omp"].get("profile-rehearsal", {}), "profile-rehearsal")
    preserve(state, value, "before-" + phase + "-install")
    site, inputs = site_inputs(site_path, phase, only)
    if phase == "omp":
        _, _, selected = host_instance(site).load_inputs()
        selected = selected["omp"]
        if selected.get("reuse"):
            artifact = Path(selected["executables"]["omp"]["path"]).resolve()
        else:
            artifact = Path(selected["artifact"]["path"]).resolve()
        require(binding(artifact) in value["checks"]["omp"]["profile-rehearsal"].get("evidenceFiles", []),
                "Rehearsal proof must bind the exact selected OMP artifact or reused executable")
    record = {"scope": only, "result": {"passed": False, "status": "running-or-interrupted"}, "site": site, "inputs": inputs}
    if phase == "omp":
        value["phase1Install"] = record
        value["checks"]["omp"] = {k: v for k, v in value["checks"]["omp"].items() if k == "profile-rehearsal"}
    else:
        value["phase2Runs"].append(record)
        value["checks"]["stack"] = {}
    save(state, value)
    result_path = state / "reports" / (phase + "-installer-result-" + secrets.token_hex(6) + ".json")
    try:
        result = run_private(state, phase + "-install-" + only,
                             boot("install-stack.py", "apply", "--site", site_path, "--only", only,
                                  "--result-json", result_path))
        record["attemptResult"] = result
        save(state, value)
        require(result["passed"], "Installer failed; inspect its private log and receipts")
        for item in inputs:
            check_binding(item)
        coordinator_result = read(result_path)
        require(coordinator_result.get("passed") is True, "Coordinator result did not pass")
        record["coordinatorResult"] = binding(result_path)
        if only in ("host", "all"):
            record["host"] = host_record(site, inputs, coordinator_result.get("hostReceipt"))
        if phase == "omp":
            receipt = read(record["host"]["receipt"])
            require(receipt["tools"]["omp"]["selection"]["version"] == value["expectedOmpVersion"],
                    "Installed OMP version differs from the inspected upgrade plan")
        elif "host" in record:
            value["phase2Host"] = record["host"]
        record["result"] = result
        save(state, value)
    except Exception as exc:
        record["result"] = {"passed": False, "failure": str(exc)}
        save(state, value)
        raise
    preserve(state, value, "after-" + phase + "-install")
    return {"stage": value["stage"], "installed": result, "hostReceipt": record.get("host", {}).get("receipt")}

def record_check(state, value, phase, name, spec_path):
    require(name in (OMP_GATES if phase == "omp" else STACK_GATES), "Unknown acceptance gate")
    require(value["stage"] == ("phase1" if phase == "omp" else "phase2"), "Acceptance gate belongs to a different phase")
    value["checks"][phase][name] = {"passed": False, "at": now(), "failure": "A new check attempt is pending or was interrupted"}
    save(state, value)
    if phase == "stack":
        stable_omp(value)
    elif name != "profile-rehearsal":
        require(value.get("phase1Install", {}).get("result", {}).get("passed"), "Install OMP before recording runtime acceptance")
    spec_path = absolute(str(spec_path), "check specification", True)
    spec = read(spec_path)
    require(spec.get("schemaVersion") == 1, "Check specification schemaVersion must be 1")
    fact(spec.get("purpose"), "check purpose")
    argv = spec.get("argv")
    require(isinstance(argv, list) and argv and all(isinstance(x, str) and "\x00" not in x for x in argv), "Check argv must be a nonempty string array")
    absolute(argv[0], "check executable", True)
    cwd = absolute(spec.get("cwd"), "check cwd")
    require(cwd.is_dir(), "Check working directory does not exist")
    if phase == "omp" and name not in ("profile-rehearsal", "canonical-command"):
        require(cwd == Path(value["ompContext"]["cwd"]), "Run OMP acceptance from the preserved project working directory")
    timeout = spec.get("timeoutSeconds", 900)
    require(isinstance(timeout, int) and not isinstance(timeout, bool) and 1 <= timeout <= 86400, "Invalid check timeout")
    token = secrets.token_hex(24)
    proof = state / "proofs" / (phase + "-" + name + "-" + secrets.token_hex(6) + ".json")
    proof.parent.mkdir(exist_ok=True, mode=0o700)
    replacements = {"{PROBE_TOKEN}": token, "{PROOF_PATH}": str(proof),
                    "{OMP_COMMAND}": value["ompContext"]["command"], "{OMP_CWD}": value["ompContext"]["cwd"]}
    for before, after in replacements.items():
        argv = [part.replace(before, after) for part in argv]
    spec_identity = binding(spec_path)
    command_identity = identity(argv[0])
    before_report = preserve(state, value, phase + "-" + name + "-before")
    configuration_identity = read(before_report["path"])["configurationIdentity"]
    result = run_private(state, phase + "-" + name, argv, cwd=str(cwd), timeout=timeout,
                         environment={"AGENTIC_UPGRADE_PROBE_TOKEN": token, "AGENTIC_UPGRADE_PROOF_PATH": str(proof),
                                      "AGENTIC_UPGRADE_PHASE": phase, "AGENTIC_UPGRADE_CHECK": name})
    result.update(spec=spec_identity, commandIdentity=command_identity)
    try:
        require(result["passed"], "Acceptance command failed")
        check_binding(spec_identity)
        require(identity(argv[0]) == command_identity, "Acceptance command executable changed during the test")
        require(proof.is_file() and not proof.is_symlink() and proof.stat().st_uid == os.getuid(), "Check did not produce its unique local proof file")
        os.chmod(proof, 0o600)
        facts = read(proof)
        require(facts.get("schemaVersion") == 1 and facts.get("passed") is True and facts.get("runToken") == token,
                "Check proof is unsuccessful, stale, or lacks the supplied run token")
        require(facts.get("phase") == phase and facts.get("check") == name, "Check proof belongs to a different gate")
        observations = facts.get("observations")
        require(isinstance(observations, list) and observations, "Check proof needs observable findings")
        for observation in observations:
            fact(observation, "observed check finding")
        result["proof"] = binding(proof)
        for attachment in facts.get("evidenceFiles", []):
            check_binding(attachment)
        result["evidenceFiles"] = facts.get("evidenceFiles", [])
        after_report = preserve(state, value, phase + "-" + name + "-after")
        require(read(after_report["path"])["configurationIdentity"] == configuration_identity,
                "Protected configuration changed during this check; review it and rerun the check")
        result["configurationIdentity"] = configuration_identity
    except (OSError, ValueError, RuntimeError) as exc:
        result.update(passed=False, failure=str(exc))
    value["checks"][phase][name] = result
    save(state, value)
    require(result["passed"], "Gate failed: " + name + ". Inspect " + result["log"]["path"])
    return {"phase": phase, "check": name, "passed": True, "proof": result["proof"], "log": result["log"]}

def acceptance(value, phase, path):
    gates = OMP_GATES if phase == "omp" else STACK_GATES
    document = read(absolute(str(path), "phase acceptance", True))
    require(document.get("schemaVersion") == 1 and document.get("passed") is True, "Acceptance evidence must pass")
    fact(document.get("summary"), "phase summary")
    fact(document.get("oldToolDisposition"), "old runtime/package/entrypoint disposition")
    require(document.get("realInternalEndpoints") is True, "Fixture-only model checks cannot qualify the target")
    require(document.get("preservedExistingConfiguration") is True, "Confirm effective brains/hooks/skills/routes, beyond file hashes")
    for name in gates:
        record = value["checks"][phase].get(name, {})
        checked_gate(record, name)
        finding = document.get("checks", {}).get(name, {})
        require(finding.get("passed") is True, "Acceptance finding failed: " + name)
        fact(finding.get("evidence"), "acceptance finding " + name)
    return binding(path)

def complete_omp(state, value, evidence):
    require(value["stage"] == "phase1", "Phase 1 has already completed or has not begun")
    selected = value.get("phase1Install", {})
    require(selected.get("result", {}).get("passed") and selected.get("host"), "OMP installation has not passed")
    accepted = acceptance(value, "omp", evidence)
    receipt = verified_host(state, selected["host"], "omp-before-handoff")
    commands = canonical_bindings(receipt, value["ompContext"])
    before_retirement = preserve(state, value, "omp-before-retirement")
    current_identity = read(before_retirement["path"])["configurationIdentity"]
    for name in OMP_GATES:
        if name != "profile-rehearsal":
            require(value["checks"]["omp"][name].get("configurationIdentity") == current_identity,
                    "OMP configuration changed after gate " + name + "; rerun that gate")
    verified_host(state, selected["host"], "omp-retirement", retire=True)
    preserved = preserve(state, value, "omp-handoff")
    require(read(preserved["path"])["configurationIdentity"] == current_identity,
            "Configuration changed during final OMP verification; rerun affected gates")
    value.update(stage="awaiting_omp", qualifiedOmp=commands["omp"], phase1CompletedAt=now(),
                 phase1Acceptance=accepted, phase1Preservation=preserved,
                 phase1Receipt=binding(selected["host"]["receipt"]))
    handoff = state / "OMP_HANDOFF.md"
    text = ("# Phase 1 complete: continue with the qualified OMP\n\n"
            "Claude completed the recorded OMP installation, canonical-command checks, real internal-model/tool/session gates, "
            "and preservation checks. This is scoped acceptance, not a guarantee of every future workload.\n\n"
            "The operator now switches clients manually. Claude must stop here and must not launch phase 2.\n\n"
            "## Continuation\n\n"
            "The launcher restores the recorded project working directory and OMP profile/config arguments. "
            "It preserves inherited credentials and verifies the configured environment.\n\n"
            "- Kit: `" + str(ROOT) + "`\n- Private state: `" + str(state) + "`\n"
            "- Preserved working directory: `" + value["ompContext"]["cwd"] + "`\n"
            "- Qualified OMP command: `" + value["ompContext"]["command"] + "`\n"
            "- Canonical entrypoint SHA256: `" + commands["omp"]["sha256"] + "`\n"
            "- Full runtime tree identity and native files: see the bound phase1Receipt.\n\n"
            "Run `upgrade.sh start-omp --state <the-private-state-above>` from the recorded kit. "
            "Do not paste credentials into this handoff.\n\n"
            "## Authoritative evidence\n\n"
            "Read workflow.json, upgrade-plan.json, phase1Acceptance, phase1Receipt, phase1Preservation and checks.omp "
            "inside the private state. Verify these exact evidence bindings before acting. "
            "Read docs/PHASE2_OMP.md and HANDOFF.md completely.\n\n"
            "Keep the qualified OMP runtime and model/profile context. Omit omp from phase-2 host replacement. "
            "Finish other native tools, Claude, Codex, OpenCode, Paperclip/PostgreSQL services, dependencies, "
            "additive native skills/hooks, actual worker profiles and final acceptance. Preserve existing brains, "
            "hooks, skills, credentials, routes, projects and sessions throughout.\n")
    write(handoff, text)
    value["handoff"] = binding(handoff)
    save(state, value)
    return {"stage": "awaiting_omp", "passed": True, "handoff": str(handoff),
            "message": "Phase 1 complete: OMP upgrade and required onsite checks passed. STOP. The operator now starts OMP manually.",
            "nextArgv": [str(ROOT / "upgrade.sh"), "start-omp", "--state", str(state)]}

def prepare_omp(state, value):
    require(value["stage"] in ("awaiting_omp", "phase2"), "OMP continuation is available only after phase 1 passes")
    for key in ("phase1Acceptance", "phase1Receipt", "handoff"):
        check_binding(value[key])
    for name in OMP_GATES:
        checked_gate(value["checks"]["omp"][name], name)
    stable_omp(value)
    preserve(state, value, "before-omp-continuation")
    value["stage"] = "phase2"
    value.setdefault("phase2StartedAt", now())
    save(state, value)
    context = value["ompContext"]
    prompt = ("Continue the authorized two-phase offline upgrade as the OMP phase. Phase 1 is complete. "
              "Keep the recorded project working directory and current internal model/profile configuration. "
              "The kit is " + str(ROOT) + "; private workflow state is " + str(state) + ". "
              "Read " + str(state / "OMP_HANDOFF.md") + ", " + str(ROOT / "docs/PHASE2_OMP.md") +
              ", and " + str(ROOT / "HANDOFF.md") + " completely. "
              "Finish the remaining stack through the phase-aware workflow, preserving existing configuration. "
              "Do not replace this running qualified OMP. Run complete-stack only after every real acceptance gate passes.")
    return [context["command"], *context.get("arguments", []), "--approval-mode", "yolo", "-p", prompt], context["cwd"]

def complete_stack(state, value, evidence):
    require(value["stage"] == "phase2", "Continue in OMP before completing the stack")
    stable_omp(value)
    accepted = acceptance(value, "stack", evidence)
    host = value.get("phase2Host")
    require(host, "The phase-2 host catalog has not been installed/qualified")
    receipt = verified_host(state, host, "stack-before-completion")
    required_tools = set(read(ROOT / "config/host-catalog.json")["tools"]) - {"omp"}
    require(required_tools <= set(receipt["tools"]), "Phase-2 host receipt omits catalog tools: " + ", ".join(sorted(required_tools - set(receipt["tools"]))))
    commands = canonical_bindings(receipt)
    successful = [r for r in value["phase2Runs"] if r["result"]["passed"]]
    require(any(r["scope"] == "all" and r["site"].get("core", {}).get("enabled", True) and r["site"].get("core", {}).get("config") for r in successful),
            "No successful core installation is recorded")
    profile_runs = [r for r in successful if r["scope"] in ("all", "profiles") and
                    r["site"].get("profiles", {}).get("enabled", True) and r["site"].get("profiles", {}).get("plan")]
    require(profile_runs, "Native profile installation is not recorded")
    require(any({"omp", "claude", "codex"} <= set(read(r["site"]["profiles"]["plan"]).get("clients", {})) for r in profile_runs),
            "Native profile installation must cover all three clients")
    for run in successful:
        for item in run["inputs"]:
            check_binding(item)
        check_binding(run["result"]["log"])
    before_retirement = preserve(state, value, "stack-before-retirement")
    current_identity = read(before_retirement["path"])["configurationIdentity"]
    for name in STACK_GATES:
        require(value["checks"]["stack"][name].get("configurationIdentity") == current_identity,
                "Configuration changed after gate " + name + "; rerun that gate")
    verified_host(state, host, "stack-retirement", retire=True)
    preserved = preserve(state, value, "stack-complete")
    require(read(preserved["path"])["configurationIdentity"] == current_identity,
            "Configuration changed during final stack verification; rerun affected gates")
    stable_omp(value)
    protected = read(preserved["path"])["protectedRoots"]
    completion = {"schemaVersion": 1, "status": "completed", "passed": True, "completedAt": now(),
                  "operatorUid": os.getuid(), "kitRoot": str(ROOT), "workflowState": str(state),
                  "hostReceipts": [binding(value["phase1Install"]["host"]["receipt"]), binding(host["receipt"])],
                  "acceptanceEvidence": accepted, "phase1Acceptance": value["phase1Acceptance"],
                  "preservationReport": preserved, "protectedRoots": protected,
                  "canonicalCommands": dict(commands, omp=value["qualifiedOmp"]), "checks": value["checks"],
                  "cleanup": "Old active paths retired as recorded; exact quarantine purge uses cleanup-retired.py after this acceptance"}
    write(state / "completion.json", completion)
    value.update(stage="completed", completion=binding(state / "completion.json"))
    save(state, value)
    return {"stage": "completed", "passed": True, "completion": str(state / "completion.json"),
            "message": "Both phases and recorded onsite acceptance gates passed. See completion report for scope and evidence."}

def cleanup_old(state, value):
    require(value["stage"] == "completed" and value.get("completion"),
            "Old quarantine files may be deleted only after both phases pass")
    check_binding(value["completion"])
    completion = read(value["completion"]["path"])
    records = [value["phase1Install"]["host"], value["phase2Host"]]
    value["cleanup"] = {"passed": False, "status": "running-or-interrupted", "runs": []}
    save(state, value)
    for index, record in enumerate(records):
        bound = binding(record["receipt"])
        require(bound in completion["hostReceipts"], "Final acceptance does not bind the cleanup receipt")
        result = run_private(state, "final-cleanup-" + str(index), boot("cleanup-retired.py", "apply",
            "--host-receipt", bound["path"], "--host-receipt-sha256", bound["sha256"],
            "--completion", value["completion"]["path"], "--completion-sha256", value["completion"]["sha256"],
            "--host-state", record["site"]["host"]["state"], "--mode", record["site"]["host"]["mode"],
            "--state", state / "final-cleanup"))
        value["cleanup"]["runs"].append(result)
        save(state, value)
        require(result["passed"], "Final acceptance passed but exact retired-file cleanup is blocked; inspect private cleanup evidence and rerun cleanup-old")
    value["cleanup"].update(passed=True, status="completed", completedAt=now())
    save(state, value)
    return value["cleanup"]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("begin", "status", "install-omp", "record-check", "complete-omp",
                                           "start-omp", "install-rest", "complete-stack", "cleanup-old"))
    parser.add_argument("--state", default=default_state())
    parser.add_argument("--plan")
    parser.add_argument("--site")
    parser.add_argument("--phase", choices=("omp", "stack"))
    parser.add_argument("--name")
    parser.add_argument("--spec")
    parser.add_argument("--evidence")
    parser.add_argument("--only", choices=("all", "host", "native", "profiles"), default="all")
    args = parser.parse_args(argv)
    if args.command == "begin":
        require(args.plan, "begin requires --plan")
    launch = None
    with locked(args.state, create=args.command == "begin") as state:
        if args.command == "begin":
            require(args.plan, "begin requires --plan")
            result = begin(state, args.plan)
        else:
            value = load(state)
            if args.command == "status":
                result = {"stage": value["stage"], "state": str(state), "kit": value["kitRoot"],
                          "gates": {phase: {name: record["passed"] for name, record in checks.items()}
                                    for phase, checks in value["checks"].items()},
                          "handoff": value.get("handoff"), "completion": value.get("completion")}
                result["cleanup"] = value.get("cleanup")
            elif args.command in ("install-omp", "install-rest"):
                require(args.site, "Installation requires --site")
                result = install(state, value, args.site, "omp" if args.command == "install-omp" else "stack",
                                 "host" if args.command == "install-omp" else args.only)
            elif args.command == "record-check":
                require(args.phase and args.name and args.spec, "record-check requires --phase, --name and --spec")
                result = record_check(state, value, args.phase, args.name, args.spec)
            elif args.command == "complete-omp":
                require(args.evidence, "complete-omp requires --evidence")
                result = complete_omp(state, value, args.evidence)
            elif args.command == "start-omp":
                launch = prepare_omp(state, value)
                result = {"stage": "phase2", "message": "Starting qualified OMP in its preserved working directory and profile context"}
            elif args.command == "cleanup-old":
                result = {"stage": value["stage"], "cleanup": cleanup_old(state, value)}
            else:
                require(args.evidence, "complete-stack requires --evidence")
                result = complete_stack(state, value, args.evidence)
                result["cleanup"] = cleanup_old(state, value)
    print(json.dumps(result, indent=2), flush=True)
    if launch:
        command, cwd = launch
        os.chdir(cwd)
        os.execvpe(command[0], command, os.environ.copy())
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
