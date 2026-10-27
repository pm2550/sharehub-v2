/* Drawn nod cels. This player never translates, scales or warps the head.
   Each atlas cell is a complete replacement tile, including transparent background.
   Never overlay a semi-transparent head on the original head. */
const W=800,H=1200,CELL=400;
const CELLS=[-1,0,1,2,3,4,5,4,3,2,1,0,-1];
// Slow in, a short low hold, then an unhurried return. No looping or overshoot.
const HOLDS=[.10,.08,.09,.10,.10,.12,.16,.10,.11,.12,.10,.10,.20];
export const NOD_SECONDS=HOLDS.reduce((a,b)=>a+b,0);
export async function createNodPlayer(host,original) {
 const atlas=new Image();atlas.decoding='async';
 await new Promise((resolve,reject)=>{atlas.onload=resolve;atlas.onerror=()=>reject(new Error('Nod frames unavailable'));atlas.src='/static/images/xiaoxing-nod-atlas-v9.webp';});
 await atlas.decode();
 const canvas=document.createElement('canvas');canvas.className='avatar-nod-canvas';canvas.hidden=true;
 canvas.setAttribute('aria-hidden','true');
 const ctx=canvas.getContext('2d',{alpha:true});
 if(!ctx)throw new Error('2D canvas unavailable');
 let lastCell=null,draws=0,shown=false;
 host.append(canvas);
 function draw(seconds,width,height) {
  const resized=canvas.width!==width||canvas.height!==height;
  if(resized){canvas.width=width;canvas.height=height;}
  let elapsed=0,cell=-1;
  for(let i=0;i<CELLS.length;i++){elapsed+=HOLDS[i];if(seconds<elapsed){cell=CELLS[i];break;}}
  if(resized||cell!==lastCell||!shown){
   ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,width,height);
   const scale=Math.min(width/W,height/H);
   ctx.setTransform(scale,0,0,scale,(width-W*scale)/2,(height-H*scale)/2);
   ctx.drawImage(original,0,0,W,H);
   if(cell>=0){
    // Clear the original silhouette as well as the facial features. The tile
    // already contains the protected original pixels outside the moving head.
    ctx.clearRect(300,0,CELL,320);
    ctx.drawImage(atlas,(cell%3)*CELL,Math.floor(cell/3)*320,CELL,320,300,0,CELL,320);
   }
   draws++;lastCell=cell;
  }
  canvas.hidden=false;if(!shown)host.classList.add('avatar-nod-active');shown=true;
 }
 function hide(){if(!shown)return;canvas.hidden=true;host.classList.remove('avatar-nod-active');shown=false;lastCell=null;}
 function dispose(){host.classList.remove('avatar-nod-active');canvas.remove();canvas.width=canvas.height=0;atlas.src='';}
 return {draw,hide,dispose,stats:()=>({cell:lastCell,draws,shown,celCount:CELLS.length,duration:NOD_SECONDS})};
}
