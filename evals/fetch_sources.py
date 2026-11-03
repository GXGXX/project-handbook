"""Download the pinned source projects the eval questions are written against.

    python evals/fetch_sources.py [TARGET_DIR]

Each project is cloned shallowly at the pinned tag into TARGET_DIR/<name>
(default: evals/.sources, ignored by Git) and its commit is checked against
sources.json, so answer keys always describe the same code.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / '.sources'
    target.mkdir(parents=True, exist_ok=True)
    for name, source in json.loads((HERE / 'sources.json').read_text(encoding='utf-8')).items():
        folder = target / name
        if not folder.exists():
            subprocess.run(['git', 'clone', '--depth', '1', '--branch', source['tag'],
                            source['url'], str(folder)], check=True)
        commit = subprocess.run(['git', '-C', str(folder), 'rev-parse', 'HEAD'],
                                check=True, capture_output=True, text=True).stdout.strip()
        if commit != source['commit']:
            sys.exit(f'{name}: expected {source["commit"]}, found {commit}. Delete {folder} and retry.')
        print(f'{name}: {folder} @ {source["tag"]}')
        for root in source['roots']:
            print('  source root:', (folder / root).resolve())


if __name__ == '__main__':
    main()
