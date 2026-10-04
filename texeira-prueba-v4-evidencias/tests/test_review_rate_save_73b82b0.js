// Reuse the existing fixture without changing its eleven regression cases.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const original = fs.readFileSync(path.join(__dirname, 'test_review_catalog_form_9fcf9df.js'), 'utf8');
const marker = '\nconst cases = [';
const boundary = original.indexOf(marker);
if (boundary < 0) throw new Error('Existing form fixture was not found');
const prefix = original.slice(0, boundary);

const scenarios = String.raw`
const cases = [
  ['Segundo guardado de tarifa recién creada actualiza el ID recibido, sin otro alta', async () => {
    const f = fixture(); await tick(); f.savedTour();
    let completePost;
    f.fetchResult = async (url, options) => options.method === 'POST'
      ? new Promise(resolve => { completePost = resolve; }) : reply([]);
    f.run('showRateForm()');
    f.el('rateName').value = 'Tarifa nueva';
    f.el('ratePrice').value = '50';
    const saving = f.run('saveRate()');
    const canEditDuringSave = !f.el('rateConditions').disabled;
    if (canEditDuringSave) f.el('rateConditions').value = 'Condición posterior al envío';
    completePost(reply({ok:true, rate_id:99}));
    await saving;
    if (!canEditDuringSave) {
      assert.equal(f.run('isRateFormDirty()'), false);
      return; // Blocking edits during save is also a valid solution.
    }
    assert.equal(f.el('rateConditions').value, 'Condición posterior al envío');
    f.fetchResult = async (url, options) => options.method === 'POST'
      ? reply({ok:true, rate_id:99}) : reply([]);
    await f.run('saveRate()');
    const posts = f.requests.filter(x => x.options.method === 'POST');
    assert.equal(posts.length, 2);
    assert.equal(JSON.parse(posts[1].options.body).id, 99);
  }],
  ['Respuesta de guardar tarifa A no marca como pendiente la tarifa B sin cambios', async () => {
    const f = fixture(); await tick(); f.savedTour();
    f.run("CURRENT_TOUR_RATES=[{id:1,rate_name:'A',price:'60'},{id:2,rate_name:'B',price:'70'}]; editRateById(1)");
    f.el('ratePrice').value = '55';
    let completePost;
    f.fetchResult = async (url, options) => options.method === 'POST'
      ? new Promise(resolve => { completePost = resolve; }) : reply([]);
    const saving = f.run('saveRate()');
    f.run('editRateById(2)');
    if (f.el('rateId').value === '1') {
      completePost(reply({ok:true, rate_id:1}));
      await saving;
      assert.equal(f.run('isRateFormDirty()'), false);
      return; // An explicit lock on switching editors is also valid.
    }
    assert.equal(f.el('rateId').value, '2');
    assert.equal(f.run('isRateFormDirty()'), false);
    completePost(reply({ok:true, rate_id:1}));
    await saving;
    assert.equal(f.el('rateId').value, '2');
    assert.equal(f.run('JSON.parse(initialRateSnapshot).id'), '2');
    assert.equal(f.run('isRateFormDirty()'), false);
  }],
];

(async () => {
  let failed = 0;
  for (const [name, run] of cases) {
    try { await run(); console.log('PASS:', name); }
    catch (error) { failed++; console.error('FAIL:', name, '\n', error.message); }
  }
  console.log((cases.length - failed) + ' PASS / ' + failed + ' FAIL; JavaScript real, DOM y API simulados');
  process.exitCode = failed ? 1 : 0;
})();
`;
vm.runInNewContext(prefix + scenarios, {require, console, process, setImmediate},
                   {filename: 'independent-rate-save-review.js'});
