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
  let tracks=[],town=null,townDone=true,courtMode=false,playing={paused:false,speed:1},cast=new Map(),signature='',selected=null,paused=false,deciding=new Set(),layout=null,last=0;
  const words=text=>text.match(/\s*\S+\s*/gu)||[];
  const duration=text=>Math.max(5000,words(text).length*400+1800);
  const hash=(x,y)=>(Math.imul(x+101,73856093)^Math.imul(y+211,19349663))>>>0;
  const seatOf=(role='',index=1)=>{
    const lower=role.toLowerCase();
    if(/judge|justice|bench|magistrate|presiding/.test(lower))return 'bench';
    if(/educational review|review panel/.test(lower))return 'review';
    if(/jury|juror|foreperson|assessor/.test(lower))return 'jury';
    if(/witness|deponent/.test(lower))return 'witness';
    if(/\(party\)/.test(lower))return 'party';
    if(/defense|defence|respondent|accused|opposite/.test(lower))return 'defense';
    if(/complainant|plaintiff|petitioner|claimant|prosecut|appellant/.test(lower))return 'petitioner';
    return ['bench','petitioner','defense','witness','witness','jury','jury','jury','petitioner','defense'][(index-1)%10];
  };
  const listenerOf=(speech,actions)=>{
    const replyTo=speech.reply_to??speech.data?.reply_to,parent=replyTo&&actions.find(action=>action.id===replyTo);
    return parent&&parent.agent_id!==speech.agent_id?cast.get(parent.agent_id):null;
  };
  const whereOf=(speech,actions)=>speech.platform==='court'?(speech.data?.phase||speech.data?.stage||'in Court'):speech.platform==='town'?`Group ${speech.data?.group}`:speech.kind==='interview'?'final interview'
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
  function courtSeats(){
    const {tile,columns,rows,center,hall}=layout,buckets={bench:[],petitioner:[],defense:[],witness:[],party:[],jury:[],review:[]};
    [...cast.values()].forEach((item,idx)=>buckets[seatOf(item.actor.role,idx+1)].push(item));
    const assign=(item,x,y,face,labelAbove=false)=>{item.home={x,y};item.slot={x,y};item.face=item.dir=face;item.seat=seatOf(item.actor.role,item.id);item.labelAbove=labelAbove;};
    // 1. Presiding Judge on the elevated top-center Bench dais (label above head)
    buckets.bench.forEach((item,idx)=>assign(item,(center.x+(idx-(buckets.bench.length-1)/2)*2.4)*tile,(hall.y+2.45)*tile,'down',true));
    // 2. Jury Box on the left wall (2 staggered columns x up to 6 rows)
    buckets.jury.forEach((item,idx)=>{
      const col=idx%2,row=Math.floor(idx/2);
      assign(item,(2.1+col*2.1)*tile,Math.min(rows-4.8,hall.y+4.4+row*1.85+col*.55)*tile,'right',false);
    });
    buckets.review.forEach((item,idx)=>assign(item,3.2*tile,(hall.y+4.4+idx*2.5)*tile,'right',false));
    // 3. Two parallel Counsel Tables in the well of the court (wider spacing + staggered label heights so both Counsel labels show)
    buckets.petitioner.forEach((item,idx)=>assign(item,(center.x-5.4+idx*2.9)*tile,(center.y+.55+(idx%2)*.45)*tile,'up',idx%2===1));
    buckets.defense.forEach((item,idx)=>assign(item,(center.x+2.5+idx*2.9)*tile,(center.y+.55+(idx%2)*.45)*tile,'up',idx%2===1));
    // 4. Witness Stand (left of Bench) & Party/Witness Dock (right wall enclosure)
    buckets.witness.forEach((item,idx)=>{
      if(idx===0)assign(item,(center.x-6.2)*tile,(hall.y+2.95)*tile,'down',true);
      else assign(item,(center.x+6.1)*tile,(hall.y+2.95+(idx-1)*2.2)*tile,'down',true);
    });
    buckets.party.forEach((item,idx)=>assign(item,(columns-3.1)*tile,(center.y-6.0+idx*2.5)*tile,'left',false));
  }
  function arrange(){
    if(courtMode){courtSeats();return;}
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
    if(courtMode){
      const box3d=(x,y,w,h,d,topFill,frontFill,stroke='#3e2616')=>{
        draw.fillStyle='rgba(22,16,12,.22)';
        draw.fillRect(Math.round((x+.18)*tile),Math.round((y+d+.18)*tile),Math.ceil(w*tile),Math.ceil(h*tile));
        block(x,y+h,w,d,frontFill);
        block(x,y,w,h,topFill);
        draw.strokeStyle=stroke;draw.lineWidth=Math.max(1,tile*.07);
        draw.strokeRect(Math.round(x*tile),Math.round(y*tile),Math.ceil(w*tile),Math.ceil(h*tile));
        draw.fillStyle='rgba(255,255,255,.16)';
        draw.fillRect(Math.round((x+.08)*tile),Math.round((y+.08)*tile),Math.ceil((w-.16)*tile),Math.max(2,Math.round(tile*.12)));
      };
      const chair3d=(cx,cy,dir='up',accent='#7c2d25')=>{
        box3d(cx-.48,cy-.38,.96,.72,.22,accent,'#4a1915','#2e120d');
        if(dir==='up')box3d(cx-.48,cy+.18,.96,.22,.32,'#5c3822','#382012');
        else if(dir==='down')box3d(cx-.48,cy-.52,.96,.22,.28,'#5c3822','#382012');
        else if(dir==='right')box3d(cx-.54,cy-.38,.22,.72,.28,'#5c3822','#382012');
        else if(dir==='left')box3d(cx+.32,cy-.38,.22,.72,.28,'#5c3822','#382012');
      };
      // Warm limestone & checkerboard marble courtroom floor
      block(0,0,columns,rows,'#ebe2d3');
      for(let y=1;y<rows-1;y++)for(let x=1;x<columns-1;x++){
        if((x+y)%2===0)block(x,y,1,1,'#e2d6c3');
      }
      // Architectural perimeter walls with 2.5D wainscot paneling & side windows
      box3d(0,0,columns,1.15,.35,'#4a2e1b','#2e1b0f','#1f1209');
      block(0,1.15,.85,rows-1.8,'#593822');block(columns-.85,1.15,.85,rows-1.8,'#593822');
      box3d(0,rows-.75,columns,.75,.2,'#4a2e1b','#2b190e');
      for(let wy=4;wy<rows-5;wy+=3){
        block(.12,wy,.55,1.8,'#bae6fd');block(columns-.67,wy,.55,1.8,'#bae6fd');
      }
      // Royal crimson courtroom carpet runner from entrance doors to Bench dais
      block(center.x-1.35,hall.y+3.8,2.7,rows-hall.y-4.5,'#8f2424');
      block(center.x-1.15,hall.y+3.8,2.3,rows-hall.y-4.5,'#ab2f2f');

      // 1. Elevated Judicial Dais & Presiding Bench (Top Center, with side stairs & flanking boxes)
      box3d(center.x-7.5,hall.y+.3,15.0,3.3,.48,'#c8ab83','#8c6743','#543820');
      for(let s=0;s<3;s++){
        block(center.x-5.3,hall.y+.6+s*.35,1.1,.28,'#b59368');
        block(center.x+4.2,hall.y+.6+s*.35,1.1,.28,'#b59368');
      }
      chair3d(center.x,hall.y+1.9,'down','#8f2424');
      box3d(center.x-4.1,hall.y+1.95,8.2,1.35,.62,'#7c4d2b','#4f2f18','#331d0d');
      block(center.x-3.7,hall.y+2.15,7.4,.9,'#992929');
      sign('PRESIDING BENCH',center.x,hall.y+2.62,Math.max(9,tile*.38),'#fff8eb');

      // Flanking Witness Stand (Left of Bench) & Court Clerk Box (Right of Bench)
      box3d(center.x-7.2,hall.y+1.7,2.2,1.7,.52,'#b89162','#75512d','#422b15');
      sign('Witness Stand',center.x-6.1,hall.y+1.35,Math.max(8,tile*.31),'#3b2312');
      box3d(center.x+5.0,hall.y+1.7,2.2,1.7,.52,'#b89162','#75512d','#422b15');
      sign([...cast.values()].filter(item=>seatOf(item.actor.role,item.id)==='witness').length>1?'Witness Stand':'Court Clerk',center.x+6.1,hall.y+1.35,Math.max(8,tile*.31),'#3b2312');

      // 2. Stepped 2-Column Jury Box along Left Wall (matching floorplan)
      if([...cast.values()].some(item=>['jury','review'].includes(seatOf(item.actor.role,item.id)))){
        const legacyJury=[...cast.values()].some(item=>seatOf(item.actor.role,item.id)==='jury');
        const juryRows=legacyJury?6:[...cast.values()].filter(item=>seatOf(item.actor.role,item.id)==='review').length;
        const juryTop=hall.y+3.4,juryH=Math.min(rows-juryTop-4.6,juryRows*(legacyJury?1.65:2.5)+.8);
        box3d(1.15,juryTop,4.1,juryH,.45,'#d4bc96','#87633f','#4a3119');
        for(let r=0;r<juryRows;r++){
          const cy=legacyJury?juryTop+.85+r*1.62:hall.y+4.4+r*2.5;
          if(cy+0.6<juryTop+juryH){
            if(legacyJury){chair3d(2.35,cy,'right','#6b442a');chair3d(4.0,cy,'right','#6b442a');}
            else chair3d(3.2,cy,'right','#6b442a');
          }
        }
        sign(legacyJury?'JURY BOX':'REVIEW PANEL',3.2,juryTop-.35,Math.max(8,tile*.34),'#3b2312');
      }

      // 3. Well of the Court: Two Parallel Counsel Tables with 2 Chairs Each
      const tableY=center.y-1.65;
      // Left Table: Complainant / Petitioner Counsel
      chair3d(center.x-4.8,center.y+.35,'up','#14705e');
      chair3d(center.x-2.6,center.y+.35,'up','#14705e');
      box3d(center.x-5.8,tableY,4.3,1.55,.48,'#9c6b43','#5e3c20','#36200f');
      block(center.x-5.4,tableY+.25,.7,.5,'#f8fafc');block(center.x-3.1,tableY+.25,.7,.5,'#fef3c7');
      sign('Complainant / Plaintiff Counsel',center.x-3.65,tableY-.38,Math.max(8,tile*.33),'#0f594a');

      // Right Table: Accused / Defense Counsel
      chair3d(center.x+2.6,center.y+.35,'up','#991b1b');
      chair3d(center.x+4.8,center.y+.35,'up','#991b1b');
      box3d(center.x+1.5,tableY,4.3,1.55,.48,'#9c6b43','#5e3c20','#36200f');
      block(center.x+1.9,tableY+.25,.7,.5,'#f8fafc');block(center.x+4.2,tableY+.25,.7,.5,'#fee2e2');
      sign('Accused / Defense Counsel',center.x+3.65,tableY-.38,Math.max(8,tile*.33),'#8f1d1d');

      // 4. Right Wall Dock / Witness & Party Enclosure
      const dockTop=center.y-7.2;
      box3d(columns-4.6,dockTop,3.1,5.3,.45,'#d4bc96','#87633f','#4a3119');
      chair3d(columns-3.1,dockTop+1.2,'left','#6b442a');
      chair3d(columns-3.1,dockTop+3.7,'left','#6b442a');
      sign('Party / Dock',columns-3.05,dockTop-.35,Math.max(8,tile*.32),'#3b2312');

      // 5. Wooden Bar Railing + Public Gallery with Seated Audience in Back
      const barY=Math.max(center.y+2.1,rows-4.9);
      box3d(1.15,barY,center.x-3.0,.32,.35,'#704425','#452813');
      box3d(center.x+1.85,barY,columns-center.x-3.0,.32,.35,'#704425','#452813');
      sign('PUBLIC GALLERY & AUDIENCE',center.x,barY+.2,Math.max(8,tile*.3),'#fff8eb');

      const pewRows=Math.min(3,Math.max(1,Math.floor((rows-barY-1.4)/1.15)));
      const audienceColors=['#334155','#475569','#1e3a5f','#57534e','#3f6212','#6b21a8','#7c2d12','#0f766e'];
      const audienceHairs=['#1c1917','#44403c','#27272a','#57534e','#78716c'];
      for(let r=0;r<pewRows;r++){
        const py=barY+.85+r*1.12;
        box3d(1.6,py,center.x-3.6,.55,.26,'#8c5a36','#57351d');
        box3d(center.x+2.0,py,columns-center.x-3.6,.55,.26,'#8c5a36','#57351d');
        for(let s=0;s<5;s++){
          for(const side of [-1,1]){
            const ax=side<0?(2.35+s*((center.x-4.6)/4.5)):(center.x+2.65+s*((columns-center.x-4.6)/4.5));
            const seed=hash(s+r*7,side<0?11:29);
            if(seed%4===0)continue; // Leave a few empty seats for natural realism
            const coat=audienceColors[seed%audienceColors.length],hair=audienceHairs[seed%audienceHairs.length];
            block(ax-.32,py-.18,.64,.42,coat);
            disc(ax,py-.32,.22,'#d9a27c');
            block(ax-.22,py-.48,.44,.24,hair);
          }
        }
      }
      // Double courtroom entrance doors at bottom center
      box3d(center.x-1.6,rows-.82,3.2,.55,.2,'#6b3e20','#3d2210');
      return;
    }
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
    if(courtMode)return {x:speaker.home.x,y:speaker.home.y,facing:speaker.face};
    const {tile,center,hall,board,width}=layout,slot=(speech.agent_id%7-3)*tile;
    if(speech.kind==='interview')return {x:speaker.home.x,y:speaker.home.y,facing:'down'};
    if(listener)return {x:Math.max(tile,Math.min(width-tile,listener.home.x+(speaker.home.x<listener.home.x?-1.3:1.3)*tile)),y:listener.home.y,listener};
    if(speech.engine_kind==='send_to_group')return {x:center.x*tile+slot,y:(hall.y+hall.h+1.4)*tile,facing:'up'};
    return {x:(board.x+1.3)*tile+slot*.5,y:(board.y+2.9)*tile,facing:'up'};
  }
  function slots(){
    for(const item of cast.values())item.slot=null;
    if(!layout)return;
    if(courtMode){
      courtSeats();
      if(town?.groups[0])town.groups[0].cell={x:8,y:8,w:layout.width-16,h:layout.height-16};
      return;
    }
    if(!town)return;
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
    const next=`${run.id}:${run.config?.platform_mode||''}:${run.agents.map(actor=>actor.id).join(',')}`;
    courtMode=run.config?.platform_mode==='court';
    host.classList.toggle('courtroom',courtMode);
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
        track.items=actions.filter(action=>['town','court'].includes(action.platform)&&action.round===playback.tick&&action.data?.group===track.group.id)
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
    const activeSpeech=tracks.some(t=>t.items[t.index]?.agent_id===item.id&&!t.bubble.element.hidden);
    context.fillStyle='rgba(32,45,50,.24)';context.beginPath();context.ellipse(x,y,6.5*unit,2.4*unit,0,0,Math.PI*2);context.fill();
    if(activeSpeech){
      context.fillStyle='rgba(245,158,11,.26)';context.beginPath();context.ellipse(x,y,11*unit,4.5*unit,0,0,Math.PI*2);context.fill();
      context.strokeStyle='#d97706';context.lineWidth=Math.max(2,1.4*unit);context.beginPath();context.ellipse(x,y,11*unit,4.5*unit,0,0,Math.PI*2);context.stroke();
    }
    if(item.id===selected){context.strokeStyle='#f08368';context.lineWidth=Math.max(1.5,unit);context.beginPath();context.ellipse(x,y,8.5*unit,3.2*unit,0,0,Math.PI*2);context.stroke();}
    const seat=courtMode?(item.seat||seatOf(item.actor.role,item.id)):null;
    const robeColor=seat==='bench'?'#14161d':(seat==='petitioner'||seat==='defense')?'#1e242d':item.color;
    part(-4,-5,3,5-Math.max(0,swing),'#252f3d');part(1,-5,3,5-Math.max(0,-swing),'#252f3d');
    part(-7,-11+Math.max(0,-swing),2,5,seat==='bench'||seat==='petitioner'||seat==='defense'?'#1e242d':skin);
    part(5,-11+Math.max(0,swing),2,5,seat==='bench'||seat==='petitioner'||seat==='defense'?'#1e242d':skin);
    part(-5,-11,10,7,robeColor);part(-5,-5,10,1,'rgba(32,45,50,.28)');
    if(seat==='bench'){
      // Presiding Judge: crimson judicial stole + white judicial collar bands + gold trim
      part(-5,-11,2,7,'#8f2424');part(3,-11,2,7,'#8f2424');
      part(-2,-11,4,2,'#ffffff');part(-1.6,-9,1.1,3,'#ffffff');part(.5,-9,1.1,3,'#ffffff');
    }else if(seat==='petitioner'||seat==='defense'){
      // Indian Advocate robe: black gown, white shirt V-neck, two white advocate neck bands, side colour lapel badge
      part(-2,-11,4,2,'#f8fafc');part(-1.5,-9,1.0,3.2,'#ffffff');part(.5,-9,1.0,3.2,'#ffffff');
      part(2.5,-10,2,2,seat==='petitioner'?'#10b981':'#ef4444');
    }else if(seat==='jury'){
      part(-1.5,-11,3,2,'#f8fafc');
    }
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
      if(track.group)element.style.width=`${Math.max(150,Math.min(courtMode?290:300,cell.w-12))}px`;
      const head=((track.group&&!courtMode)?Math.min(...track.group.members.map(id=>cast.get(id)?.y??speaker.y)):speaker.y)-22*unit,width=element.offsetWidth,height=element.offsetHeight;
      let left=Math.max(8,Math.min(layout.width-width-8,Math.max(cell.x+6,Math.min(cell.x+cell.w-width-6,speaker.x-width/2))));
      let below=false,top=head-height-14;
      if(courtMode){
        left=(layout.width-width)/2;
        top=layout.height-height-10;
      }else if(track.group){
        top=Math.max(cell.y+4,head-height-12);
      }else if(head-height-14<8){
        below=true;top=Math.min(layout.height-height-8,speaker.y+12);
      }
      element.classList.toggle('below',below);
      element.style.left=`${left}px`;element.style.top=`${top}px`;
      element.style.setProperty('--tail-left',`${Math.max(16,Math.min(width-16,speaker.x-left))}px`);
      placed.push(element.getBoundingClientRect());
    }
    labels.classList.toggle('crowded',cast.size>20);
    for(const item of [...cast.values()].sort((first,second)=>(second.id===selected)-(first.id===selected))){
      const isSpeaking=speaking.has(item.id);
      item.label.classList.toggle('speaking-now',isSpeaking);
      item.label.hidden=(!courtMode&&isSpeaking)||(cast.size>20&&item.id!==selected&&!isSpeaking);
      if(item.label.hidden)continue;
      const labelWidth=item.label.offsetWidth;
      item.label.style.left=`${courtMode?Math.max(8+labelWidth/2,Math.min(layout.width-8-labelWidth/2,item.x)):item.x}px`;
      const above=!courtMode||item.labelAbove||isSpeaking;
      item.label.style.top=above?`${item.y-22*unit}px`:`${item.y+16*unit}px`;
      const bounds=item.label.getBoundingClientRect();
      if(!courtMode&&!isSpeaking&&placed.some(other=>bounds.left<other.right+3&&bounds.right>other.left-3&&bounds.top<other.bottom+3&&bounds.bottom>other.top-3))item.label.hidden=true;
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