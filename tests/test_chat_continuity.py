import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'project-handbook/scripts/chat_server.py'
spec=importlib.util.spec_from_file_location('relay',SCRIPT); relay=importlib.util.module_from_spec(spec); spec.loader.exec_module(relay)

class RetrievalTest(unittest.TestCase):
    def test_zero_history_sends_nothing(self):
        self.assertEqual(relay.select_matches([{'url':'pages/demo.html#x','text':'rule'}], 'explain this', 'https://invalid/x'), [])
    def test_selected_node_uses_only_existing_index(self):
        node={'url':'pages/demo.html#x','text':'rule'}
        self.assertEqual(relay.select_matches([node], 'explain this', node['url']), [node])
    def test_provider_gate(self):
        with self.assertRaisesRegex(relay.ChatError, '仅证据'):
            relay.check_model_access(True, True)
        with self.assertRaisesRegex(relay.ChatError, '确认'):
            relay.check_model_access(False, False)
        relay.check_model_access(False, True)
    def test_history_disabled(self):
        self.assertEqual(relay.safe_history([{'role':'user','content':'private'}],0),[])
    def test_question_stopwords_do_not_match_unrelated_page(self):
        corpus=[{'title':'示例规则','text':'可以在这里查看相关的配置，说明依据和未确认的部分。'}]
        self.assertEqual(relay.retrieve(corpus,'火星天气怎么样？'),[])
    def test_evidence_answer_contains_excerpt_and_no_invented_inference(self):
        self.assertTrue(hasattr(relay,'evidence_answer'),'missing evidence-only answer')
        answer=relay.evidence_answer([{'title':'开放条件','url':'pages/growth.html#unlock','text':'unlock_level = 10'}])
        self.assertIn('unlock_level = 10',answer)
        self.assertIn('[1]',answer)
    def test_empty_evidence_has_actionable_next_step(self):
        self.assertTrue(hasattr(relay,'evidence_answer'),'missing evidence-only answer')
        self.assertIn('下一步',relay.evidence_answer([]))
    def test_models_url_and_ids(self):
        self.assertEqual(relay.provider_models_url('https://api.example/v1'),'https://api.example/v1/models')
        self.assertEqual(relay.provider_models_url('https://api.example/v1/chat/completions'),'https://api.example/v1/models')
        self.assertEqual(relay.model_ids({'data':[{'id':'gpt-test'},{'id':'other'}]}),['gpt-test','other'])

if __name__=='__main__': unittest.main()
