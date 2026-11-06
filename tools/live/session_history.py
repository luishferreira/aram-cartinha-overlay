"""Process-scoped state binding, available before the Live Client API is ready."""
import copy
import hashlib
import json


def process_key(game):
    return hashlib.sha256(f"{game['pid']}:{game['process_start']}".encode()).hexdigest()[:24]


def load_history(local, game):
    key = process_key(game)
    path = local / "matches" / f"{key}.json"
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if state.get("match_key") == key else None
    # Preserve a running user's history from the original champion-bound key format.
    previous = local / "state.json"
    if previous.exists():
        state = json.loads(previous.read_text(encoding="utf-8"))
        champion_id = (state.get("champion") or {}).get("champion_id")
        legacy = hashlib.sha256(f"{game['pid']}:{game['process_start']}:{champion_id}".encode()).hexdigest()[:24]
        if champion_id is not None and state.get("match_key") == legacy:
            state = copy.deepcopy(state)
            state["match_key"] = key
            return state
    return None
