#!/usr/bin/env python3
"""Run fixed coding tasks against explicit native agents; score with separate checks."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def private_json(path, value):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), "Preserving existing report: " + str(path))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def absolute_file(value, label, executable=False):
    require(isinstance(value, str) and value.startswith("/") and ".." not in Path(value).parts,
            label + " must be an absolute normalized file path")
    path = Path(value)
    require(path.is_file(), label + " does not exist")
    require(not executable or os.access(path, os.X_OK), label + " is not executable")
    return path


def git(repo, *args):
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
                            text=True, capture_output=True, check=False)
    require(result.returncode == 0, "Git operation failed: " + " ".join(args[:2]) + ": " + result.stderr.strip()[:400])
    return result.stdout.strip()


def identity(spec):
    """Bind executable and absolute file arguments, including interpreter scripts."""
    files = {}
    for arg in spec["argv"]:
        if arg.startswith("/") and Path(arg).is_file():
            files[arg] = {"resolved": str(Path(arg).resolve()), "sha256": digest(arg)}
    return files


def validate_command(spec, label):
    require(isinstance(spec, dict), label + " must be an object")
    args = spec.get("argv")
    require(isinstance(args, list) and args and all(isinstance(a, str) and "\x00" not in a for a in args),
            label + ".argv must contain literal argv strings")
    absolute_file(args[0], label + ".argv[0]", True)
    timeout = spec.get("timeoutSeconds", 900)
    require(type(timeout) is int and 1 <= timeout <= 86400, label + " has invalid timeout")
    return spec


def load_plan(path):
    path = absolute_file(path, "plan")
    data = json.loads(path.read_text())
    require(data.get("schemaVersion") == 1, "Expected schemaVersion 1")
    require(data.get("isolationAcknowledgment") == "git-worktrees-are-not-an-os-sandbox",
            "Acknowledge the worktree isolation boundary; use the site's task sandbox for stronger isolation")
    require(isinstance(data.get("routingEvidence"), str) and data["routingEvidence"].strip()
            and "REPLACE_" not in data["routingEvidence"], "Record actual internal route qualification without secrets")
    repo = Path(data.get("repository", ""))
    require(repo.is_absolute() and repo.is_dir(), "repository must be an existing absolute Git directory")
    require(git(repo, "rev-parse", "--is-inside-work-tree") == "true", "repository is not a Git working tree")
    agents, tasks = data.get("agents"), data.get("tasks")
    require(isinstance(agents, list) and agents and isinstance(tasks, list) and tasks, "Define agents and tasks")
    for values, label in ((agents, "agents"), (tasks, "tasks")):
        names = set()
        for value in values:
            require(isinstance(value, dict), label + " entries must be objects")
            name = value.get("id", "")
            require(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", name) and name not in names,
                    label + " require unique simple ids")
            names.add(name)
    for a in agents:
        validate_command(a, "agent " + a["id"])
    for t in tasks:
        require(isinstance(t.get("prompt"), str) and t["prompt"].strip(), "Task prompt is required")
        revision = t.get("revision", data.get("revision", ""))
        require(isinstance(revision, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision),
                "Use a fixed full commit hash for each task")
        resolved = git(repo, "rev-parse", "--verify", revision + "^{commit}")
        require(resolved == revision, "Task revision identity mismatch")
        t["resolvedRevision"] = resolved
        require(isinstance(t.get("checks"), list) and t["checks"], "Every task needs independent acceptance commands")
        for i, check in enumerate(t["checks"]):
            validate_command(check, "check " + str(i))
    count = data.get("repetitions", 1)
    require(type(count) is int and 1 <= count <= 20, "repetitions must be 1 through 20")
    data["repository"] = str(repo.resolve())
    data["repetitions"] = count
    return data


def state_dir(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "state must be absolute and normalized")
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink(), "state and its ancestors must not be symlinks")
    if path.exists():
        require(path.is_dir() and path.stat().st_uid == os.getuid(), "State must belong to the operator")
        require((path / "benchmark-state.json").is_file() or not any(path.iterdir()), "Preserving unrelated state")
    else:
        path.mkdir(mode=0o700, parents=True)
    path.chmod(0o700)
    marker = path / "benchmark-state.json"
    require(not marker.is_symlink(), "Refusing state marker symlink")
    if not marker.exists():
        private_json(marker, {"schemaVersion": 1, "uid": os.getuid()})
    marker_data = json.loads(marker.read_text())
    require(marker_data.get("schemaVersion") == 1 and marker_data.get("uid") == os.getuid(),
            "State owner identity mismatch")
    return path


def substitute(args, values):
    output = []
    for arg in args:
        for key, value in values.items():
            arg = arg.replace("{" + key + "}", str(value))
        output.append(arg)
    return output


def execute(spec, values, directory, name):
    argv = substitute(spec["argv"], values)
    before = identity(spec)
    out_path, err_path = directory / (name + ".stdout.log"), directory / (name + ".stderr.log")
    started, start_clock = stamp(), time.monotonic()
    timed_out = False
    with os.fdopen(os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stdout:
        with os.fdopen(os.open(err_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stderr:
            proc = subprocess.Popen(argv, cwd=values["worktree"], env=os.environ.copy(),
                                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                proc.wait(timeout=spec.get("timeoutSeconds", 900))
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            finally:
                # No candidate subprocess may continue mutating the worktree while
                # independent acceptance commands run.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    require(before == identity(spec), "Executable or check input changed during " + name)
    return {"startedAt": started, "finishedAt": stamp(), "durationSeconds": round(time.monotonic() - start_clock, 3),
            "returncode": proc.returncode, "timedOut": timed_out,
            "passed": not timed_out and proc.returncode == 0,
            "stdout": {"path": str(out_path), "sha256": digest(out_path)},
            "stderr": {"path": str(err_path), "sha256": digest(err_path)}, "commandFiles": before}


def run_one(plan, plan_path, agent, task, repeat, root):
    job = root / (agent["id"] + "--" + task["id"] + "--" + str(repeat))
    job.mkdir(mode=0o700)
    workspace = job / "worktree"
    evidence = job / "evidence"
    evidence.mkdir(mode=0o700)
    prompt = job / "prompt.txt"
    fd = os.open(prompt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(fd, "w") as stream:
        stream.write(task["prompt"])
    plan_sha = plan["_planSha256"]
    checks_identity = plan["_checkerIdentities"][task["id"]]
    result = {"schemaVersion": 1, "agent": agent["id"], "task": task["id"], "repeat": repeat,
              "revision": task["resolvedRevision"], "planSha256": plan_sha, "worktree": str(workspace),
              "startedAt": stamp(), "checks": [], "passed": False,
              "isolation": "Git worktree; operating-system isolation must be supplied by the task execution profile"}
    try:
        require(digest(plan_path) == plan_sha, "Benchmark plan changed before the candidate run")
        require(identity(agent) == plan["_agentIdentities"][agent["id"]], "Candidate command input changed")
        require([identity(c) for c in task["checks"]] == checks_identity,
                "Acceptance checker inputs changed before the candidate run")
        git(plan["repository"], "worktree", "add", "--detach", str(workspace), task["resolvedRevision"])
        values = {"worktree": workspace, "prompt_file": prompt, "evidence_dir": evidence}
        result["agentExecution"] = execute(agent, values, evidence, "agent")
        require(digest(plan_path) == plan_sha, "Benchmark plan changed during the candidate run")
        require([identity(c) for c in task["checks"]] == checks_identity,
                "Acceptance checker inputs changed during the candidate run")
        for i, check in enumerate(task["checks"]):
            result["checks"].append(execute(check, values, evidence, "check-" + str(i)))
        require(digest(plan_path) == plan_sha and [identity(c) for c in task["checks"]] == checks_identity,
                "Benchmark acceptance inputs changed")
        diff_path = evidence / "change.diff"
        with os.fdopen(os.open(diff_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            subprocess.run(["git", "-C", str(workspace), "diff", "--binary", task["resolvedRevision"], "--"],
                           stdout=stream, stderr=subprocess.DEVNULL, check=True)
        result["diff"] = {"path": str(diff_path), "sha256": digest(diff_path)}
        result["untrackedFiles"] = git(workspace, "ls-files", "--others", "--exclude-standard").splitlines()
        result["head"] = git(workspace, "rev-parse", "HEAD")
        result["passed"] = result["agentExecution"]["passed"] and all(c["passed"] for c in result["checks"])
    except Exception as exc:
        result["error"] = str(exc)
    result["finishedAt"] = stamp()
    private_json(job / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state")
    args = parser.parse_args()
    plan_path = absolute_file(args.plan, "plan")
    plan = load_plan(str(plan_path))
    plan["_planSha256"] = digest(plan_path)
    plan["_checkerIdentities"] = {t["id"]: [identity(c) for c in t["checks"]] for t in plan["tasks"]}
    plan["_agentIdentities"] = {a["id"]: identity(a) for a in plan["agents"]}
    overview = {"schemaVersion": 1, "agents": [a["id"] for a in plan["agents"]],
                "tasks": [t["id"] for t in plan["tasks"]], "repetitions": plan["repetitions"],
                "runs": len(plan["agents"]) * len(plan["tasks"]) * plan["repetitions"],
                "execution": "sequential to preserve a controlled comparison and bounded inference usage"}
    if args.action == "plan":
        print(json.dumps(overview, indent=2))
        return 0
    require(args.state is not None, "run requires --state")
    state = state_dir(args.state)
    lock_path = state / ".lock"
    require(not lock_path.is_symlink(), "Refusing lock symlink")
    lock = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(lock, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another benchmark is using this state")
        root = state / ("run-" + uuid.uuid4().hex)
        root.mkdir(mode=0o700)
        private_json(root / "input.json", {"planPath": str(plan_path), "sha256": digest(plan_path), "overview": overview})
        results = [run_one(plan, plan_path, agent, task, repeat, root)
                   for repeat in range(1, plan["repetitions"] + 1)
                   for task in plan["tasks"] for agent in plan["agents"]]
        summary = {"schemaVersion": 1, **overview, "state": str(root),
                   "passed": sum(r["passed"] for r in results), "failed": sum(not r["passed"] for r in results),
                   "results": [{k: r[k] for k in ("agent", "task", "repeat", "passed", "worktree")} for r in results],
                   "note": "Candidate worktrees and private evidence retained. Review before explicit Git worktree cleanup."}
        private_json(root / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError) as error:
        print("agentic-bench: " + str(error), file=sys.stderr)
        raise SystemExit(2)
