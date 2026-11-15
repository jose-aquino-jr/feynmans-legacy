"""Shared helpers for dataset processors: provenance metadata + IMG reading."""

from __future__ import annotations

import numpy as np
from dataset_registry import by_id
from lunar_common import RAW
from lunar_io import img_meta_from_label, parse_pds3_label

REG = by_id()


def meta(dataset_id, **over):
    d = REG[dataset_id]
    m = dict(
        dataset=dataset_id,
        mission=d["mission"],
        instrument=d["instrument"],
        product=d["product"],
        version=d["version"],
        resolution=d["resolution"],
        observation_date=d["period"],
        time_period=d["temporal_class"],
        quality="",
        uncertainty=d["uncertainty"],
        processing_method="",
        source=(d["urls"][0] if d["urls"] else d["identifier"]),
    )
    m.update(over)
    return m


def read_pds_img(dataset_id, img_name, lbl_name=None, rows=None):
    """Read a local PDS3 IMG with its label; returns (physical array float32 with NaN NoData, meta)."""
    d = RAW / dataset_id
    lbl_name = lbl_name or img_name.rsplit(".", 1)[0] + ".lbl"
    lbl = parse_pds3_label((d / lbl_name).read_text(errors="replace"))
    m = img_meta_from_label(lbl)
    arr = np.memmap(
        d / img_name,
        dtype=m["dtype"],
        mode="r",
        offset=m["header_bytes"],
        shape=(m["lines"], m["samples"]),
    )
    a = np.asarray(arr if rows is None else arr[rows], dtype=np.float32)
    raw = np.asarray(arr if rows is None else arr[rows])
    bad = np.zeros(a.shape, bool)
    if m["missing"] is not None:
        bad |= raw == np.array(m["missing"]).astype(raw.dtype)
    if np.issubdtype(raw.dtype, np.floating):
        bad |= ~np.isfinite(raw) | (raw < -1e30)
    a = a * np.float32(m["scale"]) + np.float32(m["offset"])
    a[bad] = np.nan
    return a, m, lbl


def proj_num(m, key):
    v = m["projection"].get(key, "")
    import re

    mm = re.match(r'^\s*"?\'?([-+0-9.eE]+)', v)
    return float(mm.group(1)) if mm else None
