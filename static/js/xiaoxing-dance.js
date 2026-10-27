/* A short, on-demand full-body dance using the matching standing illustration.
   Local joint weights and two-bone leg IK; no model, video or audio download. */
const TAU=Math.PI*2, SCALE=.66, END=13.2, RETURN=11.2;
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const ease=v=>{v=clamp(v);return v*v*(3-2*v);};
const mix=(a,b,t)=>a+(b-a)*t;
const rotate=(p,o,a)=>[o[0]+Math.cos(a)*(p[0]-o[0])-Math.sin(a)*(p[1]-o[1]),o[1]+Math.sin(a)*(p[0]-o[0])+Math.cos(a)*(p[1]-o[1])];
const LEGS=[{hip:[465,780],knee:[427,1015],ankle:[396,1310],side:1},{hip:[623,780],knee:[635,1015],ankle:[683,1310],side:-1}];
export function solveLeg(leg,target,body,foot=0){
 const p=rotate(target,[550,650],-body),h=leg.hip,k=leg.knee,a=leg.ankle;
 const l1=Math.hypot(k[0]-h[0],k[1]-h[1]),l2=Math.hypot(a[0]-k[0],a[1]-k[1]);
 const dx=p[0]-h[0],dy=p[1]-h[1],d=clamp(Math.hypot(dx,dy),Math.abs(l1-l2)+1,l1+l2-.2);
 const alpha=Math.acos(clamp((l1*l1+d*d-l2*l2)/(2*l1*d),-1,1));
 const theta=Math.atan2(dy,dx)+alpha*leg.side,actualK=[h[0]+Math.cos(theta)*l1,h[1]+Math.sin(theta)*l1];
 const upper=theta-Math.atan2(k[1]-h[1],k[0]-h[0]);
 const lower=Math.atan2(p[1]-actualK[1],p[0]-actualK[0])-Math.atan2(a[1]-k[1],a[0]-k[0])-upper;
 return [upper,lower,foot-upper-lower-body];
}
export function sampleDance(t){
 const p={x:65,y:148,body:0,head:0,bow:0,leftShoulder:0,rightShoulder:0,leftElbow:0,rightElbow:0,leftWrist:0,rightWrist:0,footLX:396,footRX:683,footLY:1310,footRY:1310,footLA:0,footRA:0,hair:0,alpha:1,seated:0,moon:1,phase:'dance'};
 if(t<1.6){
  const q=ease(t/1.4),lift=Math.sin(clamp(t/1.4)*Math.PI);
  p.x=mix(117,65,q);p.y=mix(55,148,q)+18*Math.sin(clamp((t-1.15)/.45)*Math.PI);
  p.alpha=ease((t-.08)/.48);p.seated=1-p.alpha;p.moon=p.alpha;p.phase='arrival';
  p.leftShoulder=.65*lift;p.rightShoulder=-.55*lift;p.leftElbow=.45*lift;p.rightElbow=-.4*lift;
  p.footLY-=100*lift;p.footRY-=65*lift;p.footLA=-.13*lift;p.footRA=.16*lift;
  p.body=-.05*lift;p.head=.05*lift;
 }else if(t<10.25){
  const beat=(t-1.6)*112/60,cycle=beat%2,left=cycle<1?Math.sin(cycle*Math.PI):0,right=cycle>=1?Math.sin((cycle-1)*Math.PI):0;
  const beatSwing=Math.sin(beat*Math.PI),sway=Math.sin(beat*Math.PI/2);
  p.x+=16*beatSwing;p.y+=9*(1-Math.cos(beat*TAU));p.body=.075*beatSwing;p.head=-p.body*.6;
  p.footLX-=50*left;p.footRX+=50*right;p.footLY-=105*left;p.footRY-=105*right;
  p.footLA=-.14*left;p.footRA=.14*right;
  // Phrases overlap through eased envelopes instead of snapping at beat boundaries.
  const reach=ease((beat-3.5)/.7)*(1-ease((beat-7.7)/.7));
  const open=ease((beat-7.5)/.7)*(1-ease((beat-11.7)/.7));
  const finale=ease((beat-11.5)/.7);
  p.leftShoulder=mix(.38+.2*sway,1.48+.18*beatSwing,reach);
  p.rightShoulder=mix(-.38+.2*sway,-1.48+.18*beatSwing,reach);
  p.leftElbow=mix(.28+.2*left,1.10+.15*right,reach);
  p.rightElbow=mix(-.28-.2*right,-1.10-.15*left,reach);
  p.leftShoulder=mix(p.leftShoulder,.92+.16*beatSwing,open);
  p.rightShoulder=mix(p.rightShoulder,-.92+.16*beatSwing,open);
  p.leftElbow=mix(p.leftElbow,.18,open);p.rightElbow=mix(p.rightElbow,-.18,open);
  p.footLX+=95*open*left;p.footRX-=95*open*right;
  p.leftShoulder=mix(p.leftShoulder,1.45,finale);p.leftElbow=mix(p.leftElbow,1.05,finale);
  p.rightShoulder=mix(p.rightShoulder,-.75,finale);p.rightElbow=mix(p.rightElbow,-.45,finale);
  p.leftWrist=.25*Math.sin(beat*Math.PI*2)*finale;p.rightWrist=-.18*Math.sin(beat*Math.PI);
  p.hair=-p.body*42+Math.sin(beat*Math.PI-.7)*5;
 }else if(t<RETURN){
  const q=ease((t-10.25)/.55),bow=Math.sin(clamp((t-10.25)/.95)*Math.PI);
  const last=sampleDance(10.249);
  for(const key of ['leftShoulder','rightShoulder','leftElbow','rightElbow','leftWrist','rightWrist'])p[key]=last[key]*(1-q);
  p.body=.025*bow;p.head=.02*bow;p.bow=bow;p.y+=10*bow;p.phase='bow';
 }else{
  const q=ease((t-RETURN)/1.55),lift=Math.sin(clamp((t-RETURN)/1.55)*Math.PI);
  p.x=mix(65,117,q);p.y=mix(148,55,q)-28*lift;
  p.leftShoulder=.45*lift;p.rightShoulder=-.5*lift;p.leftElbow=.45*lift;p.rightElbow=-.45*lift;
  p.footLY-=90*lift;p.footRY-=60*lift;p.head=-.04*lift;p.phase='return';
  p.seated=ease((t-12.35)/.7);p.alpha=1-p.seated;p.moon=p.alpha;
 }
 // Keep planted feet still while the pelvis bounces and shifts sideways.
 if(t>=1.6&&t<RETURN){p.footLX-=(p.x-65)/SCALE;p.footRX-=(p.x-65)/SCALE;p.footLY-=(p.y-148)/SCALE;p.footRY-=(p.y-148)/SCALE;}
 p.legs=[solveLeg(LEGS[0],[p.footLX,p.footLY],p.body,p.footLA),solveLeg(LEGS[1],[p.footRX,p.footRY],p.body,p.footRA)];
 return p;
}

