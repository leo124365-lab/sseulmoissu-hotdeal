import requests,re,urllib.parse,html,subprocess,os,json
from bs4 import BeautifulSoup
os.makedirs("more",exist_ok=True)
urls={
"earth_aurora":"https://svs.gsfc.nasa.gov/vis/a030000/a031200/a031281/ISS067_20220817_aurora_1080p25.mp4",
"mars_parachute":"https://science.nasa.gov/resource/perseverance-rovers-descent-and-touchdown-on-mars-onboard-camera-views/"
}
r=requests.Session();r.headers["User-Agent"]="Mozilla/5.0"
for name,url in urls.items():
 options=[]
 if url.endswith(".mp4"):options=[url]
 else:
  raw=r.get(url,timeout=40).text; soup=BeautifulSoup(raw,"html.parser")
  for node in soup.find_all(["a","video","source"]):
   u=node.get("href") or node.get("src")
   if u and ".mp4" in u:
    print("CANDIDATE",node.get_text(" ",strip=True)[:150],u,flush=True)
    options.append(urllib.parse.urljoin(url,html.unescape(u)))
  options+=re.findall(r'https?[^\s"\'<>]+?\.mp4',raw)
  options=list(dict.fromkeys(c.replace('\\/','/') for c in options))
  options=sorted(options,key=lambda v:(not ("parachute" in v.lower() or "15sec" in v.lower() or "15-sec" in v.lower()),len(v)))
 for u in options[:12]:
  try:
   rr=r.get(u,stream=True,timeout=(30,120));rr.raise_for_status()
   dest="more/"+name+".mp4";sz=0
   with open(dest,"wb") as f:
    for b in rr.iter_content(1024*1024):
     f.write(b);sz+=len(b)
     if sz>220000000:raise ValueError("Too large")
   ff=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size","-of","json",dest],capture_output=True,text=True)
   if ff.returncode:raise ValueError(ff.stderr[:150])
   print("OK",name,sz,ff.stdout,u,flush=True);break
  except Exception as e: print("FAIL",name,str(e)[:150],flush=True)
