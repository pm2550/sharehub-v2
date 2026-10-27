/* Original-art character. Nodding uses drawn cels; the other gestures retain the existing rig. */
import {createNodPlayer, NOD_SECONDS} from '/static/js/xiaoxing-nod.js?v=20260926-9';
const DURATIONS = {nod:NOD_SECONDS+.16, wave:4.2, wink:2.4, smile:3.2, tilt:3.6, star:3.8};
const clamp = (x, min=0, max=1) => Math.min(max, Math.max(min, x));
const ease = x => { x=clamp(x); return x*x*(3-2*x); };
const rest = () => ({head:0, headY:0, hand:0, shoulder:0, elbow:0, rightArm:0, left:0, right:0, smile:0, starX:0, starY:0, starTurn:0});

// Seconds on a single continuous motion timeline, including anticipation and settling.
export function sampleMotion(name, t) {
 const p=rest(), d=DURATIONS[name];
 if(!d || t<0 || t>=d) return p;
 const e=ease(t/.45)*ease((d-t)/.65);
 if(name==='wave') {
  p.shoulder=(-.14+.045*Math.sin(t*3.7))*e;
  p.elbow=(-.16+.18*Math.sin(t*4.2-.4))*e;
  p.hand=.58*Math.sin(t*8.4-.5)*e;
  p.head=-.055*e; p.headY=-3*e; p.smile=.55*e;
 }
 if(name==='wink') {
  p.left=ease((t-.2)/.25)*ease((d-.3-t)/.4);
  p.head=-.09*e; p.hand=-.16*e; p.shoulder=-.05*e; p.smile=.8*e;
 }
 if(name==='smile') {
  p.left=p.right=.96*e; p.smile=e; p.head=.055*e;
  p.headY=-4*e; p.shoulder=-.06*e; p.hand=.14*Math.sin(t*3)*e;
 }
 if(name==='tilt') {
  p.head=(.13-.21*ease((t-1.45)/.7))*e;
  p.headY=-4*e; p.smile=.5*e; p.hand=.17*e; p.elbow=-.08*e;
 }
 if(name==='star') {
  const launch=.72, land=2.3, flight=clamp((t-launch)/(land-launch));
  const anticipate=Math.sin(clamp(t/launch)*Math.PI);
  const catchTime=Math.max(0,t-land);
  p.rightArm=t<launch?.07*anticipate:t<land?-.10*Math.sin(flight*Math.PI):-.075*Math.sin(catchTime*8)*Math.exp(-catchTime*3)*e;
  p.starY=-140*4*flight*(1-flight)+(t<launch?8*anticipate:0);
  p.starX=-26*Math.sin(flight*Math.PI);
  p.starTurn=Math.PI*2*ease(flight);
  p.head=-.075*Math.sin(flight*Math.PI)*e; p.headY=-7*Math.sin(flight*Math.PI)*e;
  p.hand=.20*e; p.smile=.8*e;
 }
 return p;
}

