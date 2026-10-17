'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const element = () => ({value:'social',addEventListener(){},replaceChildren(){},append(){}});
const elements = new Map();
let projected;
const context = vm.createContext({
  document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element},
  window:{addEventListener(){}},matchMedia:()=>({matches:false}),
  AbortSignal:{timeout:()=>({})},fetch:()=>new Promise(()=>{}),
  LegisiMateAssets:{createIcons(){},cytoscape(options){projected=options.elements;return {on(){},destroy(){}};}}
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','web','app.js'),'utf8'),context);
const base = [
  {agent_id:1,engine_kind:'create_group',data:{group_id:1}},
  {agent_id:2,engine_kind:'join_group',data:{group_id:1}}
];
const follow = (platform,kind,id) => ({agent_id:1,platform,engine_kind:kind,effect_id:`${platform}:${id}`,data:{followee_id:1}});
const actions = [...base,follow('twitter','follow',1),follow('twitter','follow',2),follow('reddit','follow',3)];
function check(expectedLabels) {
  const run = {id:'fixture',agents:[{id:1,name:'One'},{id:2,name:'Two'}],actions};
  vm.runInContext(`current=${JSON.stringify(run)};graphSignature='';renderGraph();`,context);
  assert.equal(vm.runInContext('JSON.stringify(current.actions)',context),JSON.stringify(actions));
  const edges = Array.from(projected).filter(item=>item.data.source);
  assert.deepEqual(edges.filter(item=>item.data.label!=='member').map(item=>item.data.label).sort(),expectedLabels);
  assert.equal(edges.filter(item=>item.data.label==='member').length,2);
  assert.ok(edges.filter(item=>item.data.label!=='member').every(item=>item.data.target==='persona-2'));
}
check(['reddit follows','twitter follows']);
actions.push(follow('twitter','unfollow',4));
check(['reddit follows']);
actions.push(follow('reddit','unfollow',5));
check([]);
console.log('Social graph: duplicate suppression, platform isolation, unfollow and unchanged history pass');

const caseElements = new Map();
const caseRequests = [];
const documentListeners = new Map();
const caseElement = () => ({value: '', validity: {valid: true}, listeners: new Map(), hidden: false, style: {}, dataset: {}, children: [],
  classList: {add(){}, remove(){}}, addEventListener(name, listener){this.listeners.set(name, listener);}, reset(){},
  focus(){}, setAttribute(){}, scrollIntoView(){}, getBoundingClientRect: () => ({top: 0, bottom: 0, left: 0, right: 0}),
  replaceChildren(...children){this.children = children;}, append(...children){this.children.push(...children);}, elements: {namedItem: () => ({value: ''})}});
const caseContext = vm.createContext({
  document: {getElementById(id){if(!caseElements.has(id))caseElements.set(id,caseElement());return caseElements.get(id);},
    querySelector: selector => caseElements.get(selector) || (caseElements.set(selector, caseElement()), caseElements.get(selector)),
    querySelectorAll: () => [], createElement: caseElement, addEventListener(name, listener){documentListeners.set(name, listener);}},
  window: {addEventListener(){}, innerWidth: 1440, innerHeight: 900}, AbortSignal: {timeout:()=>({})},
  history: {replaceState(){}}, ConversationRoom: {reset(){}},
  fetch:(request, options = {}) => { caseRequests.push({request, method: options.method || 'GET'}); return new Promise(()=>{}); },
  LegisiMateAssets: {createIcons(){}}, setTimeout(){}, clearTimeout(){}
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','web','cases.js'),'utf8'),caseContext);
const tour = caseElements.get('tour');
assert.equal(tour.hidden,false,'The home tour opens before configuration requests finish');
assert.equal(caseElements.get('.app-shell').inert,true,'The page is inert while the tour runs');
tour.hidden = true;
vm.runInContext('initialize()',caseContext);
assert.equal(tour.hidden,false,'Every home-page initialization opens the tour again');
const tourNext = () => caseElements.get('tour-next').listeners.get('click')();
const tourBack = () => caseElements.get('tour-back').listeners.get('click')();
const title = () => caseElements.get('tour-title').textContent;
assert.equal(caseElements.get('tour-back').disabled,true);
assert.equal(caseElements.get('tour-next-label').textContent,'Load sample case');
caseElements.get('tour-skip').listeners.get('click')();
assert.equal(tour.hidden,true,'Skip closes the tour');
assert.equal(caseElements.get('.app-shell').inert,false,'The page is usable after skipping');
caseElements.get('start-tour').listeners.get('click')();
assert.equal(tour.hidden,false,'Take the tour reopens it manually');
assert.equal(title(),'Start with the sample case','A manual tour starts from the first step');
let escapePrevented = false;
documentListeners.get('keydown')({key: 'Escape', preventDefault(){escapePrevented = true;}});
assert.equal(tour.hidden,true,'Escape skips the tour'); assert.equal(escapePrevented,true);
caseElements.get('start-tour').listeners.get('click')();
tourNext();
assert.equal(title(),'What the sample just filled in');
assert.match(caseElements.get('case-scenario').value,/textile supplier/,'The first step loads the sample into the real form');
tourBack();
assert.equal(title(),'Start with the sample case');
tourNext(); tourNext();
assert.equal(title(),'Dates & records');
const bodyText = () => JSON.stringify(caseElements.get('tour-body').children.map(child => child.children.length ? child.children.map(item => item.textContent) : child.textContent));
const dateText = bodyText();
assert.match(dateText,/Assessment date/); assert.match(dateText,/Complaint filed: Not confirmed/);
tourNext();
assert.equal(title(),'Calendar review');
vm.runInContext("state.timeline={checked:2,attention:1,missing:1,checks:[{title:'Notice timing',status:'checked'}]};renderTour()",caseContext);
assert.match(bodyText(),/2 input checks met.*Notice timing: meets the base check/);
tourNext();
assert.equal(title(),'Supporting notes & your own case');
tourNext();
assert.equal(title(),'Review, consent, analyse');
assert.equal(caseElements.get('tour-skip').hidden,true,'The last step completes instead of skipping');
tourNext();
assert.equal(tour.hidden,true,'The final action completes the tour');
assert.equal(caseElements.get('.app-shell').inert,false,'The page is usable after the tour');
assert.equal(caseRequests.filter(item=>item.request==='/api/cases'&&item.method==='POST').length,0,'The tour never starts paid analysis');
assert.notEqual(caseElements.get('case-consent').checked,true,'The tour never grants model consent');
console.log('Home tour: every-load opening, skip, Escape, manual restart, sample loading, dates/records and calendar explanations, back, completion and no automatic analysis pass');
const treeRun = {id:'case-tree',branches:[1,2,3].map(branch => ({id:branch,title:`Alternative ${branch}`,status:'completed',
  assessment:'needs_evidence',turns:['Opening arguments','Witness examination','Rebuttals','Bench assessment'].map((phase,index)=>({
    id:branch*100+index,role:index===3?'Presiding Magistrate':'Complainant Counsel',text:'Recorded statement',data:{phase}}))}))};
const treeBefore = JSON.stringify(treeRun);
const tree = vm.runInContext(`decisionTreeElements(${treeBefore})`,caseContext);
const nodes = Array.from(tree).filter(item=>!item.data.source), edges = Array.from(tree).filter(item=>item.data.source);
const identities = new Set(nodes.map(item=>item.data.id));
assert.equal(identities.size,nodes.length,'Tree nodes have stable unique identities');
assert.equal(edges.filter(item=>item.data.source==='case-root').length,3,'Every alternative branches from the case');
assert.ok(edges.every(item=>identities.has(item.data.source)&&identities.has(item.data.target)),'Every edge resolves to existing nodes');
assert.deepEqual(nodes.flatMap(item=>Array.from(item.data.actionIds||[])).sort((first,second)=>first-second),
  treeRun.branches.flatMap(branch=>branch.turns.map(turn=>turn.id)).sort((first,second)=>first-second),
  'Every statement is represented once within its path and hearing stage');
assert.equal(JSON.stringify(treeRun),treeBefore,'Tree projection does not modify the saved hearing');
assert.equal(vm.runInContext('decisionTreeElements(null).length',caseContext),0);
console.log('Case decision tree: independent paths, complete stage coverage, valid edges and unchanged history pass');