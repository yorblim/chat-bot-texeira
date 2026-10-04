const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(0, 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const reply = data => ({ok: true, json: async () => data});

function fixture() {
  const elements = new Map();
  const requests = [];
  const confirmations = [];
  function element() {
    let text = '', html = '', value = '';
    const classes = new Set();
    return {
      style: {}, checked: true, disabled: false, children: [], handlers: {},
      get value() { return value; }, set value(v) { value = String(v ?? ''); },
      get textContent() { return text; },
      set textContent(v) { text = String(v); html = text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); },
      get innerHTML() { return html; }, set innerHTML(v) { html = String(v); this.children = []; },
      classList: {add(...names) { names.forEach(n => classes.add(n)); },
                  remove(...names) { names.forEach(n => classes.delete(n)); },
                  contains(name) { return classes.has(name); }},
      addEventListener(name, fn) { this.handlers[name] = fn; },
      reset() {}, focus() {}, querySelector() { return null; },
      appendChild(node) { this.children.push(node); },
    };
  }
  const doc = {
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    createElement: element, querySelectorAll() { return []; }, addEventListener() {},
    activeElement: null,
  };
  const f = {elements, requests, confirmations, confirmResult: true,
    fetchResult: async () => reply([])};
  f.context = vm.createContext({console, setTimeout() {}, alert() {},
    confirm(message) { confirmations.push(message); return f.confirmResult; },
    document: doc,
    fetch: async (url, options = {}) => {
      requests.push({url, options});
      return f.fetchResult(url, options);
    },
  });
  f.run = code => vm.runInContext(code, f.context);
  f.el = id => doc.getElementById(id);
  f.el('rateFormBox').style.display = 'none';
  f.el('formCurrency').value = 'USD';
  f.el('rateCurrency').value = 'USD';
  vm.runInContext(source, f.context);
  f.savedTour = () => {
    f.el('formEntityId').value = 'review-tour';
    f.el('formIsEdit').value = '1';
    f.el('formName').value = 'Tour guardado';
    f.el('formPrice').value = '80';
    f.el('formCurrency').value = 'USD';
    f.run('initialTourSnapshot = getTourFormSnapshot()');
  };
  return f;
}

