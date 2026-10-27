/* The original-art 2D runtime is loaded only for an on-screen, enabled character. */
(() => {
 'use strict';
 const host=document.querySelector('.avatar-stage');if(!host)return;
 const status=host.querySelector('.avatar-status'),button=host.querySelector('[data-avatar-load]');
 const companion=document.querySelector('.site-companion'),compact=host.dataset.avatarSize==='compact';
 let runtime=null,loading=null,attempted=false;
 function quiet(){return document.documentElement.dataset.motion==='off'||navigator.connection?.saveData;}
 async function load(explicit=false){
  if(runtime){runtime.sync();return;}if(loading)return loading;if(!explicit&&quiet())return;
  attempted=true;host.dataset.avatarState='loading';button.disabled=true;status.textContent='小星正在赶来…';
  loading=(async()=>{try{const module=await import('/static/js/xiaoxing-2d.js?v=20260926-9');runtime=await module.mountXiaoxing(host);button.hidden=true;status.textContent='';}
  catch(error){host.dataset.avatarState='error';status.textContent='暂时无法唤醒，仍可继续浏览。';button.disabled=false;button.textContent='再试一次';console.warn('Character unavailable:',error.message);}
  finally{loading=null;}})();
  return loading;
 }
 button.addEventListener('click',event=>{event.stopPropagation();load(true);});
 host.addEventListener('keydown',event=>{if(event.target!==host||!['Enter',' '].includes(event.key))return;event.preventDefault();if(runtime)runtime.action('wave');else load(true);});
 document.querySelectorAll('[data-avatar-action]').forEach(control=>control.addEventListener('click',async()=>{
  await load(true);const accepted=await runtime?.action(control.dataset.avatarAction);if(accepted===false)return;
  const target=document.getElementById('mascot-message')||document.getElementById('companion-greeting');
  if(target)target.textContent={wave:'你好呀，很高兴见到你！',wink:'送你一颗灵感星星 ✦',smile:'见到你，心情都变好了。',nod:'嗯嗯，我在认真听呢。',tilt:'嗯？你发现什么有趣的东西啦？',star:'接住！今天的灵感星星送给你 ✦'}[control.dataset.avatarAction];
 }));
 document.querySelector('.avatar-minimize')?.addEventListener('click',()=>{companion.classList.add('avatar-minimized');companion.classList.remove('companion-expanded');runtime?.sync();});
 document.getElementById('companion-trigger')?.addEventListener('click',()=>{companion.classList.remove('avatar-minimized');companion.classList.add('companion-expanded');load();});
 host.addEventListener('avatar-error',()=>{status.textContent='角色暂时休息了，请刷新页面重试。';});
 const observer=new IntersectionObserver(entries=>{if(entries[0].isIntersecting&&!attempted&&!quiet()){
  const start=()=>{if(host.getClientRects().length&&!document.hidden)load();};
  if('requestIdleCallback'in window)requestIdleCallback(start,{timeout:1500});else setTimeout(start,350);
 }},{threshold:.1});observer.observe(host);
 new MutationObserver(()=>{if(!quiet()&&!attempted&&host.getClientRects().length)load();}).observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
})();
