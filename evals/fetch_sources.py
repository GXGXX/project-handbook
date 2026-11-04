"""Download the pinned source projects the eval questions are written against.

    python evals/fetch_sources.py [TARGET_DIR]

Each project is checked out at its pinned tag or commit into TARGET_DIR/<name>
(default: evals/.sources, ignored by Git) and its commit is checked against
sources.json, so answer keys always describe the same code. Only the folders
the questions use are downloaded (a sparse, blob-filtered clone): about 10 MB
instead of 150 MB for Shattered Pixel Dungeon. Git prints its progress.

For each project it prints the directory to give the skill: the "ask" folder
in sources.json, or the first root.
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
            sparse = ['/' + root.strip('/') + '/' for root in source['roots']]
            if source.get('tag'):
                subprocess.run(['git', 'clone', '--progress', '--depth', '1', '--branch', source['tag'],
                                '--filter=blob:none', '--sparse', source['url'], str(folder)], check=True)
                subprocess.run(['git', '-C', str(folder), 'sparse-checkout', 'set', '--no-cone', *sparse],
                               check=True)
            else:
                # No release tag: fetch exactly the pinned commit.
                git = ['git', '-C', str(folder)]
                folder.mkdir(parents=True)
                subprocess.run(git + ['init', '-q'], check=True)
                subprocess.run(git + ['remote', 'add', 'origin', source['url']], check=True)
                subprocess.run(git + ['sparse-checkout', 'set', '--no-cone', *sparse], check=True)
                subprocess.run(git + ['fetch', '--progress', '--depth', '1', '--filter=blob:none',
                                      'origin', source['commit']], check=True)
                subprocess.run(git + ['checkout', '-q', 'FETCH_HEAD'], check=True)
        commit = subprocess.run(['git', '-C', str(folder), 'rev-parse', 'HEAD'],
                                check=True, capture_output=True, text=True).stdout.strip()
        if commit != source['commit']:
            sys.exit(f'{name}: expected {source["commit"]}, found {commit}. Delete {folder} and retry.')
        print(f'{name}: {folder} @ {source.get("tag") or commit[:10]}')
        print('  give the skill this directory:', (folder / source.get('ask', source['roots'][0])).resolve())


if __name__ == '__main__':
    main()
