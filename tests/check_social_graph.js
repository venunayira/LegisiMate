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