export async function prepareDance(host){
 const names=['xiaoxing-standing-v5.webp','xiaoxing-standing-back-v5.webp','xiaoxing-moon-v5.webp'];
 const images=await Promise.all(names.map(name=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Dance artwork unavailable'));image.src='/static/images/'+name;})));
 const [standing,back,moon]=images;
 const make=(w=1024,h=1536)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c;};
 const armPaths=[
  new Path2D('M418 289 Q443 280 457 315 L450 354 L430 392 Q424 441 389 482 Q340 549 298 581 Q277 616 243 625 L220 650 L181 691 L161 722 L79 722 L59 654 L93 584 L159 576 L187 535 Q207 513 250 499 Q292 476 325 444 Q347 414 358 376 L377 334 L395 334 Z'),
  new Path2D('M643 297 Q670 305 685 328 L713 363 L724 411 Q743 443 779 466 Q824 492 849 529 L887 589 L955 596 L991 689 L960 738 L865 731 L816 656 L795 632 Q755 627 725 590 Q690 548 679 504 L674 449 L663 397 L655 356 Z')
 ];
 function masked(path,box,skinAbove=0){
  const c=make(),ctx=c.getContext('2d');ctx.save();ctx.clip(path);ctx.drawImage(standing,0,0);ctx.restore();
  const [x,y,w,h]=box,data=ctx.getImageData(x,y,w,h);
  for(let row=0;row<h;row++)for(let col=0;col<w;col++){
   const i=(row*w+col)*4;if(!data.data[i+3]||(skinAbove&&row+y>=skinAbove))continue;
   // Cream fabric and skin are warm; the hair/dress behind them is lavender.
   const warm=clamp((data.data[i+1]-data.data[i+2]+7)/12);
   data.data[i+3]=Math.round(data.data[i+3]*warm);
  }
  ctx.putImageData(data,x,y);return c;
 }
 const leftArm=masked(armPaths[0],[55,278,410,460]),rightArm=masked(armPaths[1],[630,288,375,465]);
 const legPaths=[new Path2D('M350 755 H552 V1536 H320 Z'),new Path2D('M552 755 H755 V1536 H552 Z')];
 const leftLeg=masked(legPaths[0],[320,755,232,781],970),rightLeg=masked(legPaths[1],[552,755,203,781],970);
 const body=make(),bc=body.getContext('2d');bc.drawImage(standing,0,0);bc.globalCompositeOperation='destination-out';
 for(const path of armPaths){bc.fill(path);bc.lineWidth=2;bc.stroke(path);}
 for(const c of [leftLeg,rightLeg])bc.drawImage(c,0,0);bc.clearRect(0,903,1024,633);
 bc.globalCompositeOperation='destination-over';bc.drawImage(back,0,0);bc.globalCompositeOperation='source-over';
 const definitions=[
  {kind:0,source:moon,rect:[0,0,800,940],grid:[1,1]},
  {kind:3,source:leftLeg,rect:[318,750,238,786],grid:[18,38]},
  {kind:4,source:rightLeg,rect:[549,750,211,786],grid:[18,38]},
  {kind:1,source:body,rect:[0,0,1024,970],grid:[38,40]},
  {kind:5,source:leftArm,rect:[50,275,420,480],grid:[24,26]},
  {kind:6,source:rightArm,rect:[625,285,385,480],grid:[24,26]}
 ];
 const textures=definitions.map(d=>{const [x,y,w,h]=d.rect,c=make(w,h);c.getContext('2d').drawImage(d.source,x,y,w,h,0,0,w,h);return c;});
 definitions.forEach(d=>delete d.source);
 for(const c of [body,leftArm,rightArm,leftLeg,rightLeg])c.width=c.height=0;
 return {play};

 function play(seated,onFinish,onState){
  const canvas=document.createElement('canvas');canvas.className='avatar-dance-canvas';canvas.setAttribute('role','img');canvas.setAttribute('aria-label','小星离开月亮，落地踏步、抬手跳舞，再回到座位');
  const gl=canvas.getContext('webgl',{alpha:true,antialias:false,premultipliedAlpha:true,powerPreference:'low-power'});
  if(!gl)throw new Error('Dance renderer unavailable');
  const vertex=`precision highp float;
  attribute vec2 aPosition;varying vec2 vUV;uniform vec4 uRect;uniform vec2 uFit,uOrigin,uShoulder,uElbow,uWrist;uniform vec3 uLegL,uLegR;
  uniform float uKind,uBody,uHead,uBow,uHair,uTime;
  vec2 rotateAt(vec2 p,vec2 o,float a){float c=cos(a),s=sin(a);vec2 q=p-o;return o+vec2(c*q.x-s*q.y,s*q.x+c*q.y);}
  void main(){vec2 p=aPosition;vUV=(p-uRect.xy)/uRect.zw;
   
   if(uKind>.5){
    if(uKind>4.5){
     bool left=uKind<5.5;vec2 shoulder=left?vec2(423.,320.):vec2(650.,329.);vec2 elbow=left?vec2(306.,480.):vec2(764.,490.);vec2 wrist=left?vec2(201.,610.):vec2(856.,624.);
     float forearm=smoothstep(-38.,38.,dot(aPosition-elbow,normalize(wrist-elbow)));
     float hand=smoothstep(-18.,22.,dot(aPosition-wrist,normalize(wrist-elbow)));
     p=rotateAt(p,wrist,(left?uWrist.x:uWrist.y)*hand);
     p=rotateAt(p,elbow,(left?uElbow.x:uElbow.y)*forearm);
     p=rotateAt(p,shoulder,left?uShoulder.x:uShoulder.y);
    }else if(uKind>2.5){
     bool left=uKind<3.5;vec2 hip=left?vec2(465.,780.):vec2(623.,780.);vec2 knee=left?vec2(427.,1015.):vec2(635.,1015.);vec2 ankle=left?vec2(396.,1310.):vec2(683.,1310.);vec3 angle=left?uLegL:uLegR;
     p=rotateAt(p,ankle,angle.z*smoothstep(1260.,1330.,aPosition.y));
     p=rotateAt(p,knee,angle.y*smoothstep(980.,1050.,aPosition.y));p=rotateAt(p,hip,angle.x);
    }else{
     float head=1.-smoothstep(260.,400.,aPosition.y);p=mix(p,rotateAt(p,vec2(525.,330.),uHead),head);
     float hair=(1.-smoothstep(500.,800.,aPosition.y))*smoothstep(160.,270.,abs(aPosition.x-540.));
     p.x+=(uHair+sin(uTime*4.+aPosition.y*.008)*3.)*hair;
     float skirt=smoothstep(570.,830.,aPosition.y);p.x+=sin(uTime*5.+aPosition.y*.009)*5.*skirt;
    }
    p.y+=uBow*42.*(1.-smoothstep(520.,720.,aPosition.y));p=rotateAt(p,vec2(550.,650.),uBody);p=p*.66+uOrigin;
   }
   gl_Position=vec4((p/vec2(800.,1200.)*2.-1.)*vec2(uFit.x,-uFit.y),0.,1.);
  }`;
  const fragment='precision highp float;varying vec2 vUV;uniform sampler2D uTex;uniform float uAlpha,uKind;void main(){if(uKind<-1.5){vec2 q=(vUV-.5)*2.;float a=pow(max(0.,1.-dot(q,q)),2.)*.17*uAlpha;gl_FragColor=vec4(vec3(.35,.21,.40)*a,a);}else gl_FragColor=texture2D(uTex,vUV)*uAlpha;}';
  function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
  const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment),program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));gl.useProgram(program);
  const u={};for(const name of ['Rect','Fit','Origin','Shoulder','Elbow','Wrist','LegL','LegR','Kind','Body','Head','Bow','Hair','Time','Tex','Alpha'])u[name]=gl.getUniformLocation(program,'u'+name);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
  const meshes=[{kind:-2,rect:[170,1128,470,50],grid:[1,1]},...definitions,{kind:-1,rect:[0,0,800,1200],grid:[1,1]}].map((d,index)=>{
   const v=[],[x,y,w,h]=d.rect,[nx,ny]=d.grid;
   for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){const a=x+i*w/nx,b=y+j*h/ny,c=x+(i+1)*w/nx,f=y+(j+1)*h/ny;v.push(a,b,c,b,a,f,c,b,c,f,a,f);}
   const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(v),gl.STATIC_DRAW);
   const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,index===0?make(1,1):index<=textures.length?textures[index-1]:seated);
   return {...d,buffer,tex,count:v.length/2};
  });
  const attribute=gl.getAttribLocation(program,'aPosition');gl.enableVertexAttribArray(attribute);gl.uniform1i(u.Tex,0);
  let time=document.documentElement.dataset.motion==='off'?5.2:0,pose=sampleDance(time),last=0,raf=0,timer=0,frames=0,active=false,alive=true,visible=true,ending=null,cost=0;
  const quiet=()=>document.documentElement.dataset.motion==='off';
  function draw(){
   if(!alive||!canvas.width||!canvas.height)return;const began=performance.now();
   gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
   const ratio=canvas.width/canvas.height,art=2/3;gl.uniform2f(u.Fit,ratio>art?art/ratio:1,ratio>art?1:ratio/art);
   gl.uniform2f(u.Origin,pose.x,pose.y);gl.uniform2f(u.Shoulder,pose.leftShoulder,pose.rightShoulder);gl.uniform2f(u.Elbow,pose.leftElbow,pose.rightElbow);gl.uniform2f(u.Wrist,pose.leftWrist,pose.rightWrist);
   gl.uniform3fv(u.LegL,pose.legs[0]);gl.uniform3fv(u.LegR,pose.legs[1]);gl.uniform1f(u.Body,pose.body);gl.uniform1f(u.Head,pose.head);gl.uniform1f(u.Bow,pose.bow);gl.uniform1f(u.Hair,pose.hair);gl.uniform1f(u.Time,time);
   for(const mesh of meshes){
    const alpha=mesh.kind<-1.5?pose.alpha*ease((time-.6)/.8)*(1-ease((time-RETURN)/1.3)):mesh.kind<0?pose.seated:mesh.kind===0?pose.moon:pose.alpha;if(alpha<.001)continue;
    gl.uniform1f(u.Kind,mesh.kind);gl.uniform1f(u.Alpha,alpha);gl.uniform4fv(u.Rect,mesh.rect);gl.bindTexture(gl.TEXTURE_2D,mesh.tex);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.buffer);gl.vertexAttribPointer(attribute,2,gl.FLOAT,false,0,0);gl.drawArrays(gl.TRIANGLES,0,mesh.count);
   }
   frames++;cost=cost*.8+(performance.now()-began)*.2;
  }
  function canRun(){return alive&&visible&&!document.hidden&&!quiet()&&host.getClientRects().length>0&&!host.closest('[hidden]');}
  function stop(){cancelAnimationFrame(raf);clearTimeout(timer);raf=timer=last=0;active=false;}
  function tick(now){
   raf=timer=0;if(!canRun()){active=false;return;}active=true;
   const dt=last?Math.min((now-last)/1000,.08):1/24;last=now;time+=dt;
   if(time>=END){dispose();return;}
   pose=sampleDance(time);
   if(ending){ending.elapsed+=dt;const q=ease(ending.elapsed/.4);for(const key of Object.keys(pose))if(typeof pose[key]==='number')pose[key]=mix(ending.from[key],pose[key],q);pose.legs=[solveLeg(LEGS[0],[pose.footLX,pose.footLY],pose.body,pose.footLA),solveLeg(LEGS[1],[pose.footRX,pose.footRY],pose.body,pose.footRA)];if(q>=1)ending=null;}
   draw();const fps=cost>18?15:matchMedia('(max-width:700px)').matches?18:24;timer=setTimeout(()=>{raf=requestAnimationFrame(tick);},Math.max(0,1000/fps-cost-4));
  }
  function sync(){stop();if(canRun())raf=requestAnimationFrame(tick);else if(visible&&!document.hidden)draw();}
  function resize(){const r=host.getBoundingClientRect();if(!r.width||!r.height)return;const dpr=Math.min(devicePixelRatio||1,matchMedia('(max-width:700px)').matches?1.35:1.5);canvas.width=Math.round(r.width*dpr);canvas.height=Math.round(r.height*dpr);draw();}
  function finish(){if(!alive||time>=RETURN)return;if(quiet()){dispose();return;}ending={from:pose,elapsed:0};time=RETURN;onState?.('return');sync();}
  function escape(e){if(e.key==='Escape')finish();}
  function pageHide(e){if(e.persisted)stop();else dispose(false);}
  function pageShow(e){if(e.persisted&&alive)sync();}
  function dispose(notify=true){
   if(!alive)return;stop();alive=false;size.disconnect();view.disconnect();settings.disconnect();document.removeEventListener('visibilitychange',sync);window.removeEventListener('keydown',escape);window.removeEventListener('pagehide',pageHide);window.removeEventListener('pageshow',pageShow);
   meshes.forEach(m=>{gl.deleteTexture(m.tex);gl.deleteBuffer(m.buffer);});gl.deleteProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);canvas.remove();if(!gl.isContextLost())gl.getExtension('WEBGL_lose_context')?.loseContext();seated.width=seated.height=0;
   if(notify)onFinish();
  }
  host.append(canvas);
  const size=new ResizeObserver(resize);size.observe(host);
  const view=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05});view.observe(host);
  const settings=new MutationObserver(sync);settings.observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
  document.addEventListener('visibilitychange',sync);window.addEventListener('keydown',escape);window.addEventListener('pagehide',pageHide);window.addEventListener('pageshow',pageShow);
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();dispose();});
  const api={finish,sync,dispose,stats:()=>({playing:alive,active,frames,time,phase:pose.phase,drawCalls:8,triangles:meshes.reduce((n,m)=>n+m.count/3,0),leftShoulder:pose.leftShoulder,rightShoulder:pose.rightShoulder,leftKnee:pose.legs[0][1],rightKnee:pose.legs[1][1],leftFoot:pose.footLY,rightFoot:pose.footRY,root:{x:pose.x,y:pose.y}})};
  onState?.('dance');resize();sync();return api;
 }
}
