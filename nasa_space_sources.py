import requests,re,html,json,subprocess,urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
out=Path('sources');out.mkdir(exist_ok=True)
session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
targets={
'solar':'https://svs.gsfc.nasa.gov/vis/a000000/a005200/a005223/20240210_AR13576M90_AIA304_PSF_stamped_1024p30.mp4',
'jupiter':'https://science.nasa.gov/asset/webb/pullout-of-aurora-observations-on-jupiter/',
'mars':'https://science.nasa.gov/resource/first-video-of-nasas-ingenuity-mars-helicopter-in-flight/'
}
manifest={}
for key,url in targets.items():
 try:
  if url.endswith('.mp4'): variants=[url]
  else:
   r=session.get(url,timeout=25);r.raise_for_status();s=r.text
   soup=BeautifulSoup(s,'html.parser')
   candidates=[]
   for el in soup.find_all(['a','video','source']):
    for prop in ['href','src','data-src','data-url']:
     v=el.get(prop)
     if v and '.mp4' in v.lower():candidates.append(urllib.parse.urljoin(url,html.unescape(v)))
   candidates+=re.findall(r'https?[^\s"\'<>]+?\.mp4(?:\?[^\s"\'<>]*)?',s)
   candidates=[c.replace('\\/','/') for c in candidates]
   candidates=list(dict.fromkeys(candidates))
   print('CANDIDATES',key,len(candidates), '\n'.join(candidates[:20]),flush=True)
   variants=sorted(candidates,key=lambda v:('4k' in v.lower(),'highres' in v.lower(),len(v)))
  status=[]
  for v in variants[:12]:
   try:
    t=out/(key+'.mp4');rr=session.get(v,timeout=(20,110),stream=True);rr.raise_for_status()
    print('TRY',key,rr.status_code,rr.url,flush=True)
    with t.open('wb') as f:
     size=0
     for part in rr.iter_content(1024*1024):
      f.write(part);size+=len(part)
      if size>200_000_000:raise RuntimeError('too large')
    q=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-of','json',str(t)],capture_output=True,text=True,timeout=25)
    if q.returncode!=0:raise RuntimeError('bad mp4 '+q.stderr[:160])
    info=json.loads(q.stdout)['format'];print('OK',key,size,info,flush=True)
    manifest[key]={'status':'ok','url':v,'bytes':size,'duration':info['duration']};break
   except Exception as e:
    print('FAIL',key,type(e).__name__,str(e)[:170],flush=True);status.append(str(e))
  else:manifest[key]={'status':'failed','errors':status[:3]}
 except Exception as e:
  print('FATAL',key,str(e),flush=True);manifest[key]={'status':'failed','reason':str(e)}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('MANIFEST',json.dumps(manifest,ensure_ascii=False),flush=True)