"""Validate revisions and produce static, explicitly selected, redacted exports."""

from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile


# Each object has its own allowlist; nested dictionaries never pass through intact.
_SOURCE = ({'id': 'id', 'locator': str, 'excerpt': str}, {'id', 'locator'})
_POSITION = ({'row': int, 'col': int}, {'row', 'col'})
_NODE_FIELDS = {'id': 'id', 'title': str, 'row': int, 'col': int, 'kind': str,
                'lines': str, 'detail': str, 'source': 'id'}
_NODE = (_NODE_FIELDS, set(_NODE_FIELDS) - {'source'})
_EDGE_FIELDS = {'a': 'id', 'b': 'id', 'label': str, 'route': str}
_EDGE = (_EDGE_FIELDS, {'a', 'b'})
_CONNECTION = (_EDGE_FIELDS, {'a', 'b', 'label'})
_GRAPH = ({'id': 'id', 'title': str, 'source': 'id', 'nodes': [_NODE],
           'edges': [_EDGE], 'position': _POSITION},
          {'id', 'title', 'source', 'nodes', 'edges'})
_EXAMPLE_FIELDS = {'title': str, 'provenance': str, 'input': str, 'trace': [str], 'result': str}
_EXAMPLE = (_EXAMPLE_FIELDS, set(_EXAMPLE_FIELDS))
_FIELDS = {'title': str, 'summary': str, 'common': 'id', 'sources': [_SOURCE],
           'graphs': [_GRAPH], 'connections': [_CONNECTION], 'examples': [_EXAMPLE]}
_MANIFEST = (_FIELDS, {'title', 'sources', 'graphs'})
_PATCH = ({key: _FIELDS[key] for key in ('title', 'summary', 'graphs', 'connections', 'examples')}, set())
_QA_FIELDS = {'id': str, 'node_id': 'optional_id', 'question': str, 'answer': str}
_QA = (_QA_FIELDS, set(_QA_FIELDS))
_INCOMPLETE = {'pending', 'streaming', 'error', 'cancelled', 'canceled'}

_PRIVATE_KEY = re.compile(
    r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|\Z)',
    re.DOTALL)
_CREDENTIAL = re.compile(
    r'''(?ix)(?<![\w-])["']?(?:[a-z0-9]+[_-])*
    (?:(?:api|secret|private)[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|
       client[_-]?secret|session[_-]?(?:id|key)|cookie|password|passwd|pwd|secret|token|
       authorization|credential)["']?(?:\s*[:=]\s*|\s+is\s+)
    (?:(?:bearer|basic)\s+)?(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;<>]+)''')
_BEARER = re.compile(r'\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+', re.IGNORECASE)
_TOKEN = re.compile(
    r'\b(?:sk-[A-Za-z0-9_-]{8,}|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{8,}|'
    r'xox[baprs]-[A-Za-z0-9-]{8,}|AKIA[A-Z0-9]{16}|'
    r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b')
# No network/DNS lookup can reliably decide whether a URL names a private service.
_URL = re.compile(r'''(?i)(?:\b[a-z][a-z0-9+.-]*://|(?<![\w:/])//)[^\s<>"']+''')
_PATH = re.compile(
    r'''(?x)(?<![\w/<])(?:[A-Za-z]:[\\/]|\\\\|~[/\\]|/(?![/\s<>]))[^\r\n<>"'|,;]*''')


def _project(value, schema, strict=False):
    """Copy typed manifest fields, rejecting unknown model patch fields."""
    if isinstance(schema, tuple):
        fields, required = schema
        if not isinstance(value, dict) or not required.issubset(value):
            raise ValueError('Missing or malformed manifest fields')
        if strict and value.keys() - fields.keys():
            raise ValueError('Unknown revision field')
        return {key: _project(value[key], field, strict)
                for key, field in fields.items() if key in value}
    if isinstance(schema, list):
        if not isinstance(value, list):
            raise ValueError('Expected an array of authored values')
        return [_project(item, schema[0], strict) for item in value]
    if schema == 'optional_id' and value is None:
        return None
    if schema in ('id', 'optional_id'):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value):
            raise ValueError('Invalid authored identifier')
    elif type(value) is not schema:
        raise ValueError('Invalid authored field type')
    if isinstance(value, str):
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Authored text must be valid Unicode') from None
    return value


