'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
let now = 0, frames = [];
const reduced={matches:false};
const canvas2d=new Proxy({},{get:(target,key)=>key in target?target[key]:()=>{}});
function element() {
  return {children:[],style:{setProperty(name,value){this[name]=value;}},hidden:false,clientWidth:800,clientHeight:450,
    offsetWidth:280,offsetHeight:150,scrollHeight:110,textContent:'',attributes:{},classList:{toggle(){}},
    append(...children){this.children.push(...children);},prepend(child){this.children.unshift(child);},
    addEventListener(){},setAttribute(name,value){this.attributes[name]=value;},remove(){},getContext:()=>canvas2d,
    getBoundingClientRect(){return {left:0,right:280,top:0,bottom:150,width:280,height:150};}};
}
const host=element(),labels=element();
const context=vm.createContext({
  window:{dispatchEvent(){}},document:{getElementById:id=>id==='room-lanes'?host:labels,createElement:element},
  performance:{now:()=>now},devicePixelRatio:1,matchMedia:()=>reduced,requestAnimationFrame:frame=>frames.push(frame),
  ResizeObserver:class {observe(){}}
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','web','room.js'),'utf8'),context);
const room=context.window.ConversationRoom;
const advance=milliseconds=>{now+=milliseconds;const pending=frames;frames=[];for(const frame of pending)frame(now);};
const post={id:1,agent_id:2,kind:'post',text:'Resorts should publish their water use.'};
const speech={id:2,agent_id:1,kind:'reply',reply_to:1,text:'One two three four five six seven eight nine ten.'};
const run={id:'fixture',agents:[{id:1,name:'Mira',role:'Nurse'},{id:2,name:'Jonas',role:'Hotel chef'}],actions:[post,speech]};
const find=(root,name)=>root.children.find(child=>child.className===name);
room.render(run,[],speech,{paused:false,speed:1});
const bubble=find(host,'room-bubble'),body=find(bubble,'room-bubble-text');
const jonas=labels.children[1],speakerX=()=>parseFloat(bubble.style.left)+parseFloat(bubble.style['--tail-left']);
advance(16);
assert.equal(bubble.hidden,true,'The speaker walks to the listener before speaking');
assert.ok(room.remaining()>=room.duration(speech.text),'Playback must wait for the walk and the full reveal');
let walked=0;
while(bubble.hidden&&walked<400){advance(50);walked++;}
assert.ok(walked>10&&!bubble.hidden,'Replying is shown as walking over to the listener');
assert.ok(Math.abs(speakerX()-parseFloat(jonas.style.left))<60,'The speaker stands beside the person they reply to');
assert.ok(bubble.attributes['aria-label'].includes('to Jonas'));
assert.ok(body.textContent.length>0&&body.textContent.length<speech.text.length);
advance(1200);
const partial=body.textContent;
assert.ok(partial.length>4&&partial.length<speech.text.length);
room.render(run,[],speech,{paused:true,speed:1});
advance(1800);
assert.equal(body.textContent,partial);
room.render(run,[],speech,{paused:false,speed:2});
advance(2000);
assert.equal(body.textContent,speech.text);
room.restartSpeech();
room.render(run,[],speech,{paused:false,speed:1});
advance(16);
assert.ok(body.textContent.length<speech.text.length);
room.render(run,[2],{...post,kind:'interview',text:'A different thought.'},{paused:false,speed:1});
assert.notEqual(body.textContent,speech.text);
assert.ok(bubble.attributes['aria-label'].includes('Jonas, final interview'));
room.render(run,[],null);
assert.equal(bubble.hidden,true);
reduced.matches=true;
room.render(run,[],speech,{paused:false,speed:1});
advance(16);
assert.equal(body.textContent,speech.text);
reduced.matches=false;
const started=[];
context.CustomEvent=class {constructor(type,init){this.type=type;this.detail=init.detail;}};
context.window.dispatchEvent=event=>started.push(event.detail);
const say=(id,agent,group,turn,text)=>({id,agent_id:agent,platform:'town',kind:'post',engine_kind:'say',round:1,text,data:{group,turn}});
const town={id:'town',status:'running',round:0,agents:[1,2,3,4].map(id=>({id,name:`P${id}`,role:'Resident'})),
  groups:[{tick:1,groups:[{id:1,members:[1,2]},{id:2,members:[3,4]}]}],
  actions:[say(1,1,1,1,'Water first.'),say(2,3,2,1,'Jobs matter too.'),say(3,2,1,2,'Both can be true.')]};
room.render(town,[],null,{paused:false,speed:1,tick:1});
const talking=()=>host.children.filter(child=>child.className==='room-bubble'&&!child.hidden);
let gathering=0;
while(talking().length<2&&gathering<400){advance(50);gathering++;}
assert.equal(talking().length,2,'Every group shows its own speaker at the same time');
assert.ok(gathering>5,'People walk to their randomly assigned groups before talking');
const lefts=talking().map(item=>parseFloat(item.style.left)).sort((first,second)=>first-second);
assert.ok(lefts[1]-lefts[0]>=280,'Simultaneous group bubbles do not overlap');
assert.deepEqual(started.map(item=>item.id).sort(),[1,2]);
assert.ok(room.remaining()>0);
advance(5100);advance(16);
assert.ok(started.some(item=>item.id===3),'A group moves on to its next line by itself');
advance(12000);advance(16);
assert.equal(room.remaining(),1000,'A live tick waits for more lines');
Object.assign(town,{round:1,status:'completed'});
room.render(town,[],null,{paused:false,speed:1,tick:1});
assert.equal(room.remaining(),0,'A finished tick lets playback move to the next tick');
const drawnLabels=[];
canvas2d.fillText=text=>drawnLabels.push(text);
const courtSpeech={id:1,agent_id:3,platform:'court',kind:'say',round:1,text:'The notice date needs documentary confirmation.',data:{stage:'Notice and service'}};
const court={id:'casework-court',config:{platform_mode:'court'},agents:[
  {id:1,name:'Magistrate',role:'Presiding Magistrate'},
  {id:2,name:'Complainant counsel',role:'Complainant Counsel'},
  {id:3,name:'Defence counsel',role:'Respondent Defense Counsel'}],actions:[courtSpeech]};
room.render(court,[],courtSpeech,{paused:false,speed:1});
room.wake();advance(16);
assert.equal(talking().length,1,'Court speakers begin at their fixed seats without a stalled walking phase');
assert.ok(find(talking()[0],'room-bubble-text').textContent.length>0);
assert.ok(!drawnLabels.includes('JURY BOX'),'The magistrate workflow does not display a jury box');
drawnLabels.length=0;
room.render({...court,id:'legacy-jury',agents:[...court.agents,{id:4,name:'Assessor',role:'Jury Member'}]},[],null);
room.wake();
assert.ok(drawnLabels.includes('JURY BOX'),'Saved legacy casts retain their jury layout');
console.log('Town speech: walk-to-listener, gradual reveal, pause/resume, speed, replay, final interview, reduced motion and parallel groups pass');