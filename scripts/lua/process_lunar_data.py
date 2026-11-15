"""Run every dataset processor (acquisition by remote sampling happens inside the
processors that need it).  Order matters only for proc_operations (needs LOLA slope
npy and the WAC TiO2 sample) and the illumination model (needs LDEM_16 heights).

usage: python process_lunar_data.py [step ...]
steps: lola illum_model illum_official illum_regional diviner composition remote catalogs geophysics operations
"""

from __future__ import annotations

import sys
import time
import traceback

STEPS = {
    "lola": lambda: __import__("proc_lola").__dict__,
    "illum_model": lambda: __import__("compute_illumination").main(),
    "illum_official": lambda: __import__("proc_illumination").process_official(),
    "illum_regional": lambda: __import__("proc_illumination").process_model(),
    "diviner": lambda: [
        __import__("proc_diviner").__dict__[f]()
        for f in ("process_ra", "process_st", "process_cf", "process_gcp", "process_prp")
    ],
    "composition": lambda: [
        __import__("proc_composition").__dict__[f]()
        for f in ("process_lp_grs", "process_lp_halfdeg", "process_npfe")
    ],
    "remote": lambda: [
        __import__("proc_composition").__dict__[f]()
        for f in ("process_wac_tio2", "process_minirf", "process_kaguya")
    ],
    "catalogs": lambda: [
        __import__("proc_catalogs").__dict__[f]()
        for f in (
            "process_robbins",
            "process_lroc_vectors",
            "process_mare_ages",
            "process_pits",
            "process_ugm",
        )
    ],
    "geophysics": lambda: [
        __import__("proc_geophysics").__dict__[f]()
        for f in ("process_grail", "process_crust", "process_lp_mag", "process_points")
    ],
    "operations": lambda: __import__("proc_operations").main(),
}


def run_lola():
    import proc_lola as p

    return [p.process_ldem16(), p.process_ldsm16(), p.process_ldrm16(), p.process_ldec4()]


STEPS["lola"] = run_lola


if __name__ == "__main__":
    todo = sys.argv[1:] or list(STEPS)
    for s in todo:
        t0 = time.time()
        try:
            print(s, STEPS[s](), f"{time.time() - t0:.0f}s", flush=True)
        except Exception:  # noqa
            print(f"STEP {s} FAILED:\n{traceback.format_exc()}", flush=True)