def _selected_qa(entries, node_ids):
    if not isinstance(entries, list):
        raise ValueError('Selected Q&A must be an array')
    selected, seen = [], set()
    for entry in entries:
        qa = _project(entry, _QA)
        status = entry.get('status', 'complete')
        if not isinstance(status, str) or status not in _INCOMPLETE | {'complete'}:
            raise ValueError('Invalid Q&A status')
        if not qa['id'].strip() or qa['id'] in seen:
            raise ValueError('Missing or duplicate Q&A ID')
        seen.add(qa['id'])
        if qa['node_id'] is not None and qa['node_id'] not in node_ids:
            raise ValueError('Q&A must reference an existing node or the whole flow')
        if not qa['question'].strip():
            raise ValueError('Q&A requires a question')
        if status in _INCOMPLETE:
            continue
        if not qa['answer'].strip():
            raise ValueError('Completed Q&A requires an answer')
        selected.append(qa)
    return selected


def _attach_qa(data, entries):
    source_ids = [source['id'] for source in data['sources']]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError('Duplicate source ID')
    for graph in data['graphs']:
        for node in graph['nodes']:
            if 'source' in node and node['source'] not in source_ids:
                raise ValueError('Missing node source')
    node_ids = {node['id'] for graph in data['graphs'] for node in graph['nodes']}
    data['qa'] = _selected_qa(entries, node_ids)
    return data


@lru_cache(maxsize=1)
def _builder():
    # Load only at rendering time, including when imported outside the scripts directory.
    spec = importlib.util.spec_from_file_location(
        '_handbook_export_builder', Path(__file__).with_name('build_flow.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(data):
    try:
        return _builder().render(data)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('Invalid flow manifest') from exc


def _redact_text(text):
    text = _PRIVATE_KEY.sub('[redacted credential]', text)
    text = _CREDENTIAL.sub('[redacted credential]', text)
    text = _BEARER.sub('[redacted credential]', text)
    text = _TOKEN.sub('[redacted credential]', text)
    text = _URL.sub('[redacted URL]', text)
    return _PATH.sub('[redacted path]', text)


def _redact(value):
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def apply_revision(data, patch, selected):
    """Apply a complete-graph patch to a copy; never accept replacement sources."""
    result = _project(data, _MANIFEST)
    result.update(_project(patch, _PATCH, strict=True))
    _attach_qa(result, selected)
    _render(result)
    return result


def share_data(data, entries, redact=True):
    """Return allowlisted static data containing only the supplied completed Q&As.

    A null node_id denotes the whole flow. Saved Q&As without a live status are
    already completed artifacts. Explicit non-complete statuses are omitted.
    Redaction conservatively removes all URLs,
    absolute paths, recognizable credentials, and raw source excerpts; disabling
    it never includes runtime, auth, configuration, sessions, or unknown fields.
    """
    if type(redact) is not bool:
        raise ValueError('redact must be a boolean')
    result = _attach_qa(_project(data, _MANIFEST), entries)
    _render(result)
    if redact:
        for source in result['sources']:
            source.pop('excerpt', None)
        result = _redact(result)
        for source in result['sources']:
            if not source['locator'].strip() or source['locator'].startswith('[redacted'):
                source['locator'] = 'Source ' + source['id']
        # Redaction must not break identifiers, relationships, or Q&A validity.
        result = _attach_qa(_project(result, _MANIFEST), result['qa'])
        _render(result)
    return result


def export_html(data, entries, redact=True):
    """Render a portable page with safely escaped, node-linked Q&A JSON."""
    return _render(share_data(data, entries, redact))


def write_revision(book_dir, data, patch, selected, redact=True, cancel_event=None):
    """Validate and stage a version, then publish it with one directory rename.

    Cancellation raises InterruptedError before publication and removes only this
    call's staging directory. The rename is the commit point: after it succeeds,
    return the published path even if cancellation arrives immediately afterward.
    """
    def check_cancelled():
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError('Revision cancelled before publication')

    check_cancelled()
    revised = apply_revision(data, patch, selected)
    check_cancelled()
    shared = share_data(revised, revised['qa'], redact)
    check_cancelled()
    page = _render(shared)
    check_cancelled()
    payload = json.dumps(shared, ensure_ascii=False, indent=2)
    book = Path(book_dir).resolve(strict=True)
    if not book.is_dir():
        raise ValueError('Book directory does not exist')
    versions = book / 'versions'
    if versions.is_symlink() or versions.resolve().parent != book:
        raise ValueError('Versions must stay within the book directory')
    check_cancelled()
    versions.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.revision-', dir=versions))
    output = versions / staging.name[1:]
    relative = (output.relative_to(book) / 'handbook.html').as_posix()
    try:
        check_cancelled()
        with (staging / 'handbook.html').open('x', encoding='utf-8') as handle:
            handle.write(page)
        check_cancelled()
        with (staging / 'flow.json').open('x', encoding='utf-8') as handle:
            handle.write(payload)
        if output.exists() or output.is_symlink():
            raise FileExistsError('Revision destination already exists')
        check_cancelled()
        staging.rename(output)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return relative
