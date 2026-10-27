import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {VRMLoaderPlugin,VRMUtils} from '@pixiv/three-vrm';

export async function mountAvatar(host) {
 const compact=host.dataset.avatarSize==='compact';
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power',precision:'mediump'});
 renderer.setPixelRatio(Math.min(devicePixelRatio||1,matchMedia('(max-width:700px)').matches?1:1.35));
 renderer.setClearColor(0x000000,0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 renderer.domElement.className='avatar-canvas';renderer.domElement.setAttribute('aria-label','可以眨眼、转头和挥手的三维小星');renderer.domElement.setAttribute('role','img');
 const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xfff5ff,0x9b8eae,2.3));
 const key=new THREE.DirectionalLight(0xfff5ed,2.1);key.position.set(-1,2,3);scene.add(key);
 const camera=new THREE.PerspectiveCamera(28,1,.1,20);camera.position.set(0,.94,3.9);camera.lookAt(0,.86,0);
 const response=await fetch('/static/models/sharehub-companion.vrm'+('DecompressionStream' in window?'.gz':''));
 if(!response.ok){renderer.dispose();throw new Error('角色素材暂时无法加载');}
 const bytes='DecompressionStream' in window?await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():await response.arrayBuffer();
 const loader=new GLTFLoader();loader.register(parser=>new VRMLoaderPlugin(parser));
 let gltf;
 try {gltf=await loader.parseAsync(bytes,'/static/models/');}catch(error){renderer.dispose();throw error;}
 const vrm=gltf.userData.vrm;VRMUtils.rotateVRM0(vrm);scene.add(vrm.scene);
 vrm.scene.traverse(node=>{if(node.isMesh){node.frustumCulled=false;node.castShadow=false;node.receiveShadow=false;}});
 const bones={};for(const name of ['hips','spine','chest','neck','head','leftUpperArm','rightUpperArm','leftLowerArm','rightLowerArm','leftHand','rightHand'])bones[name]=vrm.humanoid.getNormalizedBoneNode(name);
 // A lavender shirt and a tiny star clip connect the licensed model to the site identity.
 const visitedMaterials=new Set();vrm.scene.traverse(node=>{if(!node.isMesh)return;for(const material of [].concat(node.material||[])){if(visitedMaterials.has(material))continue;visitedMaterials.add(material);if(material.name.includes('Tops_01_CLOTH'))material.color?.set('#cbb9e3');}});
 const starShape=new THREE.Shape();for(let i=0;i<10;i++){const angle=Math.PI/2+i*Math.PI/5,r=i%2?.012:.026;const x=Math.cos(angle)*r,y=Math.sin(angle)*r;i?starShape.lineTo(x,y):starShape.moveTo(x,y);}starShape.closePath();
 const clip=new THREE.Mesh(new THREE.ExtrudeGeometry(starShape,{depth:.006,bevelEnabled:false}),new THREE.MeshStandardMaterial({color:0xe8c994,metalness:.15,roughness:.7}));clip.position.set(.087,.115,.077);clip.rotation.z=-.2;vrm.humanoid.getRawBoneNode('head')?.add(clip);
 const gaze=new THREE.Object3D();gaze.position.set(0,1.35,3);scene.add(gaze);if(vrm.lookAt)vrm.lookAt.target=gaze;
 const expression=vrm.expressionManager;
 let time=0,last=0,timer=0,raf=0,visible=true,destroyed=false,action=null,frames=0,active=false;
 let cap=matchMedia('(max-width:700px)').matches?24:30,renderCost=0;
 const pointer={x:0,y:0},head={x:0,y:0};
 const rotate=(name,x=0,y=0,z=0)=>bones[name]?.rotation.set(x,y,z);
 const lerp=THREE.MathUtils.lerp;
 function pose(delta) {
  time+=delta;
  const ease=1-Math.exp(-delta*7);head.x=lerp(head.x,pointer.x,ease);head.y=lerp(head.y,pointer.y,ease);
  rotate('neck');
  rotate('leftUpperArm',0,0,-1.16);rotate('rightUpperArm',0,0,1.16);
  rotate('leftLowerArm',-.07,0,-.08);rotate('rightLowerArm',-.07,0,.08);
  rotate('leftHand',0,.08,0);rotate('rightHand',0,-.08,0);
  rotate('spine',.012*Math.sin(time*1.5),0,.009*Math.sin(time*.8));
  rotate('chest',.013*Math.sin(time*1.5),0,0);
  rotate('head',head.y*.12,head.x*.23,.014*Math.sin(time*.7));
  gaze.position.set(head.x*.8,1.4-head.y*.4,3);
  const blinkPhase=time%4.9;let blink=blinkPhase>4.62?Math.sin((blinkPhase-4.62)/.28*Math.PI):0;
  expression.setValue('blink',Math.max(0,blink));expression.setValue('blinkLeft',0);expression.setValue('happy',.08);expression.setValue('relaxed',.06);expression.setValue('aa',0);
  if(action){
   action.elapsed+=delta;const t=action.elapsed,d=action.duration;
   const envelope=Math.min(1,t/.45,(d-t)/.45);const w=Math.max(0,envelope);const smooth=w*w*(3-2*w);
   if(action.name==='wave'){
    rotate('rightUpperArm',-.12*smooth,0,lerp(1.16,-.12,smooth));
    rotate('rightLowerArm',0,-.18*smooth,lerp(.08,-1.5,smooth));
    rotate('rightHand',0,-.15,Math.sin(t*12)*.25*smooth);
    rotate('head',head.y*.08,head.x*.1,-.08*smooth);
    expression.setValue('happy',.24*smooth+.08);expression.setValue('aa',.12*Math.max(0,Math.sin(t*5))*smooth);
   }else if(action.name==='nod'){
    rotate('neck',.16*Math.sin(t*6)*smooth,0,0);expression.setValue('happy',.25*smooth);
   }else if(action.name==='wink'){
    expression.setValue('blink',0);expression.setValue('blinkLeft',smooth);expression.setValue('happy',.16*smooth);rotate('head',0,head.x*.1,-.12*smooth);
   }else if(action.name==='smile'){expression.setValue('happy',.8*smooth);rotate('head',.06*smooth,0,.06*smooth);}
   if(t>=d){action=null;rotate('neck');}
  }
  vrm.update(Math.min(delta,.06));
 }
 function canAnimate(){return !destroyed&&visible&&!document.hidden&&document.documentElement.dataset.motion!=='off'&&!host.closest('[hidden]')&&host.getClientRects().length>0;}
 function draw(){if(destroyed)return;const start=performance.now();renderer.render(scene,camera);renderCost=renderCost*.85+(performance.now()-start)*.15;frames++;if(renderCost>20)cap=18;}
 function tick(now){timer=0;raf=0;if(!canAnimate()){active=false;return;}active=true;const delta=last?Math.min((now-last)/1000,.07):1/cap;last=now;pose(delta);draw();timer=setTimeout(()=>{raf=requestAnimationFrame(tick);},Math.max(0,1000/(action?cap:Math.min(cap,12))-renderCost-5));}
 function stop(){clearTimeout(timer);cancelAnimationFrame(raf);timer=raf=0;last=0;active=false;}
 function sync(){stop();if(canAnimate()){raf=requestAnimationFrame(tick);}else if(visible&&!document.hidden){pose(0);draw();}}
 function resize(){const rect=host.getBoundingClientRect();if(!rect.width||!rect.height)return;renderer.setSize(rect.width,rect.height,false);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();draw();}
 function setAction(name){if(!['wave','nod','wink','smile'].includes(name))return;action={name,elapsed:0,duration:name==='wave'?2.8:1.8};if(document.documentElement.dataset.motion==='off'){action.elapsed=action.duration/2;pose(0);draw();return;}sync();}
 function move(event){if(document.documentElement.dataset.motion==='off')return;const r=host.getBoundingClientRect();pointer.x=Math.max(-1,Math.min(1,(event.clientX-r.left-r.width/2)/(r.width/2)));pointer.y=Math.max(-1,Math.min(1,(event.clientY-r.top-r.height*.3)/(r.height*.6)));}
 host.appendChild(renderer.domElement);host.classList.add('avatar-ready');host.dataset.avatarState='ready';
 host.addEventListener('pointermove',move,{passive:true});host.addEventListener('pointerleave',()=>{pointer.x=pointer.y=0;});
 host.addEventListener('click',()=>setAction('wave'));
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();stop();host.dataset.avatarState='lost';host.classList.remove('avatar-ready');host.dispatchEvent(new CustomEvent('avatar-error',{bubbles:true}));});
 renderer.domElement.addEventListener('webglcontextrestored',()=>{host.classList.add('avatar-ready');host.dataset.avatarState='ready';sync();});
 const sizeObserver=new ResizeObserver(resize);sizeObserver.observe(host);
 const viewObserver=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05});viewObserver.observe(host);
 const motionObserver=new MutationObserver(sync);motionObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
 document.addEventListener('visibilitychange',sync);
 function externalAction(event){setAction(event.detail);}window.addEventListener('sharehub:avatar-action',externalAction);
 pose(0);resize();sync();setAction('wave');
 const api={action:setAction,sync,stats:()=>({frames,active,fpsCap:cap,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,action:action?.name||null,blink:expression.getValue('blink'),blinkLeft:expression.getValue('blinkLeft'),happy:expression.getValue('happy'),neck:bones.neck.rotation.toArray().slice(0,3),head: bones.head.rotation.toArray().slice(0,3),hand:bones.rightHand.rotation.toArray().slice(0,3),upperArm:bones.rightUpperArm.rotation.toArray().slice(0,3)})};
 window.ShareHubAvatar=api;
 window.addEventListener('pagehide',event=>{stop();if(event.persisted)return;destroyed=true;sizeObserver.disconnect();viewObserver.disconnect();motionObserver.disconnect();document.removeEventListener('visibilitychange',sync);window.removeEventListener('sharehub:avatar-action',externalAction);VRMUtils.deepDispose(vrm.scene);renderer.dispose();},{once:true});
 window.addEventListener('pageshow',event=>{if(event.persisted)sync();});
 return api;
}
