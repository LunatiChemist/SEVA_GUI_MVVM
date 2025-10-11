from __future__ import annotations
import json, os, csv
from typing import Dict, Iterable, Any, Tuple
from seva.domain.ports import StoragePort, WellId


class StorageLocal(StoragePort):
    """Local filesystem storage for layouts and user prefs (JSON/CSV)."""

    _FLAG_DEFAULTS: Tuple[str, ...] = (
        "run_cv",
        "run_dc",
        "run_ac",
        "run_eis",
        "run_lsv",
        "run_cdl",
        "eval_cdl",
    )

    def __init__(self, root_dir: str = ".") -> None:
        self.root = root_dir

    # ---- Layouts (CSV with JSON params) ----
    def save_layout(self, name: str, wells: Iterable[WellId], params: Dict) -> None:
        path = os.path.join(self.root, f"{name}.csv")
        wells = list(wells)
        # write header: well_id, params_json
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["well_id", "params_json"])
            # if params contains per-well dict use it; else apply the same param dict to all
            per_well: Dict[str, Dict[str, Any]] = (
                params
                if isinstance(params, dict)
                and all(isinstance(v, dict) for v in params.values())
                else {}
            )
            for wid in wells:
                pj = per_well.get(wid, params if not per_well else {})
                payload = self._prepare_snapshot_for_dump(pj)
                w.writerow([wid, json.dumps(payload, ensure_ascii=False, sort_keys=True)])

    def load_layout(self, name: str) -> Dict:
        path = os.path.join(self.root, f"{name}.csv")
        result: Dict[str, Dict] = {}
        with open(path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                wid = row["well_id"]
                pj = json.loads(row["params_json"]) if row.get("params_json") else {}
                result[wid] = self._hydrate_snapshot(pj)
        return {"well_params_map": result, "selection": sorted(result.keys())}

    # ---- User prefs (JSON) ----
    def save_user_prefs(self, prefs: Dict) -> None:
        path = os.path.join(self.root, "user_prefs.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)

    def load_user_prefs(self) -> Dict:
        path = os.path.join(self.root, "user_prefs.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _is_flag_key(key: Any) -> bool:
        return isinstance(key, str) and (key.startswith("run_") or key == "eval_cdl")

    def _prepare_snapshot_for_dump(self, snapshot: Any) -> Any:
        """Split snapshot into fields/flags for persistence (legacy: flat dict)."""
        if not isinstance(snapshot, dict):
            return snapshot
        fields: Dict[str, Any] = {}
        flags: Dict[str, Any] = {}
        for key, value in snapshot.items():
            (flags if self._is_flag_key(key) else fields)[key] = value
        # store new format only if we actually have fields/flags separation
        payload: Dict[str, Any] = {"fields": fields}
        payload["flags"] = flags
        return payload

    def _hydrate_snapshot(self, payload: Any) -> Dict[str, Any]:
        """Merge persisted payload back into a flat snapshot with default flags."""
        snapshot: Dict[str, Any] = {}
        if isinstance(payload, dict):
            if "fields" in payload or "flags" in payload:
                fields = payload.get("fields")
                if isinstance(fields, dict):
                    snapshot.update(fields)
                flags = payload.get("flags")
                if isinstance(flags, dict):
                    snapshot.update(flags)
            else:
                snapshot.update(payload)
        # ensure all known flags exist (default False/"0")
        for flag in self._FLAG_DEFAULTS:
            if flag not in snapshot:
                snapshot[flag] = "0"
        return snapshot
