import copy
from contextlib import contextmanager
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'project-handbook/scripts/flow_exports.py'
exports = None
if MODULE.exists():
    spec = importlib.util.spec_from_file_location('flow_exports', MODULE)
    exports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exports)


def manifest():
    return {
        'title': 'Synthetic approval flow',
        'summary': 'A public teaching example.',
        'common': 'review',
        'sources': [{'id': 'rules', 'locator': 'Synthetic rules',
                     'excerpt': 'An invented rule, not a private input.'}],
        'graphs': [{
            'id': 'review', 'title': 'Review', 'source': 'rules',
            'position': {'row': 0, 'col': 0},
            'nodes': [
                {'id': 'start', 'title': 'Start', 'row': 0, 'col': 0,
                 'kind': 'process', 'lines': 'Read request', 'detail': 'Check inputs.'},
                {'id': 'finish', 'title': 'Finish', 'row': 1, 'col': 0,
                 'kind': 'terminal', 'lines': 'Return result', 'detail': 'Done.'},
            ],
            'edges': [{'a': 'start', 'b': 'finish', 'label': 'Reviewed', 'route': 'normal'}],
        }],
        'connections': [],
        'examples': [{'title': 'Example', 'provenance': 'Synthetic', 'input': 'One request',
                      'trace': ['Read request', 'Return result'], 'result': 'One result'}],
    }


def completed(identifier='answer-1', **changes):
    entry = {'id': identifier, 'node_id': 'start', 'question': 'What is checked?',
             'answer': 'The request inputs.', 'status': 'complete',
             'created_at': '2026-09-16T00:00:00Z'}
    entry.update(changes)
    return entry


