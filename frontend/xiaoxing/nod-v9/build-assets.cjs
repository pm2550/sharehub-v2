const {launch}=require('../browser-fixture.cjs');
const fs=require('fs'),path=require('path'),root=__dirname;
(async()=>{const browser=await launch(),page=await browser.newPage();
await page.route('http://127.0.0.1:8090/nod-build',r=>r.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));
await page.route('http://127.0.0.1:8090/nod-source.png',r=>r.fulfill({path:root+'/../nod-v8/nod-atlas-generated.png'}));
await page.goto('http://127.0.0.1:8090/nod-build');
const result=await page.evaluate(async()=>{
 const [atlas,original,old]=await Promise.all(['/nod-source.png','/static/images/sharehub-muse-800.webp','/static/images/xiaoxing-nod-atlas-v8.webp'].map(async src=>{const i=new Image();i.src=src;await i.decode();return i;}));
 const out=document.createElement('canvas');out.width=1200;out.height=640;const oc=out.getContext('2d');
 const mask=document.createElement('canvas');mask.width=400;mask.height=320;
 const mc=mask.getContext('2d');mc.filter='blur(3px)';
 // Covers BOTH silhouettes including the crown, star, flower and ribbon.
 // Its feathered lower edge lies on hair/neck, never on a facial feature.
 mc.fill(new Path2D('M-16 -16 H416 V190 L370 190 C335 210 325 245 294 264 C275 278 255 291 246 304 Q233 320 213 314 L187 299 L162 268 Q115 261 88 227 L80 191 L32 182 L-16 182 Z'));
 const side=document.createElement('canvas');side.width=800;side.height=1920;const sc=side.getContext('2d');sc.fillStyle='#241d33';sc.fillRect(0,0,800,1920);
 const size=atlas.naturalWidth/3,probes=[];
 for(let i=0;i<6;i++){
  const patch=document.createElement('canvas');patch.width=400;patch.height=320;const pc=patch.getContext('2d');
  pc.drawImage(atlas,i%3*size,Math.floor(i/3)*size,size,size*.8,0,0,400,320);
  const raw=pc.getImageData(0,0,400,320).data;
  pc.globalCompositeOperation='destination-in';pc.drawImage(mask,0,0);
  const frame=document.createElement('canvas');frame.width=400;frame.height=320;const fc=frame.getContext('2d');
  fc.drawImage(original,300,0,400,320,0,0,400,320);
  const orig=fc.getImageData(0,0,400,320).data;
  fc.globalCompositeOperation='destination-out';fc.drawImage(mask,0,0);
  // Add premultiplied complements. source-over would attenuate the seam twice.
  fc.globalCompositeOperation='lighter';fc.drawImage(patch,0,0);
  oc.drawImage(frame,i%3*400,Math.floor(i/3)*320);
  sc.drawImage(original,300,0,400,320,0,i*320,400,320);sc.drawImage(old,i%3*400,Math.floor(i/3)*320,400,320,0,i*320,400,320);
  sc.drawImage(frame,400,i*320);
  const pixels=fc.getImageData(0,0,400,320).data;
  let removedOldCrown=0,residual=0;const examples=[];
  for(let y=0;y<70;y++)for(let x=0;x<400;x++){const p=(y*400+x)*4;if(orig[p+3]>230&&raw[p+3]<10){removedOldCrown++;if(pixels[p+3]>12)residual++;if(examples.length<8)examples.push({x:x+300,y,oldAlpha:orig[p+3],newAlpha:raw[p+3],compositeAlpha:pixels[p+3]});}}
  probes.push({cell:i,removedOldCrown,residual,examples});
 }
 return {png:out.toDataURL('image/png').split(',')[1],comparison:side.toDataURL('image/png').split(',')[1],probes};
});
fs.writeFileSync(root+'/nod-complete-tiles.png',Buffer.from(result.png,'base64'));
fs.writeFileSync(root+'/before-after.png',Buffer.from(result.comparison,'base64'));
fs.writeFileSync(root+'/crown-probes.json',JSON.stringify(result.probes,null,2));
console.log(JSON.stringify(result.probes.map(({cell,removedOldCrown,residual})=>({cell,removedOldCrown,residual}))));
await browser.close();})().catch(e=>{console.error(e);process.exit(1)});
