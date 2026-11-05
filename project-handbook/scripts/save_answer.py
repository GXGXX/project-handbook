"""Save an answer to a question asked in a handbook page.

    save_answer.py HANDBOOK_DIR --id Q_ID --question-file q.txt --answer-file a.md [--node NODE_ID]

The page copies a question (with its 问题编号) for the user to paste to the
agent. The agent answers and saves it here; the page shows answers.js entries.
Re-saving the same id replaces that answer. Text comes from UTF-8 files so
Chinese, quotes and line breaks survive any shell.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

PREFIX = 'window.HANDBOOK_ANSWERS = '


def read_answers(path):
    """Return the saved list, or [] when there is no file yet."""
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8-sig').strip()
    match = re.fullmatch(r'window\.HANDBOOK_ANSWERS\s*=\s*(\[.*\])\s*;?', text, re.S)
    if not match:
        raise ValueError(f'{path} is not in the expected form "{PREFIX}[...];"; fix or move it, then save again')
    values = json.loads(match[1])
    if not all(isinstance(value, dict) for value in values):
        raise ValueError(f'{path} must hold a list of answer objects')
    return values


def node_ids(book):
    """Node ids in the handbook, from flow.json or flow-data.js, if readable."""
    for name in ('flow.json', 'flow-data.js'):
        path = book / name
        if path.exists():
            text = path.read_text(encoding='utf-8-sig').strip()
            text = re.sub(r'^window\.HANDBOOK_DATA\s*=\s*', '', text).rstrip(';').strip()
            try:
                data = json.loads(text)
            except ValueError:
                return None
            return {node.get('id') for graph in data.get('graphs', []) for node in graph.get('nodes', [])}
    return None


def save(book, entry_id, question, answer, node=None):
    book = Path(book)
    if not book.is_dir() or not (book / 'handbook.html').exists():
        raise ValueError(f'{book} is not a handbook folder (no handbook.html)')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', entry_id):
        raise ValueError('id must be the 问题编号 from the page, such as q-20261105-093321-04hp')
    if not question.strip() or not answer.strip():
        raise ValueError('question and answer must not be empty')
    known = node_ids(book)
    if node and known is not None and node not in known:
        raise ValueError(f'node "{node}" is not in this handbook; leave --node out for a whole-flow answer')
    path = book / 'answers.js'
    values = [value for value in read_answers(path) if value.get('id') != entry_id]
    values.append({'id': entry_id, 'node': node or None, 'question': question.strip(), 'answer': answer.strip(),
                   'time': datetime.now().strftime('%Y-%m-%d %H:%M')})
    text = PREFIX + json.dumps(values, ensure_ascii=False, indent=1).replace('</', '<\\/') + ';\n'
    temporary = path.with_name('answers.js.tmp')
    temporary.write_text(text, encoding='utf-8', newline='\n')
    os.replace(temporary, path)
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('book', type=Path, help='folder that holds handbook.html')
    parser.add_argument('--id', required=True, help='问题编号 copied from the page')
    parser.add_argument('--node', help='node id the question is about (omit for the whole flow)')
    parser.add_argument('--question-file', type=Path, required=True)
    parser.add_argument('--answer-file', type=Path, required=True)
    args = parser.parse_args()
    saved = save(args.book, args.id, args.question_file.read_text(encoding='utf-8-sig'),
                 args.answer_file.read_text(encoding='utf-8-sig'), args.node)
    print(f'saved to {saved}')
