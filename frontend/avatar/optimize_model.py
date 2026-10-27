import struct,json,subprocess,gzip
from pathlib import Path
root=Path(__file__).parent;b=(root/'sample.vrm').read_bytes();n=struct.unpack_from('<I',b,12)[0];j=json.loads(b[20:20+n]);data=b[28+n:];images={}
for i,im in enumerate(j['images']):
 v=j['bufferViews'][im['bufferView']];source=root/f'tex-{i}.png';target=root/f'tex-{i}-web.png';source.write_bytes(data[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]);
 subprocess.run(['convert',str(source),'-resize','512x512>','-strip',str(target)],check=True);images[im['bufferView']]=target.read_bytes();im['mimeType']='image/png'
buf=bytearray()
for i,v in enumerate(j['bufferViews']):
 while len(buf)%4:buf.append(0)
 fragment=images.get(i,data[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]);v['byteOffset']=len(buf);v['byteLength']=len(fragment);buf.extend(fragment)
while len(buf)%4:buf.append(0)
j['buffers'][0]['byteLength']=len(buf)
payload=json.dumps(j,separators=(',',':'),ensure_ascii=False).encode();payload+=b' '*((-len(payload))%4)
vrm=struct.pack('<III',0x46546c67,2,28+len(payload)+len(buf))+struct.pack('<II',len(payload),0x4e4f534a)+payload+struct.pack('<II',len(buf),0x004e4942)+buf
out=root.parents[1]/'static/models';out.mkdir(parents=True,exist_ok=True);(out/'sharehub-companion.vrm').write_bytes(vrm);(out/'sharehub-companion.vrm.gz').write_bytes(gzip.compress(vrm,compresslevel=9,mtime=0))
(out/'README.md').write_text('''# Animated companion model\n\nSource: pixiv/three-vrm v3.5.5, VRM1_Constraint_Twist_Sample.vrm\nhttps://github.com/pixiv/three-vrm/blob/v3.5.5/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm\n\n(c) 2022 pixiv Inc. VRM Public License 1.0: https://vrm.dev/licenses/1.0/\nEmbedded metadata permits everyone, commercial use, modification and redistribution. Textures are resized to at most 512 px; embedded license metadata and author credits are retained. Gzip copy is decoded by the browser to reduce transfer size.\n\nThis is an authorized existing 3D model, not a rigged reconstruction of the separately generated site illustration.\n''')
print('optimized',len(vrm),'gzip transfer',(out/'sharehub-companion.vrm.gz').stat().st_size)
