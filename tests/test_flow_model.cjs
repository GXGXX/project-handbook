// The page's own checks (flow-model.js) must report exactly what build_flow.py
// reports, so a page built without Python is held to the same rules.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const model = require(path.join(root, 'project-handbook/assets/flow-model.js'));
const base = JSON.parse(fs.readFileSync(path.join(root, 'project-handbook/assets/flow.example.json'), 'utf8'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'flow_cases.json'), 'utf8'));

function apply(data, ops) {
  for (const op of ops) {
    const keys = op.set || op.delete;
    let target = data;
    for (const key of keys.slice(0, -1)) target = target[key];
    const last = keys[keys.length - 1];
    if (op.delete) delete target[last];
    else target[last] = op.value;
  }
  return data;
}

for (const item of cases) {
  test(item.name, () => {
    const data = apply(structuredClone(base), item.ops);
    let error = null;
    try { model.validate(data); } catch (e) { error = e.message; }
    assert.equal(error, item.error);
  });
}

test('placing sections leaves the authored sections untouched', () => {
  const placed = model.prepare(base);
  assert.deepEqual(placed.graphs, base.graphs);
  assert.deepEqual(model.prepare(placed).canvas, placed.canvas, 'placing again gives the same canvas');
  assert.equal(placed.canvas.nodes.find(n => n.id === 'callback').row, 5);
  const python = require('node:child_process').spawnSync(process.env.PYTHON_EXECUTABLE || 'python', ['-B', '-X', 'utf8', '-c',
    'import json,sys;sys.path.insert(0,sys.argv[1]);import build_flow as b;print(json.dumps(b.canvas_data(json.load(open(sys.argv[2],encoding="utf-8")))["canvas"],ensure_ascii=False))',
    path.join(root, 'project-handbook/scripts'), path.join(root, 'project-handbook/assets/flow.example.json')], {encoding: 'utf8'});
  assert.equal(python.status, 0, python.stderr);
  assert.deepEqual(placed.canvas, JSON.parse(python.stdout), 'same canvas as build_flow.py');
  assert.deepEqual(placed.canvas.sections.map(s => s.title), ['创建订单', '支付结果']);
});
