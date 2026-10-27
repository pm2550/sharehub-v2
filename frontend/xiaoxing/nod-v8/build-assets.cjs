const {launch}=require('../browser-fixture.cjs');
const fs=require('fs'),path=require('path'),root=__dirname;
(async()=>{const browser=await launch(),page=await browser.newPage();
await page.route('http://127.0.0.1:8090/nod-build',r=>r.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));
await page.route('http://127.0.0.1:8090/nod-source.png',r=>r.fulfill({path:root+'/nod-atlas-generated.png'}));
await page.goto('http://127.0.0.1:8090/nod-build');
const png=await page.evaluate(async()=>{
 const atlas=new Image();atlas.src='/nod-source.png';await atlas.decode();
 const out=document.createElement('canvas');out.width=1200;out.height=640;const oc=out.getContext('2d');
 const mask=document.createElement('canvas');mask.width=400;mask.height=320;
 const mc=mask.getContext('2d');mc.filter='blur(6px)';
 mc.fill(new Path2D('M91 63 C108 38 182 32 220 52 C242 75 256 122 260 164 C264 200 245 231 221 250 L220 276 Q200 286 182 275 L162 255 Q116 260 89 230 L76 195 Q69 135 91 63 Z'));
 const size=atlas.naturalWidth/3;
 for(let i=0;i<6;i++){
  const p=document.createElement('canvas');p.width=400;p.height=320;const pc=p.getContext('2d');
  pc.drawImage(atlas,i%3*size,Math.floor(i/3)*size,size,size*.8,0,0,400,320);
  pc.globalCompositeOperation='destination-in';pc.drawImage(mask,0,0);
  oc.drawImage(p,i%3*400,Math.floor(i/3)*320);
 }
 return out.toDataURL('image/png').split(',')[1];
});
fs.writeFileSync(root+'/nod-heads-packed.png',Buffer.from(png,'base64'));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