class PageData(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.in_data = False
        self.payload = ''
        self.injected = False
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('id') == 'data':
            self.in_data = True
        if 'onerror' in attrs or attrs.get('id') == 'injected':
            self.injected = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.payload += data


class FlowExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(exports, 'The flow export contract is not implemented yet')
        self.data = manifest()

    def test_revision_copies_inputs_and_preserves_original_sources(self):
        selected = [completed()]
        patch = {'title': 'Revised', 'summary': 'A clearer explanation.'}
        before = copy.deepcopy((self.data, patch, selected))
        revised = exports.apply_revision(self.data, patch, selected)
        self.assertEqual((self.data, patch, selected), before)
        self.assertEqual(revised['title'], 'Revised')
        self.assertEqual(revised['sources'], before[0]['sources'])
        self.assertEqual(revised['qa'], [{'id': 'answer-1', 'node_id': 'start',
                                         'question': 'What is checked?', 'answer': 'The request inputs.'}])
        revised['sources'][0]['locator'] = 'Changed copy'
        revised['graphs'][0]['nodes'][0]['detail'] = 'Changed copy'
        revised['qa'][0]['answer'] = 'Changed copy'
        self.assertEqual((self.data, patch, selected), before)

    def test_graph_patch_is_a_complete_replacement(self):
        graphs = copy.deepcopy(self.data['graphs'])
        graphs[0]['nodes'].append({'id': 'archive', 'title': 'Archive', 'row': 2, 'col': 0,
                                  'kind': 'terminal', 'lines': 'Store', 'detail': 'Synthetic storage.'})
        graphs[0]['edges'].append({'a': 'finish', 'b': 'archive', 'label': 'Then'})
        revised = exports.apply_revision(self.data, {'graphs': graphs}, [completed()])
        self.assertEqual(revised['graphs'], graphs)
        graphs[0]['nodes'][0]['title'] = 'Not the output'
        self.assertEqual(revised['graphs'][0]['nodes'][0]['title'], 'Start')

    def test_patch_rejects_unknown_keys_at_every_depth(self):
        patches = [{'runtime': {}}, {'sources': []}, {'qa': []}, {'auth': 'secret'},
                   {'common': 'other'}, {'graphs': [{'id': 'review'}]}]
        for location in ('graph', 'node', 'edge', 'position', 'example'):
            patch = {'graphs': copy.deepcopy(self.data['graphs']),
                     'examples': copy.deepcopy(self.data['examples'])}
            target = {'graph': patch['graphs'][0], 'node': patch['graphs'][0]['nodes'][0],
                      'edge': patch['graphs'][0]['edges'][0],
                      'position': patch['graphs'][0]['position'],
                      'example': patch['examples'][0]}[location]
            target['sessions'] = 'INJECTED-STATE'
            patches.append(patch)
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                exports.apply_revision(self.data, patch, [completed()])

    def test_patch_rejects_graph_semantics_and_canvas_overlap(self):
        changes = [lambda d: d['graphs'][0]['edges'][0].update(b='missing'),
                   lambda d: d['graphs'][0].update(source='missing'),
                   lambda d: d['graphs'][0]['nodes'][1].update(row=0),
                   lambda d: d['graphs'][0]['nodes'][0].update(id='data'),
                   lambda d: d['graphs'][0]['nodes'][0].update(kind='decision'),
                   lambda d: d['graphs'][0].update(edges=[]),
                   lambda d: d.update(graphs=[]),
                   lambda d: d.update(connections=[{'a': 'start', 'b': 'missing', 'label': 'Then'}])]
        for change in changes:
            patch = {'graphs': copy.deepcopy(self.data['graphs'])}
            change(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                exports.apply_revision(self.data, patch, [])
        other = copy.deepcopy(self.data['graphs'][0])
        other.update(id='second', nodes=[{'id': 'other', 'title': 'Other', 'row': 0,
                                        'col': 0, 'kind': 'terminal', 'lines': '', 'detail': ''}], edges=[])
        with self.assertRaises(ValueError):
            exports.apply_revision(self.data, {'graphs': self.data['graphs'] + [other]}, [])

    def test_share_uses_recursive_allowlists_not_a_blacklist(self):
        data = self.data
        data.update(runtime={'token': 'LIVE-TOKEN'}, config={'key': 'CONFIG-LEAK'},
                    sessions=['SESSION-LEAK'], canvas={'nodes': [{'detail': 'CANVAS-LEAK'}]},
                    unknown={'value': 'ROOT-LEAK'}, auth='AUTH-LEAK')
        for index, target in enumerate([data['graphs'][0], data['graphs'][0]['nodes'][0],
                                        data['graphs'][0]['edges'][0], data['graphs'][0]['position'],
                                        data['sources'][0], data['examples'][0]]):
            target['unexpected'] = 'NESTED-LEAK-' + str(index)
        data['graphs'][0]['nodes'][0]['source'] = 'rules'
        entry = completed(unknown='QA-LEAK', runtime={'token': 'QA-TOKEN'})
        before = copy.deepcopy((data, entry))
        shared = exports.share_data(data, [entry], redact=False)
        payload = json.dumps(shared)
        for marker in ('LIVE-TOKEN', 'CONFIG-LEAK', 'SESSION-LEAK', 'CANVAS-LEAK', 'ROOT-LEAK',
                       'AUTH-LEAK', 'NESTED-LEAK-', 'QA-LEAK', 'QA-TOKEN', 'created_at'):
            self.assertNotIn(marker, payload)
        self.assertEqual(shared['graphs'][0]['nodes'][0]['source'], 'rules')
        self.assertEqual((data, entry), before)

    def test_default_redaction_removes_excerpts_but_retains_labeled_source_ids(self):
        self.data['sources'][0].update(locator=r'C:\SyntheticPrivate\rules.py:12',
                                       excerpt='RAW-EXCERPT-MUST-NOT-TRAVEL')
        shared = exports.share_data(self.data, [])
        source = shared['sources'][0]
        self.assertEqual(source['id'], 'rules')
        self.assertTrue(source['locator'].strip())
        self.assertNotIn('SyntheticPrivate', json.dumps(shared))
        self.assertNotIn('RAW-EXCERPT-MUST-NOT-TRAVEL', json.dumps(shared))
        self.assertNotIn('excerpt', source)
        self.assertEqual(shared['graphs'][0]['source'], source['id'])

    def test_secret_and_path_redaction_covers_all_authored_text(self):
        sensitive = [r'C:\SyntheticPrivate\source.py', 'D:/SyntheticPrivate/source.py',
                     '/home/synthetic/private/source.py', r'\\synthetic-host\private\source.py',
                     'file:///home/synthetic/private/source.py',
                     'https://127.0.0.1/private', 'https://internal.synthetic.local/private',
                     'https://reader:synthetic-password@example.com/private',
                     'https://example.com/?token=synthetic-query-secret',
                     'API_KEY=synthetic-api-secret', '"password": "synthetic pass phrase"',
                     'Authorization: Bearer synthetic-bearer-secret',
                     'X-Flow-Token: synthetic-live-secret',
                     'sk-proj-SYNTHETICNOTAREALKEY123456789',
                     '-----BEGIN PRIVATE KEY-----\nSYNTHETICKEYDATA\n-----END PRIVATE KEY-----']
        for value in sensitive:
            with self.subTest(value=value):
                self.data['summary'] = value
                self.data['graphs'][0]['nodes'][0]['detail'] = value
                self.data['graphs'][0]['edges'][0]['label'] = value
                self.data['examples'][0]['trace'] = [value]
                shared = exports.share_data(self.data, [completed(question=value, answer=value)])
                texts = [shared['summary'], shared['graphs'][0]['nodes'][0]['detail'],
                         shared['graphs'][0]['edges'][0]['label'], shared['examples'][0]['trace'][0],
                         shared['qa'][0]['question'], shared['qa'][0]['answer']]
                for text in texts:
                    self.assertNotEqual(text, value)
                    self.assertNotIn('synthetic-api-secret', text)
                    self.assertNotIn('synthetic pass phrase', text)
                    self.assertNotIn('synthetic-bearer-secret', text)
                    self.assertNotIn('synthetic-live-secret', text)
                    self.assertNotIn('SYNTHETICKEYDATA', text)

    def test_redaction_opt_out_keeps_authored_evidence_but_not_runtime(self):
        self.data['summary'] = r'C:\SyntheticPrivate\source.py API_KEY=synthetic-secret'
        self.data['runtime'] = {'token': 'never-share-runtime'}
        shared = exports.share_data(self.data, [], redact=False)
        self.assertEqual(shared['summary'], self.data['summary'])
        self.assertEqual(shared['sources'], self.data['sources'])
        self.assertNotIn('runtime', shared)

    def test_redacts_protocol_relative_urls_and_labeled_paths(self):
        for value in ('//synthetic.internal/private', r'Source:C:\SyntheticPrivate\source.py',
                      'Source:/home/SyntheticPrivate/source.py'):
            with self.subTest(value=value):
                self.data['summary'] = value
                shared = exports.share_data(self.data, [])
                self.assertNotIn('synthetic.internal', shared['summary'])
                self.assertNotIn('SyntheticPrivate', shared['summary'])

    def test_redacts_credential_phrases_and_additional_key_formats(self):
        for value in ('password is synthetic-secret-value', 'secret_key=synthetic-secret-value',
                      'privateKey: synthetic-secret-value', 'session_id=synthetic-secret-value',
                      'Cookie: synthetic-secret-value'):
            with self.subTest(value=value):
                self.data['summary'] = value
                shared = exports.share_data(self.data, [])
                self.assertNotIn('synthetic-secret-value', shared['summary'])

    def test_redaction_does_not_erase_formulas_or_relative_source_labels(self):
        self.data['summary'] = 'Formula: amount / count. Fraction 1/2. product/module.py:10'
        shared = exports.share_data(self.data, [])
        self.assertEqual(shared['summary'], self.data['summary'])
        self.assertEqual(shared['sources'][0]['locator'], 'Synthetic rules')

    def test_share_output_is_independent_and_redact_requires_a_boolean(self):
        entry = completed()
        original = copy.deepcopy((self.data, entry))
        shared = exports.share_data(self.data, [entry])
        shared['graphs'][0]['nodes'][0]['detail'] = 'Changed'
        shared['examples'][0]['trace'].append('Changed')
        shared['qa'][0]['answer'] = 'Changed'
        self.assertEqual((self.data, entry), original)
        for value in ('false', None, 0, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exports.share_data(self.data, [], redact=value)

    def test_only_selected_completed_entries_are_exported(self):
        self.data['qa'] = [completed('unselected', answer='UNSELECTED-DRAFT')]
        entries = [completed(), completed('pending', status='pending', answer='PENDING-DRAFT'),
                   completed('cancelled', status='cancelled', answer='CANCELLED-DRAFT'),
                   completed('failed', status='error', answer='FAILED-DRAFT')]
        shared = exports.share_data(self.data, entries)
        self.assertEqual([q['id'] for q in shared['qa']], ['answer-1'])
        self.assertNotIn('DRAFT', json.dumps(shared))
        self.assertEqual(exports.share_data(self.data, [])['qa'], [])
        self.assertEqual(exports.apply_revision(self.data, {}, entries)['qa'], shared['qa'])

    def test_saved_qa_is_a_valid_input_for_another_export(self):
        saved = {'id': 'saved-1', 'node_id': 'start', 'question': 'Saved?', 'answer': 'Yes.'}
        self.assertEqual(exports.share_data(self.data, [saved])['qa'], [saved])

    def test_full_flow_qa_preserves_null_node_in_every_export(self):
        entry = completed(node_id=None, question='What does this flow do?')
        before = copy.deepcopy((self.data, entry))
        shared = exports.share_data(self.data, [entry])
        revised = exports.apply_revision(self.data, {}, [entry])
        self.assertIsNone(shared['qa'][0]['node_id'])
        self.assertIsNone(revised['qa'][0]['node_id'])
        self.assertEqual(exports.share_data(shared, shared['qa'])['qa'], shared['qa'])
        page = exports.export_html(self.data, [entry])
        self.assertIsNone(json.loads(PageData(page).payload)['qa'][0]['node_id'])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / exports.write_revision(temp, self.data, {}, [entry])
            saved = json.loads(path.with_name('flow.json').read_text(encoding='utf-8'))
            self.assertIsNone(saved['qa'][0]['node_id'])
        self.assertEqual((self.data, entry), before)

    def test_malformed_qa_and_unknown_node_rejected(self):
        bad = [None, 'text', {}, completed(node_id='missing'), completed(id=''),
               completed(id=1), completed(question=[]), completed(question=' '),
               completed(answer={'runtime': 'payload'}), completed(answer=''),
               completed(status='invented'), completed(node_id=''), completed(answer='\ud800')]
        missing_node = completed()
        missing_node.pop('node_id')
        bad.append(missing_node)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                exports.share_data(self.data, [value])
        for entries in (None, {}, 'answers', [completed(), completed()]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                exports.share_data(self.data, entries)

    def test_patch_cannot_orphan_a_selected_qa(self):
        graphs = copy.deepcopy(self.data['graphs'])
        graphs[0]['nodes'][0]['id'] = 'replacement'
        graphs[0]['edges'][0]['a'] = 'replacement'
        with self.assertRaises(ValueError):
            exports.apply_revision(self.data, {'graphs': graphs}, [completed()])

    def test_wrong_manifest_field_types_rejected_not_stringified(self):
        changes = [lambda d: d.update(title={'auth': 'secret'}),
                   lambda d: d.update(summary=[]), lambda d: d.update(graphs={}),
                   lambda d: d['graphs'][0]['nodes'][0].update(col=True),
                   lambda d: d['graphs'][0]['edges'][0].update(label={'config': 'secret'}),
                   lambda d: d['examples'][0].update(trace=[{'sessions': 'secret'}]),
                   lambda d: d['sources'][0].update(locator={'runtime': 'secret'}),
                   lambda d: d.update(sources=[d['sources'][0], d['sources'][0]]),
                   lambda d: d['sources'][0].update(id='../outside'),
                   lambda d: d['graphs'][0]['nodes'][0].update(source='unknown')]
        for change in changes:
            data = copy.deepcopy(self.data)
            change(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                exports.share_data(data, [])
        for patch in (None, [], {'title': None}, {'examples': 'bad'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                exports.apply_revision(self.data, patch, [])

    def test_html_safely_embeds_malicious_text_and_node_linked_qa(self):
        attack = '</script><script id="injected">alert(1)</script><img src=x onerror=alert(2)>'
        self.data['title'] = attack
        self.data['sources'][0]['excerpt'] = attack
        self.data['examples'][0]['trace'] = [attack]
        entry = completed(question=attack, answer=attack)
        before = copy.deepcopy((self.data, entry))
        page = exports.export_html(self.data, [entry], redact=False)
        parsed = PageData(page)
        self.assertFalse(parsed.injected)
        payload = json.loads(parsed.payload)
        self.assertEqual(payload['qa'][0]['answer'], attack)
        self.assertEqual(payload['qa'][0]['node_id'], 'start')
        self.assertIn('start', [n['id'] for n in payload['canvas']['nodes']])
        self.assertEqual((self.data, entry), before)

    def test_version_writes_unique_static_files_and_preserves_original(self):
        self.data['runtime'] = {'token': 'LIVE-RUNTIME-TOKEN'}
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp) / 'book'
            book.mkdir()
            original_html = book / 'handbook.html'
            original_json = book / 'flow.json'
            original_html.write_text('ORIGINAL HTML', encoding='utf-8')
            original_json.write_text('ORIGINAL JSON', encoding='utf-8')
            first = exports.write_revision(book, self.data, {'title': 'First'}, [completed()])
            first_content = (book / first).read_bytes()
            second = exports.write_revision(book, self.data, {'title': 'Second'}, [completed()])
            self.assertNotEqual(first, second)
            for relative, title in ((first, 'First'), (second, 'Second')):
                self.assertIsInstance(relative, str)
                self.assertFalse(Path(relative).is_absolute())
                self.assertEqual(Path(relative).parts[0], 'versions')
                self.assertEqual(Path(relative).name, 'handbook.html')
                self.assertEqual(len(Path(relative).parts), 3)
                self.assertNotIn('\\', relative)
                output = book / relative
                data = json.loads(output.with_name('flow.json').read_text(encoding='utf-8'))
                page = output.read_text(encoding='utf-8')
                self.assertEqual(data['title'], title)
                self.assertNotIn('LIVE-RUNTIME-TOKEN', page)
                self.assertNotIn('runtime', data)
                self.assertNotIn('excerpt', data['sources'][0])
                self.assertEqual(json.loads(PageData(page).payload)['qa'], data['qa'])
            self.assertEqual((book / first).read_bytes(), first_content)
            self.assertEqual(original_html.read_text(encoding='utf-8'), 'ORIGINAL HTML')
            self.assertEqual(original_json.read_text(encoding='utf-8'), 'ORIGINAL JSON')

    def test_invalid_revision_is_atomic_even_before_versions_directory_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp)
            (book / 'handbook.html').write_text('ORIGINAL', encoding='utf-8')
            for patch, selected in (({'graphs': []}, []), ({'sources': []}, []),
                                    ({'title': '\ud800'}, []),
                                    ({}, [completed(node_id='missing')])):
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    exports.write_revision(book, self.data, patch, selected)
                self.assertEqual(sorted(p.name for p in book.iterdir()), ['handbook.html'])
                self.assertEqual((book / 'handbook.html').read_text(encoding='utf-8'), 'ORIGINAL')

    def test_write_failure_cleans_only_the_new_version(self):
        original_open = Path.open

        def fail_manifest_write(path, mode='r', *args, **kwargs):
            if path.name == 'flow.json' and mode == 'x':
                raise OSError('Synthetic disk failure')
            return original_open(path, mode, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp)
            preserved = book / 'versions/existing'
            preserved.mkdir(parents=True)
            (preserved / 'handbook.html').write_text('EXISTING', encoding='utf-8')
            with mock.patch.object(Path, 'open', fail_manifest_write):
                with self.assertRaises(OSError):
                    exports.write_revision(book, self.data, {}, [])
            self.assertEqual(list((book / 'versions').iterdir()), [preserved])
            self.assertEqual((preserved / 'handbook.html').read_text(encoding='utf-8'), 'EXISTING')

    def test_cancel_before_validation_does_not_touch_filesystem(self):
        cancel = threading.Event()
        cancel.set()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(InterruptedError):
                exports.write_revision(temp, self.data, {}, [], cancel_event=cancel)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_cancel_during_validation_does_not_create_versions(self):
        cancel = threading.Event()
        original_render = exports._render

        def cancel_after_render(data):
            page = original_render(data)
            cancel.set()
            return page

        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(exports, '_render', cancel_after_render):
                with self.assertRaises(InterruptedError):
                    exports.write_revision(temp, self.data, {}, [], cancel_event=cancel)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_cancelling_staged_writes_removes_only_own_temporary_directory(self):
        original_open = Path.open
        for cancel_after in ('handbook.html', 'flow.json'):
            with self.subTest(cancel_after=cancel_after), tempfile.TemporaryDirectory() as temp:
                book = Path(temp)
                existing = book / 'versions/existing'
                existing.mkdir(parents=True)
                (existing / 'handbook.html').write_text('KEEP EXISTING', encoding='utf-8')
                foreign = book / 'versions/.another-worker'
                foreign.mkdir()
                (foreign / 'keep.txt').write_text('KEEP FOREIGN', encoding='utf-8')
                cancel = threading.Event()
                written = []

                @contextmanager
                def cancel_after_close(path, mode='r', *args, **kwargs):
                    with original_open(path, mode, *args, **kwargs) as handle:
                        yield handle
                    if mode == 'x':
                        written.append(path.name)
                        self.assertTrue(path.parent.name.startswith('.'))
                        self.assertEqual([p for p in (book / 'versions').iterdir()
                                          if not p.name.startswith('.')], [existing])
                        if path.name == cancel_after:
                            cancel.set()

                with mock.patch.object(Path, 'open', cancel_after_close):
                    with self.assertRaises(InterruptedError):
                        exports.write_revision(book, self.data, {}, [], cancel_event=cancel)
                self.assertEqual(set((book / 'versions').iterdir()), {existing, foreign})
                self.assertEqual((existing / 'handbook.html').read_text(encoding='utf-8'), 'KEEP EXISTING')
                self.assertEqual((foreign / 'keep.txt').read_text(encoding='utf-8'), 'KEEP FOREIGN')
                self.assertEqual(written, ['handbook.html'] if cancel_after == 'handbook.html'
                                 else ['handbook.html', 'flow.json'])

    def test_success_publishes_both_files_in_one_directory_rename(self):
        original_rename = Path.rename
        publications = []

        def inspect_commit(path, target):
            self.assertTrue(path.name.startswith('.'))
            self.assertFalse(target.exists())
            self.assertEqual({p.name for p in path.iterdir()}, {'handbook.html', 'flow.json'})
            data = json.loads((path / 'flow.json').read_text(encoding='utf-8'))
            html_data = json.loads(PageData((path / 'handbook.html').read_text(encoding='utf-8')).payload)
            self.assertEqual(data['qa'], html_data['qa'])
            publications.append(target)
            return original_rename(path, target)

        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(Path, 'rename', inspect_commit):
                relative = exports.write_revision(temp, self.data, {}, [completed()],
                                                  cancel_event=threading.Event())
            output = Path(temp) / relative
            self.assertEqual(publications, [output.parent])
            self.assertEqual(list((Path(temp) / 'versions').iterdir()), [output.parent])

    def test_cancellation_after_commit_keeps_and_returns_published_version(self):
        original_rename = Path.rename
        cancel = threading.Event()

        def cancel_after_commit(path, target):
            result = original_rename(path, target)
            cancel.set()
            return result

        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(Path, 'rename', cancel_after_commit):
                relative = exports.write_revision(temp, self.data, {}, [], cancel_event=cancel)
            self.assertTrue(cancel.is_set())
            self.assertTrue((Path(temp) / relative).is_file())
            self.assertTrue((Path(temp) / relative).with_name('flow.json').is_file())

    def test_publication_collision_preserves_existing_version_and_cleans_stage(self):
        original_rename = Path.rename
        raced = []

        def another_writer_wins(path, target):
            target.mkdir()
            (target / 'handbook.html').write_text('OTHER WRITER', encoding='utf-8')
            raced.append(target)
            return original_rename(path, target)

        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(Path, 'rename', another_writer_wins):
                with self.assertRaises(OSError):
                    exports.write_revision(temp, self.data, {}, [])
            self.assertEqual(len(raced), 1)
            self.assertEqual(list((Path(temp) / 'versions').iterdir()), raced)
            self.assertEqual((raced[0] / 'handbook.html').read_text(encoding='utf-8'), 'OTHER WRITER')

    def test_versions_symlink_cannot_write_outside_book(self):
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp) / 'book'
            outside = Path(temp) / 'outside'
            book.mkdir()
            outside.mkdir()
            try:
                (book / 'versions').symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest('Creating directory symlinks is unavailable on this host')
            with self.assertRaises(ValueError):
                exports.write_revision(book, self.data, {}, [])
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
