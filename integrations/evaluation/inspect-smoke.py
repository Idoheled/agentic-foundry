#!/usr/bin/env python3
"""Offline runtime qualification. No model endpoint is contacted."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket
from unittest.mock import patch

from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import exact
from inspect_ai.solver import generate
from inspect_ai.tool._sandbox_tools_utils.sandbox import _binaries_dir
from inspect_ai.tool._sandbox_tools_utils._digests import lookup_digest
import tiktoken


def forbid_inet(self, *args, **kwargs):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise AssertionError("Offline qualification attempted an IP connection")
    return original_connect(self, *args, **kwargs)


original_connect = socket.socket.connect
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", required=True, help="New absolute output directory for qualification evidence")
args = parser.parse_args()
state = Path(args.state)
if not state.is_absolute() or state.exists() or any(p.is_symlink() for p in (state, *state.parents)):
    parser.error("--state must be a new absolute path without symlink ancestors")
state.mkdir(mode=0o700, parents=True)
result = {"schemaVersion": 1, "inspectVersion": importlib.metadata.version("inspect-ai"),
          "model": "mockllm/offline-fixture", "network": "IPv4/IPv6 socket.connect blocked in this process",
          "sandboxTools": [], "tokenizers": [], "evaluations": []}
with patch.object(socket.socket, "connect", forbid_inet):
    for p in sorted(_binaries_dir().iterdir()):
        if p.is_file():
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            assert sha == lookup_digest(p.name), p.name
            result["sandboxTools"].append({"file": p.name, "sha256": sha, "bytes": p.stat().st_size})
    for name in tiktoken.list_encoding_names():
        encoding = tiktoken.get_encoding(name)
        assert encoding.decode(encoding.encode("offline qualification")) == "offline qualification"
        result["tokenizers"].append(name)
    for output, expected in (("42", 1.0), ("wrong", 0.0)):
        model = get_model("mockllm/offline-fixture", custom_outputs=[ModelOutput.from_content("mockllm/offline-fixture", output)], memoize=False)
        logs = eval(Task(dataset=[Sample(input="Return exactly 42", target="42", id="fixed-fixture")],
                         solver=generate(), scorer=exact(), name="offline-fixture"),
                    model=model, display="none", log_dir=str(state / ("pass" if expected else "fail")),
                    log_format="json", max_samples=1, max_tasks=1, notification=False, checkpoint=False)
        assert len(logs) == 1 and logs[0].status == "success", logs
        scores = logs[0].results.scores
        accuracy = scores[0].metrics["mean"].value
        assert accuracy == expected, (accuracy, expected)
        result["evaluations"].append({"output": output, "expectedAccuracy": expected, "actualAccuracy": accuracy,
                                      "status": logs[0].status})
result["passed"] = True
(state / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
