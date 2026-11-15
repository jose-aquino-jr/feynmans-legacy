"""List an IIS/Apache style archive directory: python pds_ls.py URL [regex]"""

import re
import sys

import requests

url = sys.argv[1]
pat = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
html = requests.get(url, timeout=60, headers={"User-Agent": "lunar-research-pipeline/1.0"}).text
rows = []
# IIS style: "date time   size <A HREF=...>name</A>"
for m in re.finditer(
    r'(\d+/\d+/\d{4}\s+\d+:\d+\s*[AP]M)\s+(&lt;dir&gt;|\d+)\s+<A HREF="([^"]+)">([^<]+)</A>',
    html,
    re.I,
):
    rows.append((m.group(4), m.group(2).replace("&lt;dir&gt;", "<dir>"), m.group(1)))
if not rows:  # apache style
    for m in re.finditer(
        r'<a href="([^"?][^"]*)">([^<]+)</a>\s*</td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>\s*([^<]*)</td>',
        html,
        re.I,
    ):
        rows.append((m.group(2), m.group(4).strip(), m.group(3).strip()))
    if not rows:
        for m in re.finditer(r'<a href="([^"?][^"]*)">([^<]+)</a>\s+(\S+ \S+)\s+(\S+)', html, re.I):
            rows.append((m.group(2), m.group(4), m.group(3)))
for name, size, date in rows:
    if pat and not pat.search(name):
        continue
    if size.isdigit():
        size = f"{int(size) / 1e6:10.2f} MB"
    print(f"{name:60s} {size:>14s}  {date}")
