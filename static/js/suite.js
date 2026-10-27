/* Site controls; shared interfaces keep backend contracts unchanged. */
(() => {
 'use strict';
 const drawer=document.getElementById('nav-drawer'), toggle=document.getElementById('hamburger-btn'), backdrop=document.getElementById('nav-drawer-backdrop');
 const mobile=matchMedia('(max-width: 900px)');
 function setDrawer(open) {
  drawer?.classList.toggle('open',open);backdrop?.classList.toggle('open',open);document.body.classList.toggle('nav-open',open);
  toggle?.setAttribute('aria-expanded',String(open));toggle?.setAttribute('aria-label',open?'关闭导航菜单':'打开导航菜单');
  if(drawer) drawer.inert=mobile.matches&&!open;
  if(open) drawer?.querySelector('a')?.focus();
 }
 toggle?.addEventListener('click',()=>setDrawer(!drawer.classList.contains('open')));
 backdrop?.addEventListener('click',()=>{setDrawer(false);toggle?.focus();});
 mobile.addEventListener('change',()=>setDrawer(false));setDrawer(false);
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape') {
   if(drawer?.classList.contains('open')){setDrawer(false);toggle?.focus();}
   document.querySelectorAll('.account-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});
   closeCompanion();
   const deletion=document.getElementById('confirm-delete-modal');
   if(deletion?.classList.contains('on')) deletion.querySelector('[data-modal-close]')?.click();
   const share=document.getElementById('share-post-modal');
   if(share&&getComputedStyle(share).display!=='none')document.getElementById('close-share-modal')?.click();
  }
  if(event.key==='Tab'&&drawer?.classList.contains('open')) {
   const items=[toggle,...drawer.querySelectorAll('a,button,summary,input')].filter(el=>el&&el.getClientRects().length&&!el.disabled);
   const first=items[0],last=items[items.length-1];
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }
 });
 document.addEventListener('click',event=>document.querySelectorAll('.account-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
 const companion=document.getElementById('companion-trigger'),panel=document.getElementById('companion-panel');
 function closeCompanion(){if(!panel||panel.hidden)return;panel.hidden=true;companion.setAttribute('aria-expanded','false');}
 companion?.addEventListener('click',()=>{panel.hidden=!panel.hidden;companion.setAttribute('aria-expanded',String(!panel.hidden));});
 document.querySelector('[data-companion-close]')?.addEventListener('click',()=>{closeCompanion();companion.focus();});
 let hello=0;
 document.querySelector('.companion-hello')?.addEventListener('click',()=>{
  const lines=['嗨，我在这里！今天也一起发现美好吧。','给你一颗灵感星星，愿今天的创作顺顺利利。','喜欢的事物，值得再多看一眼。'];
  document.getElementById('companion-greeting').textContent=lines[hello++%lines.length];
  window.dispatchEvent(new CustomEvent('sharehub:avatar-action',{detail:'wave'}));
 });
 // Native password validation stays in charge; reveal state is explicit.
 document.querySelectorAll('input[type="password"]').forEach(input=>{
  const wrapper=document.createElement('div');wrapper.className='password-wrapper';input.parentNode.insertBefore(wrapper,input);wrapper.append(input);
  const button=document.createElement('button');button.type='button';button.className='password-toggle';button.textContent='显示';button.setAttribute('aria-label','显示密码');button.setAttribute('aria-pressed','false');
  button.addEventListener('click',()=>{const show=input.type==='password';input.type=show?'text':'password';button.textContent=show?'隐藏':'显示';button.setAttribute('aria-label',show?'隐藏密码':'显示密码');button.setAttribute('aria-pressed',String(show));});wrapper.append(button);
 });
 // Workspace tabs support links, reload, keyboard navigation and browser history.
 const tabs=[...document.querySelectorAll('[data-workspace-tab]')];
 function workspaceTab(name,history=true) {
  const target=tabs.find(tab=>tab.dataset.workspaceTab===name);if(!target)return;
  tabs.forEach(tab=>{const active=tab===target;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;const content=document.getElementById(tab.getAttribute('aria-controls'));content.hidden=!active;content.classList.toggle('active',active);});
  document.querySelectorAll('video[data-preview-src]').forEach(video=>video.pause());
  if(history&&location.hash!=='#'+name)window.history.pushState(null,'','#'+name);
 }
 window.switchTab=name=>workspaceTab(name);
 tabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>workspaceTab(tab.dataset.workspaceTab));
  tab.addEventListener('keydown',event=>{let next;if(['ArrowRight','ArrowDown'].includes(event.key))next=(index+1)%tabs.length;else if(['ArrowLeft','ArrowUp'].includes(event.key))next=(index-1+tabs.length)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();workspaceTab(tabs[next].dataset.workspaceTab);tabs[next].focus();});
 });
 if(tabs.length){workspaceTab(location.hash.slice(1)||'manage',false);window.addEventListener('hashchange',()=>workspaceTab(location.hash.slice(1)||'manage',false));window.addEventListener('popstate',()=>workspaceTab(location.hash.slice(1)||'manage',false));}
 document.querySelectorAll('[data-prompt-seed]').forEach(button=>button.addEventListener('click',()=>{
  const field=document.getElementById('prompt');
  if(!field){location.href='/login?next=/ai';return;}
  // Add to an existing idea rather than discarding someone's text.
  field.value=field.value.trim()?field.value.trim()+', '+button.dataset.promptSeed:button.dataset.promptSeed;
  field.dispatchEvent(new Event('input',{bubbles:true}));field.focus();
 }));
 // Poll only the small counters, never while this document is hidden.
 const counters=[['notification-badge','/api/notifications/unread-count'],['message-badge','/api/messages/unread-count']].filter(([id])=>document.getElementById(id));
 let checking=false;
 async function updateCounters(){if(document.hidden||checking)return;checking=true;await Promise.allSettled(counters.map(async([id,url])=>{const response=await fetch(url);if(!response.ok)return;const data=await response.json();const badge=document.getElementById(id);badge.hidden=!(data.count>0);badge.textContent=data.count>99?'99+':String(data.count||0);}));checking=false;}
 if(counters.length){updateCounters();const timer=setInterval(updateCounters,60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateCounters();});window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});}
 // Give custom modal panels the same keyboard focus behavior as the native upload dialog.
 document.querySelectorAll('.modal-backdrop[role="dialog"],.share-modal-overlay[role="dialog"]').forEach(modal=>{
  let previous=null,wasOpen=false;
  const visible=()=>modal.classList.contains('on')||(modal.classList.contains('share-modal-overlay')&&modal.style.display!=='none');
  new MutationObserver(()=>{const open=visible();if(open===wasOpen)return;wasOpen=open;if(open){previous=document.activeElement;modal.setAttribute('aria-modal','true');modal.querySelector('button,input')?.focus();}else{modal.removeAttribute('aria-modal');previous?.focus();}}).observe(modal,{attributes:true,attributeFilter:['class','style']});
  modal.addEventListener('keydown',event=>{if(event.key!=='Tab')return;const items=[...modal.querySelectorAll('button,input,a,textarea')].filter(el=>el.getClientRects().length&&!el.disabled);const first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}});
 });
})();
