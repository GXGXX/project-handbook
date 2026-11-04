"""Measure the in-page Q&A source lookup on pinned source code.

    python evals/score_retrieval.py SOURCE_ROOT [CASES]

SOURCE_ROOT is the directory the reader would authorize, for example the
source root printed by fetch_sources.py. CASES defaults to
evals/retrieval/spd.json. A case passes when any excerpt the lookup returns
covers any expected line; the report shows where the first hit ranked.
"""
import json
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'project-handbook/scripts'))
from flow_sources import lookup_sources  # noqa: E402

HEADER = re.compile(r'^root-\d+/(?P<file>[^\n]+?):(?P<start>\d+)$')
LINE = re.compile(r'^(?P<number>\d+): ')


def excerpts(text):
    """Split lookup output into (file, set of line numbers) in returned order."""
    found = []
    for line in text.splitlines():
        header = HEADER.match(line)
        if header:
            found.append((header['file'], set()))
        elif found and (number := LINE.match(line)):
            found[-1][1].add(int(number['number']))
    return found


def run(root, cases):
    rows = []
    for case in cases:
        started = time.monotonic()
        output = lookup_sources([root], case['query'], threading.Event())
        elapsed = time.monotonic() - started
        rank = None
        for index, (name, numbers) in enumerate(excerpts(output), start=1):
            if any(name == want['file'] and numbers & set(range(want['lines'][0], want['lines'][1] + 1))
                   for want in case['expect']):
                rank = index
                break
        rows.append({'id': case['id'], 'rank': rank, 'seconds': round(elapsed, 2),
                     'returned': [name for name, _ in excerpts(output)]})
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1]).resolve()
    data = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else HERE / 'retrieval/spd.json')
                      .read_text(encoding='utf-8'))
    rows = run(root, data['cases'])
    hits = sum(row['rank'] is not None for row in rows)
    for row in rows:
        mark = f"hit@{row['rank']}" if row['rank'] else 'MISS'
        print(f"{row['id']:<18} {mark:<7} {row['seconds']:>5}s  {', '.join(row['returned'][:3])}")
    print(f'\n{hits}/{len(rows)} found; median {sorted(r["seconds"] for r in rows)[len(rows) // 2]}s per lookup')


if __name__ == '__main__':
    main()
