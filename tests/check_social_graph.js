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
  MisofishAssets:{createIcons(){},cytoscape(options){projected=options.elements;return {on(){},destroy(){}};}}
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
const caseElement = () => ({value: '', validity: {valid: true}, addEventListener(){}, reset(){},
  replaceChildren(){}, append(){}, elements: {namedItem: () => ({value: ''})}});
const caseContext = vm.createContext({
  document: {getElementById(id){if(!caseElements.has(id))caseElements.set(id,caseElement());return caseElements.get(id);},
    querySelector: caseElement, createElement: caseElement},
  window: {addEventListener(){}}, AbortSignal: {timeout:()=>({})}, fetch:()=>new Promise(()=>{}),
  MisofishAssets: {createIcons(){}}, setTimeout(){}, clearTimeout(){}
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','web','cases.js'),'utf8'),caseContext);
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