const cases = [
  ['Vigencia usa fecha Lima incluso si el navegador está en Lima', async () => {
    const f = fixture(); await tick();
    const timestamp = Date.parse('2026-10-04T01:00:00Z'); // 03/10, 20:00 en Lima.
    class FixedLimaDate extends Date {
      constructor(...args) { super(args.length ? args[0] : timestamp); }
      getTimezoneOffset() { return 300; }
    }
    f.context.Date = FixedLimaDate;
    assert.equal(f.run('getLimaDateStr()'), '2026-10-03');
    assert.equal(f.run("getRateStatusInfo({is_active:true,valid_to:'2026-10-03'}).cls"),
                 'rate-status-active');
  }],
  ['Editar otra tarifa permite conservar el borrador al rechazar descarte', async () => {
    const f = fixture(); await tick(); f.confirmResult = false;
    f.run("CURRENT_TOUR_RATES = [{id:1,rate_name:'Tarifa A',price:'60'}, {id:2,rate_name:'Tarifa B',price:'70'}]; editRateById(1)");
    f.el('ratePrice').value = '55';
    f.run('editRateById(2)');
    assert.equal(f.el('rateId').value, '1');
    assert.equal(f.el('ratePrice').value, '55');
    assert.ok(f.confirmations.length > 0);
  }],
  ['Añadir tarifa no sustituye silenciosamente una tarifa pendiente', async () => {
    const f = fixture(); await tick(); f.confirmResult = false;
    f.run('showRateForm()');
    f.el('rateName').value = 'Borrador pendiente';
    f.el('ratePrice').value = '55';
    f.run('showRateForm()');
    assert.equal(f.el('rateName').value, 'Borrador pendiente');
    assert.ok(f.confirmations.length > 0);
  }],
  ['Referencia de tarifas usa precio guardado, no borrador descartado', async () => {
    const f = fixture(); await tick(); f.savedTour();
    f.el('formPrice').value = '90'; f.el('formCurrency').value = 'PEN';
    f.run("switchModalTab('tourRates')");
    assert.equal(f.el('ratesTourBaseRef').textContent, 'USD 80');
  }],
  ['Cambios hechos durante el POST siguen pendientes tras la respuesta', async () => {
    const f = fixture(); await tick(); f.savedTour();
    let completePost;
    f.fetchResult = async (url, options) => options.method === 'POST'
      ? new Promise(resolve => { completePost = resolve; }) : reply([]);
    f.el('formName').value = 'Nombre enviado A';
    const saving = f.el('tourForm').handlers.submit({preventDefault() {}});
    assert.equal(JSON.parse(f.requests.at(-1).options.body).name, 'Nombre enviado A');
    // También es válida una solución que bloquee los campos durante el envío.
    const canEditDuringSave = !f.el('formName').disabled;
    if (canEditDuringSave) f.el('formName').value = 'Cambio posterior B';
    completePost(reply({ok: true, entity_id: 'review-tour'}));
    await saving;
    assert.equal(f.run('isTourFormDirty()'), canEditDuringSave);
  }],
  ['Respuesta tardía de tarifas A no reemplaza las del tour B', async () => {
    const f = fixture(); await tick();
    let completeA;
    f.fetchResult = async url => url.includes('/tour-a/')
      ? new Promise(resolve => { completeA = resolve; })
      : reply([{id:2,entity_id:'tour-b',rate_name:'Tarifa B',price:'70',is_active:true}]);
    f.el('formEntityId').value = 'tour-a';
    const loadingA = f.run("loadTourRates('tour-a')");
    f.el('formEntityId').value = 'tour-b';
    await f.run("loadTourRates('tour-b')");
    completeA(reply([{id:1,entity_id:'tour-a',rate_name:'Tarifa A',price:'60',is_active:true}]));
    await loadingA;
    assert.equal(f.run('CURRENT_TOUR_RATES[0].entity_id'), 'tour-b');
  }],
  ['POST fallido de tour conserva borrador y estado pendiente', async () => {
    const f = fixture(); await tick(); f.savedTour();
    f.fetchResult = async (url, options) => {
      if (options.method === 'POST') {
        return { ok: false, json: async () => ({ error: 'Error del servidor al guardar tour' }) };
      }
      return reply([]);
    };
    f.el('formName').value = 'Tour con fallo';
    await f.el('tourForm').handlers.submit({ preventDefault() {} });
    assert.equal(f.el('formName').value, 'Tour con fallo');
    assert.equal(f.run('isTourFormDirty()'), true);
  }],
  ['Respuesta tardía tras cerrar o crear otro tour no altera el formulario nuevo', async () => {
    const f = fixture(); await tick();
    let completeA;
    f.fetchResult = async url => url.includes('/tour-a/')
      ? new Promise(resolve => { completeA = resolve; })
      : reply([]);
    f.el('formEntityId').value = 'tour-a';
    const loadingA = f.run("loadTourRates('tour-a')");
    // Usuario hace clic en "Nuevo Tour"
    f.el('btnNewTour').handlers.click();
    assert.equal(f.el('formEntityId').value, '');
    assert.equal(f.el('formIsEdit').value, '0');
    // Llega respuesta demorada de tour-a
    completeA(reply([{ id: 1, entity_id: 'tour-a', rate_name: 'Tarifa A', price: '60', is_active: true }]));
    await loadingA;
    assert.equal(f.run('CURRENT_TOUR_RATES.length'), 0);
  }],
  ['Guardar una tarifa conserva ediciones posteriores de la misma tarifa sin cerrarla', async () => {
    const f = fixture(); await tick(); f.savedTour();
    let completeRatePost;
    f.fetchResult = async (url, options) => options.method === 'POST'
      ? new Promise(resolve => { completeRatePost = resolve; })
      : reply([]);
    f.run('showRateForm()');
    f.el('rateName').value = 'Tarifa Enviada';
    f.el('ratePrice').value = '50';
    const savingRate = f.run('saveRate()');
    // El usuario sigue editando la tarifa mientras el POST está en vuelo
    f.el('rateConditions').value = 'Solo con carnet universitario 2026';
    completeRatePost(reply({ ok: true, rate_id: 99 }));
    await savingRate;
    assert.notEqual(f.el('rateFormBox').style.display, 'none');
    assert.equal(f.el('rateConditions').value, 'Solo con carnet universitario 2026');
    assert.equal(f.run('isRateFormDirty()'), true);
  }],
  ['Estados de vigencia alrededor de medianoche en Lima (inclusivo y fin de día)', async () => {
    const f = fixture(); await tick();
    // 23:59:59 del 03/10 en Lima -> UTC: 2026-10-04T04:59:59Z
    const tBeforeMidnight = Date.parse('2026-10-04T04:59:59Z');
    class LimaBeforeMidnight extends Date {
      constructor(...args) { super(args.length ? args[0] : tBeforeMidnight); }
      getTimezoneOffset() { return 300; }
    }
    f.context.Date = LimaBeforeMidnight;
    assert.equal(f.run('getLimaDateStr()'), '2026-10-03');
    // Tarifa que vence el 03/10 sigue vigente a las 23:59:59 (inclusivo)
    assert.equal(f.run("getRateStatusInfo({is_active:true, valid_to:'2026-10-03'}).cls"), 'rate-status-active');
    // Tarifa programada para el 04/10 aún no empieza
    assert.equal(f.run("getRateStatusInfo({is_active:true, valid_from:'2026-10-04'}).cls"), 'rate-status-scheduled');

    // 00:00:01 del 04/10 en Lima -> UTC: 2026-10-04T05:00:01Z
    const tAfterMidnight = Date.parse('2026-10-04T05:00:01Z');
    class LimaAfterMidnight extends Date {
      constructor(...args) { super(args.length ? args[0] : tAfterMidnight); }
      getTimezoneOffset() { return 300; }
    }
    f.context.Date = LimaAfterMidnight;
    assert.equal(f.run('getLimaDateStr()'), '2026-10-04');
    // Tarifa que venció el 03/10 ya está vencida
    assert.equal(f.run("getRateStatusInfo({is_active:true, valid_to:'2026-10-03'}).cls"), 'rate-status-expired');
    // Tarifa programada para el 04/10 ya está activa
    assert.equal(f.run("getRateStatusInfo({is_active:true, valid_from:'2026-10-04'}).cls"), 'rate-status-active');
  }],
  ['Independencia total entre tour y tarifa: guardar tarifa no afecta borrador de tour', async () => {
    const f = fixture(); await tick(); f.savedTour();
    f.el('formName').value = 'Tour con borrador activo';
    assert.equal(f.run('isTourFormDirty()'), true);
    f.run('showRateForm()');
    f.el('rateName').value = 'Tarifa Aislada';
    f.el('ratePrice').value = '45';
    f.fetchResult = async () => reply({ ok: true, rate_id: 101 });
    await f.run('saveRate()');
    // El formulario del tour debe conservar intacto su nombre y su estado dirty
    assert.equal(f.el('formName').value, 'Tour con borrador activo');
    assert.equal(f.run('isTourFormDirty()'), true);
  }],
];

(async () => {
  let failed = 0;
  for (const [name, run] of cases) {
    try { await run(); console.log('PASS:', name); }
    catch (error) { failed++; console.error('FAIL:', name, '\n', error.message); }
  }
  console.log(`${cases.length - failed} PASS / ${failed} FAIL; JavaScript real, DOM y API simulados`);
  process.exitCode = failed ? 1 : 0;
})();
