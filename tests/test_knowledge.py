import json
import os
os.environ['PYTHONUTF8'] = '1'
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'project-handbook/scripts/build_knowledge.py'


def fixture():
    return {'title':'测试手册', 'book_id':'synthetic-demo', 'sources':[{'id':'s-one','title':'规则','path':'config/demo.txt','locator':'L1','excerpt':'启用条件：等级达到10。<script>alert(1)</script>','sha256':'a'*64}], 'systems':[{'id':'growth','title':'成长','summary':'成长规则','question':'等级到几才开放成长？','nodes':[{'id':'unlock','title':'开放条件','body':'等级达到10才开放。','kind':'配置声明','sources':['s-one'],'related':['combat']} ]},{'id':'combat','title':'战斗','summary':'尚缺服务端','question':'战斗结算缺了哪一端？','nodes':[{'id':'boundary','title':'结算边界','body':'服务端未提供。','kind':'待确认','sources':[],'related':[]}]}], 'relations':[{'from':'growth','to':'combat','label':'阅读路径，不是调用链','status':'inferred'}]}


def onboarding_fixture():
    data = fixture()
    data['project'] = {
        'purpose': '让新人先看懂入口、主链路和边界。',
        'audience': '刚接手项目的客户端、服务端和策划同学。',
        'status': 'partial',
        'layers': [
            {'id': 'client', 'title': '客户端', 'summary': '入口与展示。', 'status': 'verified', 'sources': ['s-one']},
            {'id': 'server', 'title': '服务端', 'summary': '结算待补充。', 'status': 'open', 'sources': []},
        ],
        'entrypoints': [
            {'title': '成长入口', 'path': 'client/growth.ts', 'summary': '从客户端进入成长页面。', 'status': 'declared', 'sources': ['s-one']},
        ],
        'runtime': [
            {'title': '本地启动', 'command': 'python app.py', 'summary': '启动命令来自旧文档。', 'status': 'declared', 'sources': []},
        ],
    }
    data['flows'] = [{
        'id': 'newcomer-path',
        'title': '新人先理解成长链路',
        'goal': '从入口走到开放条件，再确认服务端缺口。',
        'status': 'partial',
        'lanes': [
            {'id': 'growth-lane', 'title': '成长入口', 'tone': 'a', 'handoff': '进入共用核对', 'steps': [
                {'kind': 'start', 'label': '找到入口', 'action': '打开成长页面。', 'output': '看到开放条件。', 'systems': ['growth'], 'sources': ['s-one'], 'status': 'verified', 'tone': 'a'},
            ]},
            {'id': 'combat-lane', 'title': '战斗入口', 'tone': 'b', 'handoff': '进入共用核对', 'steps': [
                {'kind': 'start', 'label': '检查战斗入口', 'action': '从战斗页进入同一核对。', 'output': '带着缺口进入共用段。', 'systems': ['combat'], 'sources': [], 'status': 'open', 'tone': 'b'},
            ]},
        ],
        'shared': {'title': '共用核对', 'banner': '两条入口汇入同一核对', 'steps': [
            {'kind': 'formula', 'label': '确认边界', 'action': '检查服务端结算。', 'output': '记录待补充项。', 'systems': ['combat'], 'sources': [], 'status': 'open', 'tone': 'shared'},
        ]},
    }]
    data['risks'] = [{
        'title': '服务端结算未纳入资料',
        'impact': 'high',
        'status': 'open',
        'detail': '当前只能确认客户端声明。',
        'next': '补充服务端入口和落库证据。',
        'sources': [],
    }]
    return data


