'use strict';
const $=id=>document.getElementById(id), activeStates=new Set(['preparing','running','reporting']);
const views=['room','graph','transcript','synthesis'];
let settings,current,history=[],stream,generation=0,busy=false,selectedPersona=null,graphRenderer,graphSignature='';
let paused=false,viewerIndex=-1,viewerTick=0,followLive=true,playbackTimer,speed=1,seenSpeech=new Set(),drafts=new Map();
const townMode=()=>current?.config?.platform_mode==='town';
const node=(tag,text,className)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(className)element.className=className;return element;};
const icon=(name)=>{const element=node('i');element.dataset.lucide=name;return element;};
const icons=()=>MisofishAssets.createIcons({icons:MisofishAssets.icons});
const shiftLabels={unchanged:'Held view',softened:'Softened',hardened:'Hardened',reversed:'Changed sides',not_stated:'Shift not stated'},shiftLabel=shift=>shiftLabels[shift||'not_stated'];
function error(message){$('error').textContent=message;$('error').hidden=!message;}
async function api(path,body){const response=await fetch(path,{...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),signal:AbortSignal.timeout(15000)});const result=await response.json();if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);return result;}
function showView(view){for(const name of views){$('view-'+name).hidden=name!==view;$('tab-'+name).setAttribute('aria-selected',String(name===view));$('tab-'+name).tabIndex=name===view?0:-1;}if(view==='room')ConversationRoom.wake();if(view==='graph')renderGraph();}
function speech(){return (current?.actions||[]).filter(action=>action.text&&action.kind!=='pass');}
function viewer(){
  if(paused)clearTimeout(playbackTimer);
  const town=townMode(),items=speech(),action=town?null:items[viewerIndex],ticks=current?.groups?.length||0;
  $('backlog').textContent=town?(ticks?`Tick ${viewerTick} of ${ticks}`:'Groups not formed yet'):`${Math.max(0,items.length-viewerIndex-1)} queued`;
  if(!town){
    $('speech-meta').textContent=action?`${current.agents.find(actor=>actor.id===action.agent_id)?.name||'Persona '+action.agent_id} / A${action.id} / ${action.kind==='interview'?`Final interview / ${shiftLabel(action.shift)}`:`${action.visibility||'legacy'} / ${action.engine_kind||action.kind}`}`:'No Speech Selected';
    $('selected-speech').textContent=action?.text||'No committed discussion yet.';
  }else if(!viewerTick){$('speech-meta').textContent='Town Conversations';$('selected-speech').textContent='Every tick, random groups form and talk at the same time.';}
  $('playback-pause').setAttribute('aria-pressed',String(paused));
  $('playback-pause').setAttribute('aria-label',paused?'Resume playback':'Pause playback');
  $('playback-pause').title=paused?'Resume playback':'Pause playback';
  $('playback-pause').replaceChildren(icon(paused?'play':'pause'));
  $('catch-up').setAttribute('aria-pressed',String(followLive));
  if(current)ConversationRoom.render(current,[...drafts.values()].map(draft=>draft.agent_id),action,{paused,speed,...(town?{tick:viewerTick}:{})});
  icons();
}
function schedulePlayback(){
  clearTimeout(playbackTimer);if(paused||!current)return;
  if(townMode()){
    playbackTimer=setTimeout(()=>{
      if(ConversationRoom.remaining()>50)return schedulePlayback();
      if(viewerTick<(current.groups?.length||0)){viewerTick++;viewer();schedulePlayback();}
      else if(current.status==='running')playbackTimer=setTimeout(schedulePlayback,1000);
    },Math.max(16,ConversationRoom.remaining()));
    return;
  }
  const items=speech();if(viewerIndex<items.length-1){playbackTimer=setTimeout(()=>{if(ConversationRoom.remaining()>50)return schedulePlayback();viewerIndex++;viewer();schedulePlayback();},Math.max(16,ConversationRoom.remaining()));}
}
function evidence(id){const link=node('a','A'+id,'evidence');link.href='#action-'+id;link.addEventListener('click',event=>{event.preventDefault();$('agent-filter').value='all';showView('transcript');renderFeed();requestAnimationFrame(()=>$('action-'+id)?.scrollIntoView({block:'nearest'}));});return link;}
function inspectEntity(identity){
  const graph=current?.graph,item=graph?.nodes.find(record=>record.id===identity)||graph?.edges.find(record=>record.id===identity);
  if(!item)return;
  const host=$('inspector-content');host.replaceChildren(node('span',item.kind,'status'),node('h3',item.name||item.fact),node('p',item.summary||item.fact));
  host.append(node('p',item.synthetic?'Synthetic Scenario Evidence':'Source Quotation / Model-Extracted Relation','provenance'));
  for(const span of item.evidence||[]){host.append(node('blockquote',span.quote),node('p',`${span.source_id} / characters ${span.start}-${span.end}`,'provenance'));}
  const linked=current.agents.filter(actor=>actor.profile?.entity_id===identity);
  for(const actor of linked){const button=node('button',actor.name);button.addEventListener('click',()=>selectPersona(actor.id));host.append(button);}
}
function selectPersona(id){
  selectedPersona=id;ConversationRoom.select(id);
  const actor=current?.agents.find(person=>person.id===id);if(!actor)return;
  const host=$('inspector-content');host.replaceChildren(node('span','Synthetic Persona','status'),node('h3',actor.name),node('p',actor.role,'muted'),node('p',actor.perspective));
  if(actor.profile){
    const profile=actor.profile;
    if(profile.outlook)host.append(node('p',`${profile.outlook} outlook / ${profile.openness} openness to change`,'provenance'));
    if(profile.initial_view)host.append(node('h3','Opening View'),node('p',profile.initial_view));
    for(const [key,title] of [['goal','Goal'],['background','Background'],['speaking_style','Speaking Style']])host.append(node('h3',title),node('p',profile[key]));
    for(const [key,title] of [['interests','Interests'],['beliefs','Beliefs']]){
      host.append(node('h3',title));const list=node('ul');
      for(const value of profile[key])list.append(node('li',value));host.append(list);
    }
    host.append(node('p',`${Math.round(profile.activity_level*100)}% activation / active hours ${profile.active_hours.join(', ')}`,'provenance'));
    const identity=profile.entity_id||profile.source_entity_ids[0];
    if(identity){
      const button=node('button','Source Evidence');
      button.addEventListener('click',()=>{showView('graph');inspectEntity(identity);graphRenderer?.getElementById(identity).select();});
      host.append(button);
    }
  }
  const finals=current.actions.filter(action=>action.agent_id===id&&action.kind==='interview'&&action.text);
  if(finals.length)host.append(node('h3','Final View'));
  for(const action of finals)host.append(node('p',`${shiftLabel(action.shift)} / ${action.platform||'legacy'}`,'provenance'),node('p',action.text));
  const thoughts=new Map(current.actions.filter(action=>action.agent_id===id&&action.view).map(action=>[action.round,action]));
  if(thoughts.size)host.append(node('h3','Thought Evolution'));
  for(const [tick,action] of thoughts)host.append(node('p',`After tick ${tick} / ${shiftLabel(action.shift)}`,'provenance'),node('p',action.view));
  host.append(node('h3','Committed Participation'));
  const participation=current.actions.filter(action=>action.agent_id===id&&action.text);
  host.append(node('p',`${participation.length} recorded contributions`,'muted'));
  for(const action of participation.slice(-5))host.append(evidence(action.id));
  $('agent-filter').value=String(id);renderFeed();renderRoster();viewer();
}
function renderRoster(){
  const filter=$('agent-filter').value;
  $('roster').replaceChildren();$('agent-filter').replaceChildren(new Option('All Personas','all'));
  for(const actor of current.agents){const button=node('button',undefined,'persona-button');button.append(node('strong',actor.name),node('small',[actor.role,actor.profile?.outlook].filter(Boolean).join(' / ')));button.style.setProperty('--persona-color',ConversationRoom.palette[(actor.id-1)%10]);button.setAttribute('aria-pressed',String(selectedPersona===actor.id));button.addEventListener('click',()=>selectPersona(actor.id));$('roster').append(button);$('agent-filter').append(new Option(actor.name,String(actor.id)));}
  $('agent-filter').value=[...$('agent-filter').options].some(option=>option.value===filter)?filter:'all';
}
function renderFeed(){
  if(!current)return;
  const filter=$('agent-filter').value,host=$('feed'),fragment=document.createDocumentFragment();
  const actions=current.actions.filter(action=>action.text&&(filter==='all'||String(action.agent_id)===filter));
  for(const action of actions){const item=node('article',undefined,'action');item.id='action-'+action.id;const heading=node('div',undefined,'action-head');heading.append(node('span','A'+action.id),node('strong',current.agents.find(actor=>actor.id===action.agent_id)?.name||'Persona '+action.agent_id),node('span',action.kind==='interview'?`Final interview / ${action.platform||'legacy'} / ${shiftLabel(action.shift)}`:action.platform==='town'?`Tick ${action.round} / Group ${action.data.group} / minute ${action.data.turn}`:`Tick ${action.round} / ${action.platform||'legacy'} / ${action.engine_kind||action.kind}`));if(action.visibility==='private')heading.append(node('span','Private Group','private'));item.append(heading,node('p',action.text));if(action.view)item.append(node('p',`Thinking now (${shiftLabel(action.shift)}): ${action.view}`,'provenance'));if(action.reply_to)item.append(node('span','Replies to '),evidence(action.reply_to));if(action.observed_effect_ids?.length)item.append(node('p',`${action.observed_effect_ids.length} previously observed effects`,'provenance'));item.addEventListener('click',()=>{viewerIndex=speech().findIndex(record=>record.id===action.id);if(action.platform==='town')viewerTick=action.round;paused=true;followLive=false;viewer();});fragment.append(item);}
  if(!actions.length)fragment.append(node('p','No committed speech.','muted'));host.replaceChildren(fragment);
}
function renderDecisions(){
  $('live-turns').replaceChildren();
  for(const draft of drafts.values()){
    const actor=current.agents.find(person=>person.id===draft.agent_id);
    $('live-turns').append(node('p',`${actor?.name||'Persona '+draft.agent_id} / ${draft.platform} / Deciding`,'muted'));
  }
  $('room-state').textContent=drafts.size?`${drafts.size} deciding`:townMode()?'Town Conversations':(current.version===2?'Reddit-Owned Shared Room':'Legacy Conversation Record');
}
function finalThoughts(host){
  let finals=current.actions.filter(action=>action.kind==='interview'&&action.text);
  // Town conversations update each speaker's view on every line; the latest one is their final thought.
  if(!finals.length)finals=[...new Map(current.actions.filter(action=>action.view).map(action=>[action.agent_id,{...action,text:action.view}])).values()];
  if(!finals.length)return;
  const counts={};for(const action of finals){const key=action.shift||'not_stated';counts[key]=(counts[key]||0)+1;}
  const missing=current.agents.filter(actor=>!finals.some(action=>action.agent_id===actor.id)).length;
  host.append(node('h3','Final Thoughts'),node('p',`${finals.length} final views / `+Object.entries(counts).map(([key,count])=>`${shiftLabel(key)}: ${count}`).join(' / ')+(missing?` / ${missing} personas without a final view`:''),'muted'));
  for(const actor of current.agents){
    const answers=finals.filter(action=>action.agent_id===actor.id);if(!answers.length)continue;
    const item=node('article',undefined,'final-thought');item.append(node('strong',`${actor.name} / ${actor.role}`));
    if(actor.profile?.initial_view)item.append(node('p',`Opening view: ${actor.profile.initial_view}`,'muted'));
    for(const action of answers){const line=node('p',`${shiftLabel(action.shift)}${action.platform?` (${action.platform})`:''}: ${action.text} `);line.append(evidence(action.id));item.append(line);}
    host.append(item);
  }
}
function renderReport(){
  const host=$('report'),report=current.report;host.replaceChildren();
  if(!report){host.append(node('h3',current.status==='reporting'?'Synthesis Draft':'Final Synthesis'),node('p',current.report_draft?.conclusion||current.report_draft?.summary||'No report published.','muted'));finalThoughts(host);return;}
  host.append(node('span','Final Synthesis','status'),node('h3','Conclusion'),node('p',report.conclusion||report.summary,'conclusion'));
  if(report.conclusion)host.append(node('p',report.summary));
  for(const [key,title] of [['opinion_changes','How Views Changed'],['agreements','Agreements'],['disagreements','Disagreements'],['open_questions','Open Questions']]){if(!report[key]?.length)continue;host.append(node('h3',title));const list=node('ul');for(const point of report[key])list.append(node('li',point));host.append(list);}
  finalThoughts(host);
  host.append(node('h3','Evidence'));
  for(const finding of report.findings){const item=node('article',undefined,'finding');item.append(node('p',finding.claim));for(const id of finding.action_ids)item.append(evidence(id));for(const identity of [...(finding.entity_ids||[]),...(finding.relationship_ids||[])]){const button=node('button',identity);button.addEventListener('click',()=>{showView('graph');inspectEntity(identity);});item.append(button);}host.append(item);}
  host.append(node('p',report.limitations,'limitations'));
}
function renderGraph(){
  if(!current)return;
  const kind=$('graph-kind').value,signature=current.id+kind+JSON.stringify(kind==='knowledge'?current.graph:current.actions);
  if(signature===graphSignature){graphRenderer?.resize();graphRenderer?.fit(undefined,30);return;}
  graphSignature=signature;graphRenderer?.destroy();const elements=[];
  if(kind==='knowledge'){
    for(const item of current.graph?.nodes||[])elements.push({data:{id:item.id,label:item.name,type:item.kind,synthetic:item.synthetic}});
    for(const item of current.graph?.edges||[])elements.push({data:{id:item.id,source:item.source,target:item.target,label:item.kind}});
  }else{
    for(const actor of current.agents)elements.push({data:{id:'persona-'+actor.id,label:actor.name}});
    const groups=new Map(),members=new Map(),follows=new Map();
    for(const action of current.actions){
      const data=action.data||{};
      if(action.engine_kind==='create_group'){groups.set(data.group_id,data.group_name||'Group '+data.group_id);members.set(`${data.group_id}:${action.agent_id}`,{group:data.group_id,actor:action.agent_id});}
      if(action.engine_kind==='join_group')members.set(`${data.group_id}:${action.agent_id}`,{group:data.group_id,actor:action.agent_id});
      if(action.engine_kind==='leave_group')members.delete(`${data.group_id}:${action.agent_id}`);
      if(data.followee_id!==undefined){
        const identity=`${action.platform}:${action.agent_id}:${data.followee_id}`;
        if(action.engine_kind==='follow')follows.set(identity,{data:{id:action.effect_id,source:'persona-'+action.agent_id,target:'persona-'+(data.followee_id+1),label:`${action.platform} follows`}});
        if(action.engine_kind==='unfollow')follows.delete(identity);
      }
    }
    elements.push(...follows.values());
    const met=new Map();
    for(const entry of current.groups||[])for(const group of entry.groups)group.members.forEach((first,index)=>{for(const second of group.members.slice(index+1)){const pair=[first,second].sort((a,b)=>a-b).join('-');met.set(pair,(met.get(pair)||0)+1);}});
    for(const [pair,count] of met){const [first,second]=pair.split('-');elements.push({data:{id:'met-'+pair,source:'persona-'+first,target:'persona-'+second,label:`talked ${count}x`}});}
    for(const [id,name] of groups)elements.push({data:{id:'group-'+id,label:name}});
    for(const [id,member] of members)if(groups.has(member.group))elements.push({data:{id:'membership-'+id,source:'persona-'+member.actor,target:'group-'+member.group,label:'member'}});
  }
  $('graph-count').textContent=`${elements.filter(item=>!item.data.source).length} nodes / ${elements.filter(item=>item.data.source).length} links`;
  graphRenderer=MisofishAssets.cytoscape({container:$('graph-canvas'),elements,style:[{selector:'node',style:{'background-color':'#14705e','label':'data(label)','font-family':'IBM Plex Sans','font-size':11,'color':'#202d32','text-valign':'bottom','text-margin-y':8,'width':26,'height':26}},{selector:'edge',style:{'width':1.4,'line-color':'#9aafb4','target-arrow-color':'#9aafb4','target-arrow-shape':'triangle','curve-style':'bezier','label':'data(label)','font-size':9,'color':'#54676d','text-background-color':'#f5f8f8','text-background-opacity':1,'text-background-padding':'3px'}},{selector:':selected',style:{'background-color':'#bd503e','line-color':'#bd503e'}}],layout:{name:'cose',animate:false,randomize:false,nodeRepulsion:()=>500000,padding:50},minZoom:.2,maxZoom:4});
  graphRenderer.on('tap','node,edge',event=>{const id=event.target.id();if(id.startsWith('persona-'))selectPersona(Number(id.slice(8)));else if(kind==='knowledge')inspectEntity(id);else $('inspector-content').replaceChildren(node('h3',event.target.data('label')),node('p','Simulation Membership','provenance'));});
  $('graph-list').replaceChildren();for(const item of elements.filter(element=>!element.data.source)){const button=node('button',item.data.label);button.addEventListener('click',()=>{graphRenderer.elements().unselect();graphRenderer.getElementById(item.data.id).select();if(kind==='knowledge')inspectEntity(item.data.id);else if(item.data.id.startsWith('persona-'))selectPersona(Number(item.data.id.slice(8)));});$('graph-list').append(button);}
}
function controls(){const active=history.some(run=>activeStates.has(run.status))||activeStates.has(current?.status);$('prepare').disabled=!settings?.configured||active||busy;$('start').hidden=current?.status!=='ready';$('start').disabled=busy||active;$('cancel').hidden=!activeStates.has(current?.status);$('cancel').disabled=busy;$('export').hidden=!current?.actions.length;if(current)$('export').href=`/api/runs/${current.id}/export`;}
function renderRun(run){
  current=run;
  $('status').textContent=`${run.status}${run.config.platform_mode==='town'?' / Town':run.version===2?' / OASIS':' / Legacy'}`;
  $('run-title').textContent=run.config.scenario;
  $('agent-metric').textContent=run.agents.length||run.config.agent_count;
  $('round-metric').textContent=`${run.round} / ${run.config.rounds} ticks`;
  $('call-metric').textContent=`${run.model_calls||0} / ${run.config.model_call_budget||'legacy'} calls`;
  $('token-metric').textContent=`${((run.usage?.input_tokens||0)+(run.usage?.output_tokens||0)).toLocaleString()} reported tokens`;
  $('progress').max=run.config.rounds;$('progress').value=run.round;
  $('run-error').textContent=run.error||'';
  $('room-state').textContent=townMode()?'Town Conversations':current.version===2?'Reddit-Owned Shared Room':'Legacy Conversation Record';
  renderRoster();renderFeed();renderReport();viewer();
  if(!$('view-graph').hidden)renderGraph();
  controls();
}
async function refreshHistory(){history=await api('/api/runs');$('history').replaceChildren();for(const run of history){const button=node('button',undefined,'history-item');button.setAttribute('aria-pressed',String(current?.id===run.id));button.append(node('strong',run.config.scenario),node('small',`${run.status} / ${run.config.agent_count} personas / ${run.round}/${run.config.rounds}`));button.addEventListener('click',()=>selectRun(run.id));$('history').append(button);}controls();}
async function selectRun(id){
  stream?.close();clearTimeout(playbackTimer);const ticket=++generation;graphSignature='';selectedPersona=null;drafts.clear();seenSpeech.clear();paused=false;followLive=true;ConversationRoom.reset();
  try{
    const run=await api(`/api/runs/${id}`);if(ticket!==generation)return;
    viewerIndex=Math.max(-1,run.actions.filter(action=>action.text&&action.kind!=='pass').length-1);
    viewerTick=run.groups?.length||0;
    renderRun(run);showView(run.report?'synthesis':'room');await refreshHistory();
    if(ticket!==generation||!activeStates.has(run.status))return;
    let cursor=run.event_cursor||0;stream=new EventSource(`/api/runs/${id}/events?after=${cursor}`);
    stream.addEventListener('update',event=>{
      if(ticket!==generation)return;const update=JSON.parse(event.data);if(update.id<=cursor)return;cursor=update.id;const data=update.data;
      if(update.kind==='turn_complete'&&!current.actions.some(action=>action.id===data.action.id)){current.actions.push(data.action);if(!paused&&viewerIndex<0)viewerIndex=0;}
      if(update.kind==='groups_formed'){current.groups=[...(current.groups||[]),data];if(!viewerTick)viewerTick=data.tick;}
      if(update.kind==='state'){if(data.status)current.status=data.status;if(data.agents)current.agents=data.agents;if(data.room)current.room=data.room;if(data.status==='ready')api(`/api/runs/${id}`).then(snapshot=>{if(ticket===generation)renderRun(snapshot);}).catch(exception=>error(exception.message));}
      if(update.kind==='tick_complete'&&data.successful)current.round=data.tick;
      if(update.kind==='worker_usage')current.model_calls=(current.model_calls||0)- (current.worker_calls||0)+data.model_calls,current.worker_calls=data.model_calls;
      if(update.kind==='decision_start')drafts.set(`${data.platform}:${data.agent_id}`,data);
      if(update.kind==='decision_complete'||update.kind==='decision_error')drafts.delete(`${data.platform}:${data.agent_id}`);
      if(update.kind==='graph_progress')$('status').textContent=`Graph / ${data.chunk} of ${data.chunks}`;
      if(data.usage)current.usage=data.usage;
      if(update.kind==='report_start')current.status='reporting';
      if(update.kind==='report_delta')current.report_draft={...current.report_draft,...data};
      if(update.kind==='report_complete'){current.report=data.report;current.report_draft={};}
      if(update.kind==='terminal'){current.status=data.status;current.error=data.error;current.report_draft={};drafts.clear();}
      current.event_cursor=cursor;renderRun(current);renderDecisions();schedulePlayback();
    });
    stream.addEventListener('end',async()=>{stream.close();try{const snapshot=await api(`/api/runs/${id}`);if(ticket===generation){renderRun(snapshot);await refreshHistory();}}catch(exception){error(exception.message);}});
    stream.onerror=()=>{if(ticket===generation)$('room-state').textContent='Reconnecting';};
  }catch(exception){error(exception.message);}
}
async function mutation(path,body){busy=true;error('');controls();try{const run=await api(path,body);if(run.id)await selectRun(run.id);return run;}catch(exception){error(exception.message);}finally{busy=false;controls();}}
$('scenario-form').addEventListener('submit',event=>{event.preventDefault();if(!$('scenario-form').reportValidity())return;mutation('/api/runs',{scenario:$('scenario').value,source:$('source').value,agent_count:Number($('agents').value),rounds:Number($('rounds').value),population_mode:$('population-mode').value,platform_mode:$('platform-mode').value,conversation_minutes:Number($('conversation-minutes').value),model_call_budget:Number($('call-budget').value),minutes_per_round:Number($('minutes').value),start_hour:Number($('hour').value),seed:Number($('seed').value),readable_dwell:Number($('dwell').value)});});
$('file').addEventListener('change',async()=>{try{const file=$('file').files[0];if(!file)return;if(file.size>80000)throw new Error('Source file exceeds the import limit.');const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(text.length>20000)throw new Error('Source exceeds 20,000 characters.');$('source').value=text;}catch(exception){error(exception.message);}});
$('start').addEventListener('click',()=>mutation(`/api/runs/${current.id}/start`,{}));
$('cancel').addEventListener('click',async()=>{const result=await mutation(`/api/runs/${current.id}/cancel`,{});if(result)$('run-error').textContent=result.message;});
$('refresh').addEventListener('click',async()=>{try{await refreshHistory();if(current)await selectRun(current.id);}catch(exception){error(exception.message);}});
$('agent-filter').addEventListener('change',renderFeed);$('graph-kind').addEventListener('change',()=>{graphSignature='';renderGraph();});
window.addEventListener('persona-select',event=>selectPersona(event.detail));
window.addEventListener('speech-start',event=>{const action=event.detail,actor=current?.agents.find(person=>person.id===action.agent_id);$('speech-meta').textContent=`${actor?.name||'Persona '+action.agent_id} / Tick ${action.round} / Group ${action.data.group} / minute ${action.data.turn}`;$('selected-speech').textContent=action.text;});
$('pause-motion').addEventListener('click',()=>{const stopped=ConversationRoom.pause();$('pause-motion').setAttribute('aria-pressed',String(stopped));});
$('playback-pause').addEventListener('click',()=>{paused=!paused;followLive=false;viewer();schedulePlayback();});
$('playback-step').addEventListener('click',()=>{paused=true;followLive=false;if(townMode())viewerTick=Math.min(viewerTick+1,current.groups?.length||0);else viewerIndex=Math.min(viewerIndex+1,speech().length-1);clearTimeout(playbackTimer);viewer();});
$('catch-up').addEventListener('click',()=>{paused=false;followLive=true;viewerIndex=speech().length-1;viewerTick=current?.groups?.length||0;viewer();schedulePlayback();});
$('playback-speed').addEventListener('change',()=>{speed=Number($('playback-speed').value);viewer();schedulePlayback();});
$('replay').addEventListener('click',()=>{ConversationRoom.restartSpeech();viewerIndex=speech().length?0:-1;viewerTick=current?.groups?.length?1:0;paused=false;followLive=false;viewer();schedulePlayback();});
for(const name of views){$('tab-'+name).addEventListener('click',()=>showView(name));$('tab-'+name).addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const index=event.key==='Home'?0:event.key==='End'?3:(views.indexOf(name)+(event.key==='ArrowRight'?1:3))%4;showView(views[index]);$('tab-'+views[index]).focus();});}
async function initialize(){icons();if(matchMedia('(max-width:700px)').matches)$('experiment-settings').open=false;try{settings=await api('/api/config');$('model-name').textContent=settings.model;$('setup').hidden=settings.configured;$('agents').max=settings.max_agents;$('agents').value=settings.default_agents||10;$('population-limit').textContent=`Default: ${settings.default_agents||10} / Deployment Ceiling: ${settings.max_agents}`;await refreshHistory();const run=history.find(item=>activeStates.has(item.status))||history[0];if(run)await selectRun(run.id);}catch(exception){error(exception.message);}controls();}
initialize();