(() => {
 'use strict';
 const key='sharehub-theme',themes=['light','dark','system'],media=matchMedia('(prefers-color-scheme: dark)');
 let saved='system';try{saved=localStorage.getItem(key)||'system';}catch(_){}if(!themes.includes(saved))saved='system';
 function apply(theme){if(theme==='system')document.documentElement.removeAttribute('data-theme');else document.documentElement.dataset.theme=theme;}
 function icon(){const button=document.getElementById('theme-toggle');if(!button)return;const actual=saved==='system'?(media.matches?'dark':'light'):saved;button.textContent=actual==='dark'?'☾':'☼';const names={light:'浅色',dark:'深色',system:'跟随系统'};button.setAttribute('aria-label',`当前${names[saved]}，点击切换主题`);button.title=`主题：${names[saved]}`;}
 function toggle(){saved=themes[(themes.indexOf(saved)+1)%themes.length];try{localStorage.setItem(key,saved);}catch(_){}apply(saved);icon();}
 apply(saved);document.addEventListener('DOMContentLoaded',()=>{icon();document.getElementById('theme-toggle')?.addEventListener('click',toggle);});media.addEventListener('change',()=>{if(saved==='system')icon();});
 window.ThemeManager={toggle,getCurrent:()=>saved,apply};
})();
