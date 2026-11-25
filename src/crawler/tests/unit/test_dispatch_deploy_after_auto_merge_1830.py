import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ops"))
import dispatch_deploy_after_auto_merge as mod


def test_poll_aborts_immediately_when_auto_merge_disabled():
    def fake_gh(args):
        return 0, json.dumps({"state": "OPEN", "mergeCommit": None, "autoMergeRequest": None})

    action, sha = mod._poll("1829", fake_gh)
    assert action == "abort"
    assert sha is None
    assert mod.exit_code_for(action) == 0
