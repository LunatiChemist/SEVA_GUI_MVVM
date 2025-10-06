from __future__ import annotations
import json, os, csv
from typing import Dict, Iterable, Any
from seva.domain.ports import StoragePort, WellId


class StorageLocal(StoragePort):
    """Local filesystem storage for layouts and user prefs (JSON/CSV)."""

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
                w.writerow([wid, json.dumps(pj, ensure_ascii=False, sort_keys=True)])

    def load_layout(self, name: str) -> Dict:
        path = os.path.join(self.root, f"{name}.csv")
        result: Dict[str, Dict] = {}
        with open(path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                wid = row["well_id"]
                pj = json.loads(row["params_json"]) if row.get("params_json") else {}
                result[wid] = pj
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