export async function mountXiaoxing(host) {
 const W=800,H=1200,canvas=document.createElement('canvas');
 canvas.className='avatar-canvas'; canvas.setAttribute('role','img');
 canvas.setAttribute('aria-label','小星会招手、眨眼、点头，和你一起接住星光');
 const gl=canvas.getContext('webgl',{alpha:true,antialias:false,premultipliedAlpha:true,powerPreference:'low-power'});
 if(!gl) throw new Error('WebGL unavailable');
 const paths=['sharehub-muse-800.webp','xiaoxing-blink.webp','xiaoxing-arm-back.webp','xiaoxing-star-back.webp','xiaoxing-star.webp'];
 const [original,blink,armBack,starBack,star]=await Promise.all(paths.map(path=>new Promise((resolve,reject)=>{
  const img=new Image(); img.onload=()=>resolve(img); img.onerror=()=>reject(new Error('Art unavailable')); img.src='/static/images/'+path;
 })));
 const handPath=new Path2D('M344 318 C347 306 345 294 343 288 C336 278 323 271 309 266 L286 255 Q281 252 286 250 Q291 247 300 250 L324 256 L289 239 Q280 234 284 229 Q287 223 296 228 L329 245 L304 217 Q298 209 303 208 Q309 205 316 212 L339 233 L329 208 Q324 201 329 199 Q334 198 341 208 L357 239 Q365 250 374 252 L377 235 Q380 224 385 224 Q390 223 389 234 L389 258 Q389 272 382 285 L378 308 Q363 316 344 318 Z');
 const sleevePath=new Path2D('M392 286 C405 285 415 294 421 309 C427 328 433 347 430 365 C425 403 408 447 385 474 C370 491 353 503 336 501 C311 498 295 476 286 453 C276 430 267 413 270 397 C273 378 285 367 301 359 C307 344 307 323 311 306 C315 294 329 288 339 290 C355 285 375 291 382 302 Z');
 function layer(){const c=document.createElement('canvas');c.width=W;c.height=H;return c;}
 const base=layer(),bc=base.getContext('2d');bc.drawImage(original,0,0,W,H);
 // Repaint only the hidden local region; the face, clothing and moon remain the original.
 const erase=layer(),ec=erase.getContext('2d');
 ec.fill(sleevePath);ec.strokeStyle='#000';ec.lineWidth=1;ec.stroke(sleevePath);
 ec.fill(handPath);ec.lineWidth=4;ec.stroke(handPath);
 bc.globalCompositeOperation='destination-out';bc.drawImage(erase,0,0);
 bc.globalCompositeOperation='destination-over';bc.drawImage(armBack,250,185,225,340);
 bc.globalCompositeOperation='source-over';
 bc.clearRect(660,255,140,150);bc.drawImage(starBack,660,255,140,150);
 const arm=layer(),ac=arm.getContext('2d');ac.save();ac.clip(sleevePath);ac.drawImage(original,0,0,W,H);ac.restore();
 ac.globalCompositeOperation='destination-out';ac.fill(handPath);
 const hand=layer(),hc=hand.getContext('2d');hc.clip(handPath);hc.drawImage(original,0,0,W,H);
 const vertex=`precision highp float;
 attribute vec2 aPosition; varying vec2 vUV;
 uniform vec2 uFit,uGaze,uStar;
 uniform float uTime,uHead,uHeadY,uHand,uShoulder,uElbow,uRightArm,uHair,uLayer,uStill,uStarTurn;
 float region(vec2 p,vec2 c,vec2 r){return 1.-smoothstep(.45,1.,length((p-c)/r));}
 vec2 rotateAt(vec2 p,vec2 origin,float angle){float c=cos(angle),s=sin(angle);vec2 q=p-origin;return origin+vec2(c*q.x-s*q.y,s*q.x+c*q.y);}
 void main(){vec2 p=aPosition;vUV=p/vec2(800.,1200.);
 if(uLayer>2.5) {
  vUV=(p-vec2(670.,266.))/vec2(117.,124.);
  p=rotateAt(p,vec2(728.5,328.),uStarTurn);
  p=rotateAt(p,vec2(642.,480.),uRightArm);p+=uStar;
 } else if(uLayer>.5) {
  // Hierarchical joints: finger/wrist -> elbow -> shoulder, with a soft cuff.
  if(uLayer>1.5) p=rotateAt(p,vec2(360.,311.),uHand*(1.-smoothstep(291.,321.,aPosition.y)));
  float forearm=(1.-smoothstep(398.,430.,aPosition.x))*(1.-smoothstep(370.,466.,aPosition.y));
  p=rotateAt(p,vec2(338.,438.),uElbow*forearm);
  p=rotateAt(p,vec2(414.,291.),uShoulder);
 } else {
  float head=(1.-smoothstep(225.,330.,p.y))*smoothstep(285.,355.,p.x)*(1.-smoothstep(640.,710.,p.x));
  p=mix(p,rotateAt(p,vec2(460.,275.),uHead+uGaze.x*.035),head);
  p+=vec2(uGaze.x*2.5,uGaze.y*1.5+uHeadY)*head;
  float hairL=region(aPosition,vec2(231.,454.),vec2(113.,190.));
  float hairR=region(aPosition,vec2(704.,457.),vec2(65.,180.));
  p.x+=(sin(uTime*1.25+aPosition.y*.014)*5.5*hairL+sin(uTime*1.05+aPosition.y*.016)*4.5*hairR)*(1.-uStill)+uHair*(hairL+hairR*.7);
  p.y+=sin(uTime*1.55)*.8*region(aPosition,vec2(492.,423.),vec2(120.,143.))*(1.-uStill);
  float rightArm=region(aPosition,vec2(712.,390.),vec2(92.,137.));
  p=mix(p,rotateAt(p,vec2(642.,480.),uRightArm),rightArm);
 }
 gl_Position=vec4((p/vec2(800.,1200.)*2.-1.)*vec2(uFit.x,-uFit.y),0.,1.);}`;
 const fragment=`precision highp float;
 varying vec2 vUV; uniform sampler2D uBase,uBlink,uArmTex,uHandTex,uStarTex;
 uniform float uLayer,uLeft,uRight,uSmile; uniform vec2 uGaze;
 float eye(vec2 p,vec2 c,vec2 r){vec2 q=p-c;q=vec2(.94*q.x-.342*q.y,.342*q.x+.94*q.y);return 1.-smoothstep(.68,1.,length(q/r));}
 void main(){
 if(uLayer>2.5){gl_FragColor=texture2D(uStarTex,vUV);return;}
 if(uLayer>1.5){gl_FragColor=texture2D(uHandTex,vUV);return;}
 if(uLayer>.5){gl_FragColor=texture2D(uArmTex,vUV);return;}
 vec2 p=vUV*vec2(800.,1200.);float left=eye(p,vec2(423.,188.),vec2(31.,23.));float right=eye(p,vec2(493.,161.),vec2(30.,24.));
 vec2 gazeUV=vUV-vec2(uGaze.x*1.1,uGaze.y*.65)/vec2(800.,1200.)*max(left*(1.-uLeft),right*(1.-uRight));
 vec4 color=texture2D(uBase,gazeUV);vec4 closed=texture2D(uBlink,(p-vec2(383.,125.))/vec2(152.,100.));
 color=mix(color,closed,max(left*uLeft,right*uRight));
 float blush=(1.-smoothstep(.2,1.,length((p-vec2(437.,209.))/vec2(17.,9.))))+(1.-smoothstep(.2,1.,length((p-vec2(511.,184.))/vec2(14.,8.))));
 color.rgb=mix(color.rgb,vec3(.98,.56,.68),blush*uSmile*.14);gl_FragColor=color;}`;
 function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('Character shader unavailable: '+gl.getShaderInfoLog(s));return s;}
 const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment),program=gl.createProgram();
 gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
 if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Character renderer unavailable: '+gl.getProgramInfoLog(program));gl.useProgram(program);
 const uniforms={};for(const name of ['Fit','Gaze','Star','Time','Head','HeadY','Hand','Shoulder','Elbow','RightArm','Hair','Layer','Still','StarTurn','Left','Right','Smile','Base','Blink','ArmTex','HandTex','StarTex'])uniforms[name]=gl.getUniformLocation(program,'u'+name);
 function grid(x,y,w,h,nx,ny){const v=[];for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){const a=x+i*w/nx,b=y+j*h/ny,c=x+(i+1)*w/nx,d=y+(j+1)*h/ny;v.push(a,b,c,b,a,d,c,b,c,d,a,d);}const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(v),gl.STATIC_DRAW);return {buffer,count:v.length/2};}
 const meshes=[grid(0,0,W,H,40,60),grid(255,280,185,230,24,28),grid(275,190,130,140,18,20),grid(670,266,117,124,1,1)],textures=[];
 gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);
 [base,blink,arm,hand,star].forEach((source,i)=>{const tex=gl.createTexture();textures.push(tex);gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,tex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);});
 ['Base','Blink','ArmTex','HandTex','StarTex'].forEach((name,i)=>gl.uniform1i(uniforms[name],i));
 gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
 const position=gl.getAttribLocation(program,'aPosition');gl.enableVertexAttribArray(position);
 let time=0,last=0,raf=0,timer=0,visible=true,alive=true,frames=0,active=false,current=null,drawCost=0,nextGesture=1.1,gestureIndex=0;
 let pose=rest(),hair=0,hairSpeed=0;
 let nodPlayer=null,nodLoading=null,actionRequest=0,pendingAction=null;
 const status=host.querySelector('.avatar-status');
 const gaze={x:0,y:0,tx:0,ty:0}, controls=Array.from(document.querySelectorAll('[data-avatar-action]'));
 const quiet=()=>document.documentElement.dataset.motion==='off';
 function signal(name){host.dataset.avatarGesture=name||'idle';controls.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.avatarAction===name)));}
 function begin(name){if(name==='nod'){gaze.tx=gaze.ty=0;}current={name,elapsed:0,duration:DURATIONS[name],from:{...pose}};nextGesture=time+20;signal(name);}
 function update(dt,motionDt=dt){
  time+=dt;const smooth=1-Math.exp(-dt*7);gaze.x+=(gaze.tx-gaze.x)*smooth;gaze.y+=(gaze.ty-gaze.y)*smooth;
  if(!current&&time>=nextGesture&&!quiet()){begin(['wave','tilt','star','smile'][gestureIndex++%4]);}
  pose=rest();const phase=time%5.2,blink=phase>4.9?Math.pow(Math.sin((phase-4.9)/.3*Math.PI),2):0;
  if(current){
   current.elapsed+=motionDt;pose=sampleMotion(current.name,current.elapsed);
   // A new click smoothly takes over from the current pose, including a flying star.
   const blend=ease(current.elapsed/.28);
   for(const key of Object.keys(pose)){
    let from=current.from[key];if(key==='starTurn')from=((from+Math.PI)%(Math.PI*2)+Math.PI*2)%(Math.PI*2)-Math.PI;
    pose[key]=from*(1-blend)+pose[key]*blend;
   }
   if(current.elapsed>=current.duration){current=null;signal(null);if(pendingAction){const next=pendingAction;pendingAction=null;begin(next);}}
  }
  if(current?.name!=='nod'){pose.left=Math.max(pose.left,blink);pose.right=Math.max(pose.right,blink);}else{const settle=1-ease(current.elapsed/.28);gaze.x*=settle;gaze.y*=settle;hair*=settle;hairSpeed*=settle;}
  const target=clamp(-pose.head*65-pose.shoulder*16,-12,12);
  hairSpeed+=(target-hair)*32*dt;hairSpeed*=Math.exp(-8*dt);hair+=hairSpeed*dt;
 }
 function draw(){
  if(!alive)return;const began=performance.now();
  if(current?.name==='nod'&&nodPlayer){
   nodPlayer.draw(current.elapsed,canvas.width,canvas.height);canvas.style.visibility='hidden';
   frames++;drawCost=drawCost*.8+(performance.now()-began)*.2;return;
  }
  nodPlayer?.hide();canvas.style.visibility='';
  gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
  const ratio=canvas.width/canvas.height,art=W/H;
  gl.uniform2f(uniforms.Fit,ratio>art?art/ratio:1,ratio>art?1:ratio/art);gl.uniform2f(uniforms.Gaze,gaze.x,gaze.y);gl.uniform2f(uniforms.Star,pose.starX,pose.starY);
  gl.uniform1f(uniforms.Time,time);gl.uniform1f(uniforms.Still,quiet()?1:0);gl.uniform1f(uniforms.Hair,hair);
  for(const key of ['Head','HeadY','Hand','Shoulder','Elbow','RightArm','Left','Right','Smile','StarTurn'])gl.uniform1f(uniforms[key],pose[key[0].toLowerCase()+key.slice(1)]);
  // The palm is in the body layer and naturally covers the star's lower tip.
  for(const i of [3,0,1,2]){const mesh=meshes[i];gl.uniform1f(uniforms.Layer,i);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.buffer);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);gl.drawArrays(gl.TRIANGLES,0,mesh.count);}
  frames++;drawCost=drawCost*.8+(performance.now()-began)*.2;
 }
 function canRun(){return alive&&visible&&!document.hidden&&!quiet()&&host.getClientRects().length>0&&!host.closest('[hidden]');}
 function stop(){clearTimeout(timer);cancelAnimationFrame(raf);timer=raf=0;last=0;active=false;}
 function tick(now){raf=timer=0;if(!canRun()){active=false;return;}active=true;const rawDt=last?Math.max(0,(now-last)/1000):1/30,dt=Math.min(rawDt,.06);last=now;update(dt,current?.name==='nod'?Math.min(rawDt,.12):dt);draw();if(current?.name==='nod'){timer=setTimeout(()=>tick(performance.now()),50);}else{const fps=drawCost>20?18:current?30:24;timer=setTimeout(()=>{raf=requestAnimationFrame(tick);},Math.max(0,1000/fps-drawCost-4));}}
 function sync(){stop();if(canRun()){if(current?.name==='nod')timer=setTimeout(()=>tick(performance.now()),0);else raf=requestAnimationFrame(tick);}else if(visible&&!document.hidden)draw();}
 function resize(){const r=host.getBoundingClientRect();if(!r.width||!r.height)return;const dpr=Math.min(devicePixelRatio||1,matchMedia('(max-width:700px)').matches?1.5:1.75);canvas.width=Math.round(r.width*dpr);canvas.height=Math.round(r.height*dpr);draw();}
 async function action(name){
  if(!DURATIONS[name]||!alive)return false;
  if(name==='nod'&&quiet()){if(status)status.textContent='静态模式已开启，打开页面动效后可以和小星点头互动。';return false;}
  if(name==='nod'&&(nodLoading||current?.name==='nod'))return false;
  const request=++actionRequest;
  if(name==='nod'&&!nodPlayer){
   if(status)status.textContent='正在准备小星的点头动作…';
   host.dataset.nodState='loading';
   nodLoading=createNodPlayer(host,original);
   try{const loaded=await nodLoading;if(!alive){loaded.dispose();return false;}nodPlayer=loaded;host.dataset.nodState='ready';}
   catch(error){if(alive){host.dataset.nodState='error';if(status&&request===actionRequest)status.textContent='点头画面暂时没加载好，可以再点一次。';}return false;}
   finally{nodLoading=null;}
   if(request!==actionRequest||!alive)return false;
  }
  if(status)status.textContent='';
  // Finish this short nod before accepting another gesture; repeated clicks never restart it.
  if(current?.name==='nod'&&nodPlayer?.stats().shown){pendingAction=name;return true;}
  pendingAction=null;begin(name);
  if(name==='nod')draw();
  if(quiet()){current.elapsed=name==='star'?1.5:.8;update(0);draw();}else sync();
  return true;
 }
 function pointer(event){if(quiet())return;const r=host.getBoundingClientRect();gaze.tx=clamp((event.clientX-r.left-r.width/2)/(r.width/2),-1,1);gaze.ty=clamp((event.clientY-r.top-r.height*.3)/(r.height*.5),-1,1);}
 function resetGaze(){gaze.tx=gaze.ty=0;}
 function touch(event){if(event.target.closest('button'))return;const r=host.getBoundingClientRect(),s=Math.min(r.width/W,r.height/H);const x=(event.clientX-r.left-(r.width-W*s)/2)/s,y=(event.clientY-r.top-(r.height-H*s)/2)/s;action(x>625&&y<465?'star':x<395&&y<510?'wave':y<285?'wink':'tilt');}
 host.append(canvas);host.classList.add('avatar-ready');host.dataset.avatarState='ready';host.dataset.avatarKind='original-2d';
 host.addEventListener('pointermove',pointer,{passive:true});host.addEventListener('pointerleave',resetGaze);host.addEventListener('click',touch);
 const sizes=new ResizeObserver(resize);sizes.observe(host);
 const views=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05});views.observe(host);
 const settings=new MutationObserver(sync);settings.observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
 document.addEventListener('visibilitychange',sync);
 const external=e=>action(e.detail);window.addEventListener('sharehub:avatar-action',external);
 function dispose(){stop();alive=false;actionRequest++;nodPlayer?.dispose();sizes.disconnect();views.disconnect();settings.disconnect();document.removeEventListener('visibilitychange',sync);window.removeEventListener('sharehub:avatar-action',external);host.removeEventListener('pointermove',pointer);host.removeEventListener('pointerleave',resetGaze);host.removeEventListener('click',touch);textures.forEach(t=>gl.deleteTexture(t));meshes.forEach(m=>gl.deleteBuffer(m.buffer));gl.deleteProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);}
 canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();dispose();host.classList.remove('avatar-ready');host.dataset.avatarState='fallback';host.dispatchEvent(new CustomEvent('avatar-error',{bubbles:true}));});
 const api={action,sync,stats:()=>({kind:'original-art-2d',frames,active,drawCalls:nodPlayer?.stats().shown?0:4,triangles:nodPlayer?.stats().shown?0:6866,nod:nodPlayer?.stats()||null,nodLoading:!!nodLoading,action:current?.name||null,elapsed:current?.elapsed||0,drawMs:drawCost,...pose,gaze:{x:gaze.x,y:gaze.y}})};
 window.ShareHubAvatar=api;signal(null);if(!quiet()){begin('wave');gestureIndex=1;}resize();sync();
 window.addEventListener('pagehide',event=>{if(event.persisted)stop();else dispose();});window.addEventListener('pageshow',event=>{if(event.persisted&&alive)sync();});
 return api;
}
