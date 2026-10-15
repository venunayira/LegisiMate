'use strict';
window.ConversationRoom = (() => {
  const palette = ['#14705e','#c75d4d','#557fb5','#a7852f','#737fa1','#408a9f','#bc778b','#6a914d','#cd814c','#435d72'];
  const skins = ['#f2c9a6','#d9a27c','#b07a57','#86583f'], hairs = ['#30302e','#6b4a2f','#c4954a','#1f2d3d','#8b3d2f','#d9d4c9'];
  const host = document.getElementById('room-lanes'), labels = document.getElementById('room-labels');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const canvas = document.createElement('canvas'), ground = document.createElement('canvas'), context = canvas.getContext('2d');
  canvas.setAttribute('aria-hidden','true');host.prepend(canvas);
  const pool=[],bubble=()=>{
    if(pool.length)return pool.pop();
    const element=document.createElement('div'),name=document.createElement('strong'),text=document.createElement('div');
    element.className='room-bubble';name.className='room-bubble-name';text.className='room-bubble-text';
    element.hidden=true;element.setAttribute('role','note');text.setAttribute('aria-hidden','true');
    text.tabIndex=0;element.append(name,text);host.append(element);
    return {element,name,text};
  };
  let tracks=[],town=null,townDone=true,playing={paused:false,speed:1},cast=new Map(),signature='',selected=null,paused=false,deciding=new Set(),layout=null,last=0;
  const words=text=>text.match(/\s*\S+\s*/gu)||[];
  const duration=text=>Math.max(5000,words(text).length*400+1800);
  const hash=(x,y)=>(Math.imul(x+101,73856093)^Math.imul(y+211,19349663))>>>0;
  const listenerOf=(speech,actions)=>{
    const parent=speech.reply_to&&actions.find(action=>action.id===speech.reply_to);
    return parent&&parent.agent_id!==speech.agent_id?cast.get(parent.agent_id):null;
  };
  const whereOf=(speech,actions)=>speech.platform==='town'?`Group ${speech.data?.group}`:speech.kind==='interview'?'final interview'
    :listenerOf(speech,actions)?`to ${listenerOf(speech,actions).actor.name}`:speech.engine_kind==='send_to_group'?'in the Shared Room':'on the Public Board';
  function open(key,items,extra){
    const track={key,bubble:bubble(),items,index:0,elapsed:0,updated:performance.now(),visible:-1,arrived:false,labelled:null,...extra};
    track.bubble.element.classList.toggle('compact',Boolean(town));
    return track;
  }
  function close(){for(const track of tracks){track.bubble.element.hidden=true;pool.push(track.bubble);}tracks=[];}
  function credit(track){
    const now=performance.now();
    // Each line is revealed only once its speakers have gathered or walked over.
    if(!playing.paused&&track.arrived)track.elapsed+=(now-track.updated)*playing.speed;
    track.updated=now;
  }
  function reveal(track){
    let speech=track.items[track.index];
    if(town&&speech&&track.labelled===speech.id&&track.elapsed>=duration(speech.text)&&track.index<track.items.length-1)speech=track.items[++track.index];
    if(!speech){track.bubble.element.hidden=true;return;}
    if(track.labelled!==speech.id){
      const speaker=cast.get(speech.agent_id).actor,where=whereOf(speech,track.actions);
      track.bubble.name.textContent=`${speaker.name}${speaker.role?` / ${speaker.role}`:''} / ${where}`;
      track.bubble.element.setAttribute('aria-label',`${speaker.name}, ${where}: ${speech.text}`);
      Object.assign(track,{labelled:speech.id,elapsed:0,visible:-1,updated:performance.now()});
      if(town)window.dispatchEvent(new CustomEvent('speech-start',{detail:speech}));
    }
    credit(track);
    const parts=words(speech.text);
    const count=!track.arrived?0:reduced.matches?parts.length:Math.min(parts.length,1+Math.floor(track.elapsed/400));
    track.bubble.element.hidden=!track.arrived;
    if(count!==track.visible){
      track.visible=count;track.bubble.text.textContent=parts.slice(0,count).join('');
      track.bubble.text.scrollTop=track.bubble.text.scrollHeight;
    }
  }
  function plan(){
    const width=host.clientWidth,height=host.clientHeight;
    // Tiles shrink for large populations so every persona still fits on one map.
    const tile=Math.max(8,Math.min(Math.floor(width/(width<600?22:34)),Math.floor(Math.sqrt(width*height/(Math.max(cast.size,1)*6)))));
    const columns=Math.ceil(width/tile),rows=Math.ceil(height/tile),center={x:Math.floor(columns/2),y:Math.floor(rows*.58)};
    return {width,height,tile,columns,rows,center,hall:{x:center.x-4,y:1,w:8,h:4},board:{x:center.x+4.5,y:center.y-2.4}};
  }
  function arrange(){
    const {tile,columns,rows,center,hall}=layout,count=cast.size;
    const top=hall.y+hall.h+2,across=Math.ceil(Math.sqrt(count*(columns-4)/Math.max(1,rows-top-1))),down=Math.ceil(count/across);
    [...cast.values()].forEach((item,index)=>{
      const angle=Math.PI*(1.7+1.6*(index+.5)/count);
      item.home=count<=30?{x:(center.x+Math.cos(angle)*columns*.38)*tile,y:(center.y+Math.sin(angle)*Math.max(4,rows*.3))*tile}
        :{x:(2+(index%across+.5)*(columns-4)/across)*tile,y:(top+(Math.floor(index/across)+.5)*(rows-top-1)/down)*tile};
    });
  }
  function paint(){
    const {width,height,tile,columns,rows,center,hall,board}=layout,ratio=Math.min(devicePixelRatio||1,2),draw=ground.getContext('2d');
    canvas.width=ground.width=Math.round(width*ratio);canvas.height=ground.height=Math.round(height*ratio);
    draw.setTransform(ratio,0,0,ratio,0,0);
    const block=(x,y,w,h,fill)=>{draw.fillStyle=fill;draw.fillRect(Math.round(x*tile),Math.round(y*tile),Math.ceil(w*tile),Math.ceil(h*tile));};
    const disc=(x,y,radius,fill)=>{draw.fillStyle=fill;draw.beginPath();draw.arc(x*tile,y*tile,radius*tile,0,Math.PI*2);draw.fill();};
    const sign=(value,x,y,size,fill)=>{draw.fillStyle=fill;draw.font=`600 ${size}px "IBM Plex Sans", sans-serif`;draw.textAlign='center';draw.textBaseline='middle';draw.fillText(value,x*tile,y*tile);};
    block(0,0,columns,rows,'#94cf74');
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const noise=hash(x,y);
      if(noise%5===0){block(x+.2,y+.55,.1,.25,'#7fbd5f');block(x+.38,y+.45,.1,.35,'#7fbd5f');}
      else if(noise%37===0)block(x+.45,y+.4,.16,.16,['#f7f4ea','#e2675a','#f1c84b'][noise%3]);
    }
    block(center.x-1,hall.y+hall.h,2,rows,'#e5d2a2');block(0,center.y-1,columns,2,'#e5d2a2');
    for(let x=0;x<8;x++)for(let y=0;y<6;y++)block(center.x-4+x,center.y-3+y,1,1,(x+y)%2?'#d4ccb9':'#ddd6c6');
    disc(center.x,center.y,1.6,'#bdb5a2');disc(center.x,center.y,1.25,'#64b9e6');
    block(center.x-.2,center.y-.7,.4,.9,'#a39b88');disc(center.x,center.y-.85,.3,'#cdeefb');
    block(hall.x,hall.y+1.4,hall.w,hall.h-1.4,'#efe3c8');block(hall.x-.3,hall.y,hall.w+.6,1.6,'#b9574a');
    for(let stripe=1;stripe<4;stripe++)block(hall.x-.3,hall.y+stripe*.4,hall.w+.6,.06,'#a14b40');
    for(const offset of [.7,hall.w-2.1])block(hall.x+offset,hall.y+2.1,1.4,.9,'#8fc8e6');
    block(center.x-.6,hall.y+hall.h-1.5,1.2,1.5,'#7a5432');
    sign('Shared Room',center.x,hall.y+.8,Math.max(9,tile*.42),'#fff8ee');
    block(board.x+.25,board.y+1.2,.15,1,'#7a5432');block(board.x+2.2,board.y+1.2,.15,1,'#7a5432');
    block(board.x,board.y,2.6,1.4,'#b88b55');block(board.x+.1,board.y+.1,2.4,1.2,'#d8b47c');
    for(const [x,y] of [[.25,.2],[1.05,.3],[1.75,.15]])block(board.x+x,board.y+y,.55,.7,'#fffdf6');
    sign('Public Board',board.x+1.3,board.y-.4,Math.max(8,tile*.36),'#2f4a35');
    const homes=cast.size<=30?[...cast.values()].map(item=>({x:item.home.x/tile,y:item.home.y/tile})):[];
    const clear=(x,y)=>!(Math.abs(x-center.x)<2.5||Math.abs(y-center.y)<2.5||(x>hall.x-2&&x<hall.x+hall.w+1&&y<hall.y+hall.h+2)
      ||(x>board.x-1&&x<board.x+3.5&&y>board.y-1.5&&y<board.y+3.5)||homes.some(home=>Math.abs(home.x-x)<2.4&&y>home.y-4&&y<home.y+1.5));
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const edge=x===0||y===0||x===columns-1||y===rows-1;
      if((edge?hash(x,y)%3===0:homes.length&&hash(x,y)%47===0)&&clear(x+.5,y+.5)){
        block(x+.4,y+.45,.2,.45,'#7a5432');disc(x+.5,y+.3,.5,'#4c944c');disc(x+.38,y+.18,.2,'#66b05e');
      }
    }
    if(cast.size<=16)for(const item of cast.values()){
      const x=item.home.x/tile,y=item.home.y/tile;
      block(x-1,y-2.55,2,1.65,'#f3ead7');block(x-1.2,y-3.25,2.4,.85,item.color);block(x-1.2,y-2.45,2.4,.1,'rgba(32,45,50,.2)');
      block(x-.25,y-1.75,.5,.85,'#7a5432');block(x+.35,y-2.25,.45,.45,'#8fc8e6');
    }
  }
  function destination(speech,actions){
    const speaker=cast.get(speech.agent_id),listener=listenerOf(speech,actions);
    if(!layout)return {listener};
    const {tile,center,hall,board,width}=layout,slot=(speech.agent_id%7-3)*tile;
    if(speech.kind==='interview')return {x:speaker.home.x,y:speaker.home.y,facing:'down'};
    if(listener)return {x:Math.max(tile,Math.min(width-tile,listener.home.x+(speaker.home.x<listener.home.x?-1.3:1.3)*tile)),y:listener.home.y,listener};
    if(speech.engine_kind==='send_to_group')return {x:center.x*tile+slot,y:(hall.y+hall.h+1.4)*tile,facing:'up'};
    return {x:(board.x+1.3)*tile+slot*.5,y:(board.y+2.9)*tile,facing:'up'};
  }
  function slots(){
    for(const item of cast.values())item.slot=null;
    if(!town||!layout)return;
    const {tile,width,height,hall}=layout,top=(hall.y+hall.h+.5)*tile,count=town.groups.length;
    const across=Math.max(1,Math.min(count,width<600?2:Math.round(Math.sqrt(count*width/Math.max(1,height-top)))));
    const down=Math.ceil(count/across),cellWidth=width/across,cellHeight=(height-top)/Math.max(1,down);
    town.groups.forEach((group,index)=>{
      group.cell={x:(index%across)*cellWidth,y:top+Math.floor(index/across)*cellHeight,w:cellWidth,h:cellHeight};
      const center={x:group.cell.x+cellWidth/2,y:group.cell.y+cellHeight*.76};
      const radius=Math.min(cellWidth*.3,cellHeight*.24,tile*(.8+.2*group.members.length));
      group.members.forEach((id,position)=>{
        const item=cast.get(id),angle=Math.PI*2*position/group.members.length-Math.PI/2;
        if(!item)return;
        item.slot={x:center.x+Math.cos(angle)*radius,y:center.y+Math.sin(angle)*radius*.7};
        item.face=Math.abs(Math.cos(angle))>.5?(Math.cos(angle)>0?'left':'right'):(Math.sin(angle)>0?'up':'down');
      });
    });
  }
  function resize(){
    if(!host.clientWidth||!host.clientHeight)return;
    layout=plan();arrange();slots();
    for(const item of cast.values()){const spot=item.slot||item.home;item.x=spot.x;item.y=spot.y;}
    const track=tracks[0],speech=track?.items[0];
    if(track&&!town&&speech){
      track.target=destination(speech,track.actions);
      const speaker=cast.get(speech.agent_id);
      if(track.arrived&&speaker&&track.target.x!==undefined){speaker.x=track.target.x;speaker.y=track.target.y;}
    }
    paint();
  }
  function choose(id){selected=id;window.dispatchEvent(new CustomEvent('persona-select',{detail:id}));}
  function person(actor,index){
    const color=palette[index%palette.length],label=document.createElement('button'),name=document.createElement('span');
    label.className='room-label';label.type='button';label.style.setProperty('--persona-color',color);
    name.textContent=actor.name;label.append(name);
    if(actor.role){const role=document.createElement('small');role.textContent=actor.role;label.append(role);}
    label.setAttribute('aria-label',`Inspect ${actor.name}${actor.role?`, ${actor.role}`:''}`);
    label.addEventListener('click',()=>choose(actor.id));labels.append(label);
    return {id:actor.id,actor,color,label,x:0,y:0,home:{x:0,y:0},dir:'down',moving:false};
  }
  function render(run,thinking=[],speech=null,playback={}){
    const next=`${run.id}:${run.agents.map(actor=>actor.id).join(',')}`;
    if(next!==signature){
      signature=next;close();town=null;
      for(const item of cast.values())item.label.remove();
      cast=new Map(run.agents.map((actor,index)=>[actor.id,person(actor,index)]));
      resize();
    }
    deciding=new Set(thinking);
    tracks.forEach(credit);
    playing={paused:Boolean(playback.paused),speed:playback.speed||1};
    const actions=run.actions||[];
    if(playback.tick!==undefined){
      const key=`${run.id}:${playback.tick}`;
      if(town?.key!==key){
        close();
        town={key,groups:((run.groups||[]).find(entry=>entry.tick===playback.tick)?.groups||[]).map(group=>({...group}))};
        slots();
        tracks=town.groups.map(group=>open(`${key}:${group.id}`,[],{group}));
      }
      townDone=run.round>=playback.tick||run.status!=='running';
      for(const track of tracks){
        track.actions=actions;
        track.items=actions.filter(action=>action.platform==='town'&&action.round===playback.tick&&action.data?.group===track.group.id)
          .sort((first,second)=>first.data.turn-second.data.turn);
      }
    }else{
      if(town){close();town=null;slots();}
      const key=speech&&cast.has(speech.agent_id)?`${run.id}:${speech.effect_id||speech.id}:${speech.text}`:null;
      if(tracks[0]?.key!==key){
        close();
        if(key)tracks=[open(key,[speech],{actions,target:destination(speech,actions)})];
      }
    }
    tracks.forEach(reveal);
    for(const [id,item] of cast)item.label.setAttribute('aria-pressed',String(id===selected));
  }
  function gathered(track){
    if(track.group)return track.group.members.every(id=>{const item=cast.get(id);return !item?.slot||Math.hypot(item.x-item.slot.x,item.y-item.slot.y)<=.5;});
    const speaker=cast.get(track.items[0].agent_id),target=track.target||{};
    if(target.x!==undefined&&Math.hypot(speaker.x-target.x,speaker.y-target.y)>.5)return false;
    if(target.listener){speaker.dir=target.listener.x<speaker.x?'left':'right';target.listener.dir=speaker.x<target.listener.x?'left':'right';}
    else if(target.facing)speaker.dir=target.facing;
    return true;
  }
  function sprite(item,time){
    const unit=layout.tile/16,x=item.x,y=item.y,swing=item.moving?(Math.floor(time/150)%2?1:-1):0;
    const part=(dx,dy,w,h,fill)=>{context.fillStyle=fill;context.fillRect(Math.round(x+dx*unit),Math.round(y+dy*unit),Math.ceil(w*unit),Math.ceil(h*unit));};
    const skin=skins[item.id%skins.length],hair=hairs[item.id%hairs.length];
    context.fillStyle='rgba(32,45,50,.22)';context.beginPath();context.ellipse(x,y,6*unit,2*unit,0,0,Math.PI*2);context.fill();
    if(item.id===selected){context.strokeStyle='#f08368';context.lineWidth=Math.max(1.5,unit);context.beginPath();context.ellipse(x,y,8*unit,3*unit,0,0,Math.PI*2);context.stroke();}
    part(-4,-5,3,5-Math.max(0,swing),'#3d4b5c');part(1,-5,3,5-Math.max(0,-swing),'#3d4b5c');
    part(-7,-11+Math.max(0,-swing),2,5,skin);part(5,-11+Math.max(0,swing),2,5,skin);
    part(-5,-11,10,7,item.color);part(-5,-5,10,1,'rgba(32,45,50,.25)');
    part(-4,-18,8,7,skin);
    if(item.dir==='up')part(-4,-19,8,6,hair);
    else{
      part(-4,-19,8,3,hair);
      if(item.dir==='left'){part(1,-17,3,3,hair);part(-3,-14,1,2,'#202d32');}
      else if(item.dir==='right'){part(-4,-17,3,3,hair);part(2,-14,1,2,'#202d32');}
      else{part(-4,-17,1,2,hair);part(3,-17,1,2,hair);part(-2,-14,1,2,'#202d32');part(1,-14,1,2,'#202d32');}
    }
    if(deciding.has(item.id)){
      context.fillStyle='#fff';context.beginPath();context.roundRect(x+3*unit,y-28*unit,13*unit,7*unit,2*unit);context.fill();
      for(let dot=0;dot<3;dot++)part(5+dot*3.5,-25.5,2,2,'#54676d');
    }
  }
  function place(){
    const unit=layout.tile/16,placed=[],speaking=new Set();
    for(const track of tracks){
      const speech=track.items[track.index],speaker=speech&&cast.get(speech.agent_id),element=track.bubble.element;
      if(!speaker||element.hidden)continue;
      speaking.add(speaker.id);
      const cell=track.group?.cell||{x:0,y:0,w:layout.width,h:layout.height};
      if(track.group)element.style.width=`${Math.max(150,Math.min(300,cell.w-12))}px`;
      // A group's bubble sits above the whole circle so it never hides the listeners.
      const head=(track.group?Math.min(...track.group.members.map(id=>cast.get(id)?.y??speaker.y)):speaker.y)-21*unit,width=element.offsetWidth,height=element.offsetHeight;
      const left=Math.max(8,Math.min(layout.width-width-8,Math.max(cell.x+6,Math.min(cell.x+cell.w-width-6,speaker.x-width/2))));
      // Group bubbles stay inside their group's cell so simultaneous conversations do not cover each other.
      const below=!track.group&&head-height-12<8,top=track.group?Math.max(cell.y+4,head-height-12):below?Math.min(layout.height-height-8,speaker.y+10):head-height-12;
      element.classList.toggle('below',below);
      element.style.left=`${left}px`;element.style.top=`${top}px`;
      element.style.setProperty('--tail-left',`${Math.max(16,Math.min(width-16,speaker.x-left))}px`);
      placed.push(element.getBoundingClientRect());
    }
    labels.classList.toggle('crowded',cast.size>20);
    for(const item of [...cast.values()].sort((first,second)=>(second.id===selected)-(first.id===selected))){
      item.label.hidden=speaking.has(item.id)||(cast.size>20&&item.id!==selected);
      if(item.label.hidden)continue;
      item.label.style.left=`${item.x}px`;item.label.style.top=`${item.y-21*unit}px`;
      const bounds=item.label.getBoundingClientRect();
      if(placed.some(other=>bounds.left<other.right+3&&bounds.right>other.left-3&&bounds.top<other.bottom+3&&bounds.bottom>other.top-3))item.label.hidden=true;
      else placed.push(bounds);
    }
  }
  function animate(time=0){
    requestAnimationFrame(animate);
    const delta=Math.min(100,Math.max(0,time-(last||time)));last=time;
    if(!layout||!host.clientWidth||!host.clientHeight){
      for(const track of tracks){track.arrived=true;reveal(track);}
      return;
    }
    const speech=!town&&tracks[0]?.items[0],speaker=speech&&cast.get(speech.agent_id),pace=layout.tile*6*playing.speed*delta/1000;
    for(const item of cast.values()){
      const target=item.slot||(item===speaker&&tracks[0].target?.x!==undefined?tracks[0].target:item.home);
      const dx=target.x-item.x,dy=target.y-item.y,distance=Math.hypot(dx,dy);
      item.moving=false;
      if(distance<=.5){if(item.slot)item.dir=item.face;continue;}
      if(reduced.matches||paused){item.x=target.x;item.y=target.y;continue;}
      const step=Math.min(distance,pace);
      item.x+=dx/distance*step;item.y+=dy/distance*step;item.moving=true;
      item.dir=Math.abs(dx)>Math.abs(dy)?(dx>0?'right':'left'):(dy>0?'down':'up');
    }
    for(const track of tracks){
      if(!track.arrived&&track.items.length)track.arrived=gathered(track);
      reveal(track);
    }
    const ratio=canvas.width/layout.width;
    context.setTransform(1,0,0,1,0,0);context.imageSmoothingEnabled=false;context.drawImage(ground,0,0);
    context.setTransform(ratio,0,0,ratio,0,0);
    for(const item of [...cast.values()].sort((first,second)=>first.y-second.y))sprite(item,time);
    place();
  }
  canvas.addEventListener('click',event=>{
    if(!layout)return;
    const bounds=canvas.getBoundingClientRect(),x=event.clientX-bounds.left,y=event.clientY-bounds.top;
    let nearest=null,best=layout.tile;
    for(const item of cast.values()){const distance=Math.hypot(item.x-x,item.y-9*layout.tile/16-y);if(distance<best){best=distance;nearest=item;}}
    if(nearest)choose(nearest.id);
  });
  new ResizeObserver(resize).observe(host);
  requestAnimationFrame(animate);
  return {render,wake:resize,select:id=>{selected=id;},palette,duration,
    restartSpeech:()=>{close();town=null;},
    remaining:()=>{
      tracks.forEach(credit);
      let longest=0;
      for(const track of tracks){
        const speech=track.items[track.index];
        let rest=speech?Math.max(0,duration(speech.text)-track.elapsed):0;
        if(town)for(const later of track.items.slice(track.index+1))rest+=duration(later.text);
        longest=Math.max(longest,rest);
      }
      if(!town)return tracks.length?longest/playing.speed:5000;
      return longest?longest/playing.speed:townDone?0:1000;
    },
    pause:()=>{paused=!paused;return paused;},reset:()=>{signature='';selected=null;close();town=null;}};
})();