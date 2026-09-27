const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(0, 'utf8');
const elements = new Map();
function element() {
  return {style: {}, value: '', checked: true, disabled: false, innerHTML: '',
    classList: {add(){}, remove(){}}, children: [],
    addEventListener(){}, reset(){}, appendChild(node){this.children.push(node);},
    set textContent(value){this.innerHTML = String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
  };
}
const rate = {id: 42, rate_name: '<img src=x onerror=alert(1)>', rate_category:'student',
  price:'50', currency:'PEN', conditions:'Carnet <vigente>', is_active:true};
const requests = [];
const context = vm.createContext({console, setTimeout(){}, alert(){}, confirm(){return true;},
  document: {getElementById(id){if(!elements.has(id)) elements.set(id,element()); return elements.get(id);},
    querySelectorAll(){return [];}, createElement: element},
  fetch: async (url, options={}) => {
    requests.push({url,options});
    return {ok:true,json:async()=> options.method ? {ok:true,rate_id:42} :
      (url.includes('/rates') ? [rate] : [])};
  }
});
vm.runInContext(source, context);
(async()=>{
  await vm.runInContext("loadTourRates('city-tour-cusco')", context);
  assert.equal(vm.runInContext('CURRENT_TOUR_RATES.length',context),1);
  const rendered=elements.get('tourRatesList').children.at(-1).innerHTML;
  assert.ok(rendered.includes('&lt;img'));
  assert.ok(!rendered.includes('<img src=x'));
  vm.runInContext('editRateById(42)',context);
  assert.equal(elements.get('rateName').value,rate.rate_name);
  assert.equal(elements.get('rateCategory').value,'student');
  context.document.getElementById('formEntityId').value='city-tour-cusco';
  await vm.runInContext('saveRate()',context);
  const posted=requests.find(r=>r.options.method==='POST');
  assert.ok(posted);
  const body=JSON.parse(posted.options.body);
  assert.equal(body.rate_category,'student');
  assert.equal(body.rate_name,rate.rate_name);
  assert.equal(body.id,42);
  assert.equal(posted.options.headers['X-Catalog-CSRF'],'synthetic-csrf');
  console.log('PASS rendered JS: load, escaped render, edit and save API contract');
})().catch(error=>{console.error(error);process.exitCode=1;});