class KnowledgeTest(unittest.TestCase):
    def run_build(self, data, root):
        manifest=root/'knowledge.json'; manifest.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        return subprocess.run([sys.executable,str(SCRIPT),str(manifest),str(root/'book')],capture_output=True,text=True,encoding='utf-8')

    def test_clickable_nodes_evidence_and_section_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=self.run_build(fixture(),root)
            self.assertEqual(result.returncode,0,result.stderr)
            site=root/'book/site'
            page=(site/'pages/growth.html').read_text(encoding='utf-8')
            self.assertIn('id="unlock"',page)
            self.assertIn('data-ask=',page)
            home=(site/'index.html').read_text(encoding='utf-8')
            architecture=(site/'pages/architecture.html').read_text(encoding='utf-8')
            self.assertIn('id="layer-1"', architecture)
            self.assertIn('data-flow-stage',home)
            self.assertIn('VERTICAL FLOW',home)
            self.assertIn('打开步骤说明',home)
            self.assertIn('topic-index',home)
            self.assertNotIn('data-map-stage',home)
            self.assertNotIn('vf-toggle',home)
            self.assertIn('等级到几才开放成长？',home)
            self.assertNotIn('阅读关联图',home)
            self.assertNotIn('briefing-band',home)
            self.assertNotIn('orientation-board',home)
            sidebar=home.split('<aside class="sidebar">',1)[1].split('</aside>',1)[0]
            self.assertNotIn('source-s-one',sidebar)
            self.assertIn('pages/growth.html',sidebar)
            self.assertIn('source-s-one.html?from=growth.unlock',page)
            evidence=(site/'pages/source-s-one.html').read_text(encoding='utf-8')
            self.assertIn('&lt;script&gt;',evidence)
            self.assertIn('返回专题',evidence)
            self.assertIn('growth.html#unlock',evidence)
            index=json.loads((site/'assets/search-index.json').read_text(encoding='utf-8'))
            self.assertTrue(any(i['url']=='pages/growth.html#unlock' and '等级达到10' in i['text'] for i in index))
            self.assertNotIn('问这个节点', next(i['text'] for i in index if i['url']=='pages/growth.html#unlock'))
            verify=subprocess.run([sys.executable,str(ROOT/'project-handbook/scripts/verify_handbook.py'),str(root/'book')],capture_output=True,text=True)
            self.assertEqual(verify.returncode,0,verify.stdout+verify.stderr)

    def test_shared_branches_render_side_by_side(self):
        data=onboarding_fixture()
        data['flows'][0]['shared']['groups']=[{
            'title':'类型分支','tone':'shared','steps':[{
                'kind':'check','label':'按类型分列','status':'open','tone':'shared','branches':[
                    {'title':'物理','tone':'a','steps':[{'kind':'formula','label':'物理层','action':'物理增减伤','status':'open','tone':'a'}]},
                    {'title':'法术','tone':'b','steps':[{'kind':'formula','label':'法术层','action':'法术增减伤','status':'open','tone':'b'}]},
                ],
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=self.run_build(data,root)
            self.assertEqual(result.returncode,0,result.stderr)
            home=(root/'book/site/index.html').read_text(encoding='utf-8')
            self.assertIn('vf-branch-row',home)
            self.assertIn('vf-branch-col',home)
            self.assertIn('vf-group vf-tone-a',home)
            self.assertIn('vf-wide',home)
            self.assertIn('物理增减伤',home)
            self.assertIn('法术增减伤',home)

    def test_invalid_lane_tone_rejected(self):
        data=onboarding_fixture(); data['flows'][0]['lanes'][0]['tone']='phys'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=self.run_build(data,root)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('invalid lane tone',result.stderr)
            self.assertFalse((root/'book').exists())

    def test_unknown_source_rejected_without_output(self):
        data=fixture(); data['systems'][0]['nodes'][0]['sources']=['missing']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result=self.run_build(data,root)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('unknown source',result.stderr)
            self.assertFalse((root/'book').exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'book').mkdir(); (root/'book/keep.txt').write_text('keep')
            result=self.run_build(fixture(),root)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((root/'book/keep.txt').read_text(),'keep')

    def test_newcomer_handbook_renders_project_map_flow_and_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_build(onboarding_fixture(), root)
            self.assertEqual(result.returncode, 0, result.stderr)
            site = root / 'book' / 'site'
            home = (site / 'index.html').read_text(encoding='utf-8')
            book = json.loads((root / 'book' / 'book.json').read_text(encoding='utf-8'))
            labels = [part['label'] for part in book['parts']]
            self.assertEqual(labels[:3], ['开始', '项目地图', '关键链路'])
            self.assertIn('onboarding-hero', home)
            self.assertIn('data-flow-stage', home)
            self.assertIn('data-flow-lane="growth-lane"', home)
            self.assertIn('data-flow-lane="combat-lane"', home)
            self.assertIn('data-flow-panel="combat-lane"', home)
            self.assertIn('id="shared-flow"', home)
            self.assertIn('vf-separator', home)
            self.assertIn('vf-shared-banner', home)
            self.assertIn('vf-arrow-label vf-tone-a', home)
            self.assertIn('VERTICAL FLOW', home)
            self.assertNotIn('下面共用段对所有入口都生效', home)
            self.assertNotIn('data-map-stage', home)
            self.assertNotIn('data-map-play', home)
            self.assertIn('新人先理解成长链路', home)
            self.assertIn('服务端结算未纳入资料', home)
            self.assertNotIn('briefing-band', home)
            self.assertNotIn('orientation-board', home)
            self.assertNotIn('class="layer-map"', home)
            self.assertNotIn('15 分钟', home)
            architecture = (site / 'pages' / 'architecture.html').read_text(encoding='utf-8')
            self.assertIn('客户端', architecture)
            self.assertIn('服务端', architecture)
            self.assertIn('id="layer-1"', architecture)
            self.assertIn('id="layer-2"', architecture)
            self.assertIn('href="#layer-2"', architecture)
            self.assertIn('按资料归属排列', architecture)
            self.assertIn('data-map-stage', architecture)
            self.assertIn('data-map-id="client"', architecture)
            flow = (site / 'pages' / 'flows.html').read_text(encoding='utf-8')
            self.assertIn('id="newcomer-path"', flow)
            self.assertIn('找到入口', flow)
            self.assertIn('flow-sequence-step', flow)
            self.assertEqual(flow.count('class="flow-step"'), 3)
            self.assertIn('status-badge', flow)
            self.assertIn('source-s-one.html?from=flow.newcomer-path.growth-lane.0', flow)
            self.assertIn('data-flow-stage', flow)
            style = (site / 'assets' / 'style.css').read_text(encoding='utf-8')
            self.assertIn('.atlas-book .flow-sequence-step::before{content:none', style)
            self.assertIn('.atlas-book .flow-sequence-step .flow-step', style)
            self.assertNotIn('flow-sequence-step::before{content:counter', style)
            self.assertIn('body.atlas-book{overflow-x:hidden}', style)
            self.assertIn('.atlas-book .content-wrap,.atlas-book .article,.atlas-book .map-band{min-width:0}', style)
            self.assertIn('.atlas-book .map-scroll{max-width:100%;overflow-x:auto}', style)
            self.assertIn('.atlas-book .map-stage', style)
            self.assertIn('[data-lens=route]', style)
            self.assertIn('.atlas-book .vf-stage', style)
            self.assertIn('.atlas-book .vf-toggle-btn', style)
            self.assertIn('.atlas-book .vf-shared', style)
            self.assertIn('.atlas-book .vf-separator', style)
            self.assertIn('.atlas-book .vf-group.vf-wide', style)
            self.assertIn('minmax(0,1fr) minmax(280px,320px)', style)
            source = (site / 'pages' / 'source-s-one.html').read_text(encoding='utf-8')
            self.assertIn('return-flow', source)
            self.assertIn('data-return="flow.newcomer-path.growth-lane.0"', source)
            risks = (site / 'pages' / 'risks.html').read_text(encoding='utf-8')
            self.assertIn('服务端结算未纳入资料', risks)
            verify = subprocess.run([sys.executable, str(ROOT / 'project-handbook/scripts/verify_handbook.py'), str(root / 'book')], capture_output=True, text=True)
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    @unittest.skipUnless(shutil.which('node'), 'node not installed')
    def test_atlas_map_interaction_harness(self):
        result = subprocess.run(['node', str(ROOT / 'tests' / 'test_atlas_ui.cjs')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__=='__main__': unittest.main()
