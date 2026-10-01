#!/usr/bin/env python3
"""Private backend. Python 3.12 stdlib, SQLite, OAuth refresh, SMTP, Meta webhook.
Run behind a TLS reverse proxy; config and database must be outside the web root.
"""
import argparse,datetime as dt,email.message,hashlib,hmac,http.server,json,os,re,secrets,smtplib,sqlite3,ssl,threading,time,urllib.parse,urllib.request,urllib.error,uuid
from zoneinfo import ZoneInfo
from pathlib import Path
UTC=dt.timezone.utc
def now():return dt.datetime.now(UTC)
def iso(d):return d.astimezone(UTC).isoformat()
def parse(s):
 d=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('Timezone required')
 return d.astimezone(UTC)
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
class ApiError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message
def http_json(url,data=None,headers=None,method=None):
 request=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**(headers or {})},method=method)
 with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
class Google:
 def __init__(self,c):self.c=c;self.token=None;self.until=0;self.lock=threading.Lock()
 def auth(self):
  with self.lock:
   if time.time()<self.until:return self.token
   data=urllib.parse.urlencode({'client_id':self.c['clientId'],'client_secret':self.c['clientSecret'],'refresh_token':self.c['refreshToken'],'grant_type':'refresh_token'}).encode()
   with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data),timeout=15) as response:result=json.load(response)
   self.token=result['access_token'];self.until=time.time()+result.get('expires_in',3600)-60
   return self.token
 def call(self,path,data=None,method=None,query=None):
  url='https://www.googleapis.com/calendar/v3/calendars/'+urllib.parse.quote(self.c['calendarId'],safe='')+'/events'+path
  if query:url+='?'+urllib.parse.urlencode(query)
  return http_json(url,data,{'Authorization':'Bearer '+self.auth()},method)
 def events(self):
  params={'timeMin':iso(now()),'timeMax':iso(now()+dt.timedelta(days=120)),'singleEvents':'true','orderBy':'startTime','maxResults':2500}
  result=[]
  for _ in range(20):
   page=self.call('',query=params);result.extend(page.get('items',[]))
   if not page.get('nextPageToken'):return result
   params['pageToken']=page['nextPageToken']
  raise ApiError(503,'calendar_too_large')
 def sync(self,b,status):
  eid='hj'+b['id'].replace('-','')
  if status in ('cancelled','declined','expired'):
   try:self.call('/'+eid,method='DELETE',query={'sendUpdates':'all'})
   except urllib.error.HTTPError as ex:
    if ex.code not in (404,410):raise
   return
  event={'id':eid,'summary':('Jelentkezés – ' if status=='pending' else 'Találkozó – ')+b['name'],'description':'HJ foglalás: '+b['id'],'start':{'dateTime':b['start'],'timeZone':self.c['timezone']},'end':{'dateTime':b['end'],'timeZone':self.c['timezone']},'status':'tentative' if status=='pending' else 'confirmed','visibility':'private','guestsCanInviteOthers':False,'guestsCanModify':False,'guestsCanSeeOtherGuests':False,'extendedProperties':{'private':{'hjBooking':b['id'],'hjSlot':b['slotId']}}}
  if status=='confirmed':event['attendees']=[{'email':b['email'],'responseStatus':'needsAction'}]
  try:self.call('',event,method='POST',query={'sendUpdates':'all' if status=='confirmed' else 'none'})
  except urllib.error.HTTPError as ex:
   if ex.code!=409:raise
   update=dict(event);update.pop('id');update.setdefault('attendees',[])
   self.call('/'+eid,update,method='PUT',query={'sendUpdates':'all' if status=='confirmed' else 'none'})
class Store:
 def __init__(self,c,content,google=None,mailer=None):
  self.c=c;self.content=content;self.google=google or Google(c['google']);self.mailer=mailer or self.send_mail
  path=Path(c['database']);path.parent.mkdir(parents=True,exist_ok=True)
  with self.db() as db:db.executescript('''
   PRAGMA journal_mode=WAL;
   CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY,slotId TEXT,serviceId TEXT,name TEXT,email TEXT,start TEXT,end TEXT,price INTEGER,status TEXT,baby INTEGER,tokenHash TEXT,expiresAt TEXT,createdAt TEXT);
   CREATE INDEX IF NOT EXISTS slot_status ON bookings(slotId,status);
   CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY,payloadHash TEXT,response TEXT);
   CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,name TEXT,email TEXT,topic TEXT,message TEXT,createdAt TEXT);
   CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,payload TEXT,bookingId TEXT,attempts INTEGER DEFAULT 0,readyAt REAL,done INTEGER DEFAULT 0,lastError TEXT);
   CREATE TABLE IF NOT EXISTS rates(ipHash TEXT,at REAL);
   CREATE TABLE IF NOT EXISTS webhook_ids(id TEXT PRIMARY KEY,createdAt REAL);
  ''')
  try:os.chmod(path,0o600)
  except OSError:pass
  self.worker_lock=threading.Lock()
 def db(self):
  db=sqlite3.connect(self.c['database'],timeout=30);db.row_factory=sqlite3.Row;return db
 def queue(self,db,kind,payload,booking_id=None,ready_at=None):db.execute('INSERT INTO outbox(kind,payload,bookingId,readyAt) VALUES(?,?,?,?)',(kind,json.dumps(payload),booking_id,ready_at or time.time()))
 def approved(self):
  if not self.c.get('contentApproved') or not self.c.get('legalApproved'):raise ApiError(503,'launch_not_approved')
 def rate(self,ip):
  key=hmac.new(self.c['ipHashSalt'].encode(),ip.encode(),'sha256').hexdigest()
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');db.execute('DELETE FROM rates WHERE at<?',(time.time()-3600,))
   if db.execute('SELECT COUNT(*) FROM rates WHERE ipHash=?',(key,)).fetchone()[0]>=self.c.get('rateLimitPerHour',10):raise ApiError(429,'too_many_requests')
   db.execute('INSERT INTO rates VALUES(?,?)',(key,time.time()))
 def expire(self):
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE')
   for row in db.execute("SELECT * FROM bookings WHERE status='pending' AND expiresAt<?",(iso(now()),)).fetchall():
    b=dict(row);db.execute("UPDATE bookings SET status='expired' WHERE id=?",(b['id'],));self.queue(db,'google',{'id':b['id'],'status':'expired'},b['id']);self.queue(db,'mail',{'id':b['id'],'status':'expired'},b['id'])
 def list_slots(self):
  self.approved();self.expire();events=self.google.events();services={x['id']:x for x in self.content['offers']['items']}
  with self.db() as db:
   used={r['slotId']:r['n'] for r in db.execute("SELECT slotId,COUNT(*) n FROM bookings WHERE status IN ('pending','confirmed') GROUP BY slotId")}
   known={'hj'+r['id'].replace('-','') for r in db.execute('SELECT id FROM bookings')}
  candidate=[];busy=[]
  for event in events:
   if event.get('status')=='cancelled' or event.get('id') in known:continue
   title=event.get('summary','');is_slot=title.startswith(self.c['google']['slotPrefix'])
   start=event.get('start',{}).get('dateTime');end=event.get('end',{}).get('dateTime')
   if is_slot:
    try:
     raw=event.get('description','').strip();params=json.loads(raw)
     service=services[params['service']];capacity=int(params.get('capacity',1 if service['id']=='coaching' else 6))
     if not start or not end or capacity<1 or capacity>20 or (service['id']=='coaching' and capacity!=1):continue
     duration=int(service['duration'].split()[0]);s=parse(start);en=parse(end)
     if s<=now() or en-s!=dt.timedelta(minutes=duration):continue
     candidate.append({'id':event['id'],'serviceId':service['id'],'title':service['title'],'start':iso(s),'end':iso(en),'price':service['price'],'capacity':capacity,'available':max(0,capacity-used.get(event['id'],0))})
    except (ValueError,KeyError,TypeError):continue
   elif event.get('transparency')!='transparent':
    try:
     zone=ZoneInfo(self.c['google']['timezone'])
     s=parse(start) if start else dt.datetime.combine(dt.date.fromisoformat(event['start']['date']),dt.time(),zone).astimezone(UTC)
     en=parse(end) if end else dt.datetime.combine(dt.date.fromisoformat(event['end']['date']),dt.time(),zone).astimezone(UTC)
     busy.append((s,en))
    except (KeyError,ValueError,TypeError):raise ApiError(503,'invalid_calendar_event')
  return [s for s in candidate if not any(parse(s['start'])<en and parse(s['end'])>st for st,en in busy)]
 def validate(self,data):
  if data.get('website'):raise ApiError(400,'invalid_submission')
  name=str(data.get('name','')).strip();address=str(data.get('email','')).strip()
  if not 2<=len(name)<=100 or any(ord(x)<32 for x in name) or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',address) or len(address)>200 or data.get('privacy') is not True:raise ApiError(400,'invalid_submission')
  return name,address
 def existing(self,db,key,payload):
  if not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}',key):raise ApiError(400,'invalid_idempotency_key')
  row=db.execute('SELECT * FROM idempotency WHERE key=?',(key,)).fetchone()
  if row:
   if row['payloadHash']!=digest(json.dumps(payload,sort_keys=True)):raise ApiError(409,'idempotency_payload_changed')
   return json.loads(row['response'])
 def remember(self,db,key,payload,response):db.execute('INSERT INTO idempotency VALUES(?,?,?)',(key,digest(json.dumps(payload,sort_keys=True)),json.dumps(response)))
 def book(self,data,key):
  self.approved();name,address=self.validate(data)
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');existing=self.existing(db,key,data)
   if existing:return existing
  slot=next((s for s in self.list_slots() if s['id']==data.get('slotId')),None)
  if not slot:raise ApiError(409,'slot_unavailable')
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');existing=self.existing(db,key,data)
   if existing:return existing
   used=db.execute("SELECT COUNT(*) FROM bookings WHERE slotId=? AND status IN ('pending','confirmed')",(slot['id'],)).fetchone()[0]
   if used>=slot['capacity']:raise ApiError(409,'slot_full')
   token=secrets.token_urlsafe(32);bid=uuid.uuid4().hex
   b={'id':bid,'slotId':slot['id'],'serviceId':slot['serviceId'],'name':name,'email':address,'start':slot['start'],'end':slot['end'],'price':slot['price'],'status':'pending','baby':int(bool(data.get('baby'))),'tokenHash':digest(token),'expiresAt':iso(now()+dt.timedelta(hours=self.c.get('pendingHours',48))),'createdAt':iso(now())}
   db.execute('INSERT INTO bookings VALUES('+','.join('?' for _ in b)+')',tuple(b.values()))
   response={k:v for k,v in b.items() if k not in ('tokenHash','baby','createdAt')};response['token']=token
   self.remember(db,key,data,response);self.queue(db,'google',{'id':bid,'status':'pending'},bid);self.queue(db,'mail',{'id':bid,'status':'pending','token':token},bid)
   return response
 def contact(self,data,key):
  self.approved();name,address=self.validate(data);message=str(data.get('message','')).strip();topic=str(data.get('topic',''))
  if len(message)>1000 or topic not in self.content['contact']['topics']:raise ApiError(400,'invalid_submission')
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');existing=self.existing(db,key,data)
   if existing:return existing
   cid=uuid.uuid4().hex;db.execute('INSERT INTO contacts VALUES(?,?,?,?,?,?)',(cid,name,address,topic,message,iso(now())))
   response={'id':cid,'status':'received'};self.remember(db,key,data,response);self.queue(db,'contact-mail',{'id':cid});return response
 def get_booking(self,bid,token=None,admin=False):
  with self.db() as db:row=db.execute('SELECT * FROM bookings WHERE id=?',(bid,)).fetchone()
  if not row or (not admin and not hmac.compare_digest(row['tokenHash'],digest(token or ''))):raise ApiError(404,'booking_not_found')
  return {k:v for k,v in dict(row).items() if k!='tokenHash'}
 def transition(self,bid,target,token=None,admin=False):
  self.expire();b=self.get_booking(bid,token,admin)
  if target=='confirmed':
   slot=next((s for s in self.list_slots() if s['id']==b['slotId']),None)
   if not slot or parse(b['start'])<=now():raise ApiError(409,'slot_no_longer_available')
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');current=db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0]
   if current==target:return self.get_booking(bid,token,admin)
   allowed={'confirmed':['pending'],'declined':['pending'],'cancelled':['pending','confirmed']}
   if target not in allowed or current not in allowed[target] or (target!='cancelled' and not admin):raise ApiError(409,'invalid_transition')
   db.execute('UPDATE bookings SET status=? WHERE id=?',(target,bid));self.queue(db,'google',{'id':bid,'status':target},bid);self.queue(db,'mail',{'id':bid,'status':target},bid)
   if target=='confirmed':
    reminder=parse(b['start']).timestamp()-24*3600
    if reminder>time.time():self.queue(db,'mail',{'id':bid,'status':'reminder'},bid,reminder)
  return self.get_booking(bid,token,admin)
 def send_mail(self,to,subject,body,ics=None):
  c=self.c['smtp'];msg=email.message.EmailMessage();msg['From']=c['from'];msg['To']=to;msg['Subject']=subject;msg.set_content(body)
  if ics:msg.add_attachment(ics.encode(),maintype='text',subtype='calendar',filename='idopont.ics')
  cls=smtplib.SMTP_SSL if c.get('implicitTLS') else smtplib.SMTP
  with cls(c['host'],c['port'],timeout=20) as smtp:
   if not c.get('implicitTLS'):smtp.starttls(context=ssl.create_default_context())
   if c.get('username'):smtp.login(c['username'],c['password'])
   smtp.send_message(msg)
 def ics(self,b):
  def fmt(s):return parse(s).strftime('%Y%m%dT%H%M%SZ')
  return '\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Hauber Judit//Booking//HU','METHOD:PUBLISH','BEGIN:VEVENT','UID:'+b['id']+'@hauberjudit.hu','DTSTAMP:'+fmt(iso(now())),'DTSTART:'+fmt(b['start']),'DTEND:'+fmt(b['end']),'SUMMARY:Találkozó Judittal','STATUS:CONFIRMED','END:VEVENT','END:VCALENDAR'])+'\r\n'
 def run_job(self,job):
  p=json.loads(job['payload']);kind=job['kind']
  if kind=='google':
   b=self.get_booking(p['id'],admin=True)
   if b['status']==p['status']:self.google.sync(b,p['status'])
   return
  if kind=='contact-mail':
   with self.db() as db:row=db.execute('SELECT * FROM contacts WHERE id=?',(p['id'],)).fetchone()
   self.mailer(self.c['smtp']['ownerEmail'],'Új webes megkeresés',f"{row['name']} <{row['email']}>\n{row['topic']}\n\n{row['message']}")
   self.mailer(row['email'],'Megérkezett az üzeneted','Köszönöm a megkeresést! Általában egy napon belül válaszolok.\nÜdvözlettel: Judit');return
  if kind=='meta-reply':
   c=self.c['meta'];http_json('https://graph.facebook.com/'+c['graphVersion']+'/'+c['pageId']+'/messages',{'recipient':{'id':p['sender']},'messaging_type':'RESPONSE','message':{'text':c['reply']}},{'Authorization':'Bearer '+c['pageAccessToken']});return
  b=self.get_booking(p['id'],admin=True);status=p['status']
  if status=='reminder' and b['status']!='confirmed':return
  if status in ('pending','confirmed') and b['status']!=status:return
  texts={'pending':'Megérkezett a jelentkezésed. Az időpont még függőben van; személyesen visszajelzek.','confirmed':'Elfogadtam a jelentkezésedet. Az időpontod megerősítve.','declined':'Ezt a jelentkezést most nem tudom elfogadni. Kérlek, írj, hogy másik lehetőséget egyeztethessünk.','cancelled':'A jelentkezésedet visszavontuk.','expired':'A függő jelentkezésed lejárt. Ha még szeretnél találkozni, kérlek, jelentkezz újra.','reminder':'Emlékeztető: holnap találkozunk.'}
  subject={'pending':'Jelentkezésed függőben','confirmed':'Időpontod megerősítve','reminder':'Holnap találkozunk'}.get(status,'Jelentkezésed állapota')
  when=parse(b['start']).astimezone(__import__('zoneinfo').ZoneInfo(self.c['google']['timezone'])).strftime('%Y. %m. %d. %H:%M')
  body=f"Kedves {b['name']}!\n\n{texts[status]}\nIdőpont: {when}\nRészvételi díj: {b['price']} Ft\n"
  if status=='confirmed':body+='\n'+self.c['meetingDetails']+'\n'
  if p.get('token'):body+='\nÁllapot és visszavonás: '+self.c['publicSiteUrl'].rstrip('/')+'/status.html#id='+b['id']+'&token='+p['token']+'\n'
  body+='\nÜdvözlettel: Judit'
  self.mailer(b['email'],subject,body,self.ics(b) if status=='confirmed' else None)
  if status=='pending':self.mailer(self.c['smtp']['ownerEmail'],'Új függő jelentkezés',f"{b['name']} <{b['email']}>\nIdőpont: {when}\nBabával egyeztetne: {bool(b['baby'])}\nElfogadás: {self.c['publicSiteUrl']}/admin.html")
 def work(self):
  if not self.worker_lock.acquire(blocking=False):return
  try:
   self.expire()
   with self.db() as db:
    # A later job must wait for earlier jobs of the same booking, except future reminders.
    jobs=db.execute('''SELECT * FROM outbox o WHERE done=0 AND readyAt<=? AND NOT EXISTS(SELECT 1 FROM outbox p WHERE p.done=0 AND p.id<o.id AND p.bookingId=o.bookingId AND NOT(p.kind='mail' AND json_extract(p.payload,'$.status')='reminder')) ORDER BY id LIMIT 20''',(time.time(),)).fetchall()
   for job in jobs:
    try:self.run_job(job)
    except Exception:
     with self.db() as db:db.execute('UPDATE outbox SET attempts=attempts+1,readyAt=?,lastError=? WHERE id=?',(time.time()+min(3600,30*2**min(job['attempts'],7)),'integration_failed',job['id']))
    else:
     with self.db() as db:db.execute('UPDATE outbox SET done=1,lastError=NULL WHERE id=?',(job['id'],))
  finally:self.worker_lock.release()
 def admin_snapshot(self):
  self.expire()
  with self.db() as db:
   rows=[{k:v for k,v in dict(row).items() if k!='tokenHash'} for row in db.execute('SELECT * FROM bookings ORDER BY start')]
   jobs=[dict(row) for row in db.execute('SELECT id,kind,bookingId,attempts,lastError,readyAt FROM outbox WHERE done=0 ORDER BY id')]
  return {'bookings':rows,'jobs':jobs}
 def webhook(self,raw,signature):
  c=self.c['meta']
  if not c.get('enabled'):raise ApiError(404,'disabled')
  expected='sha256='+hmac.new(c['appSecret'].encode(),raw,'sha256').hexdigest()
  if not hmac.compare_digest(expected,signature or ''):raise ApiError(403,'invalid_signature')
  payload=json.loads(raw)
  if payload.get('object')!='page':return
  with self.db() as db:
   db.execute('BEGIN IMMEDIATE');db.execute('DELETE FROM webhook_ids WHERE createdAt<?',(time.time()-7*86400,))
   for entry in payload.get('entry',[]):
    if str(entry.get('id'))!=c['pageId']:continue
    for m in entry.get('messaging',[]):
     msg=m.get('message',{});mid=msg.get('mid');sender=str(m.get('sender',{}).get('id',''))
     if not mid or msg.get('is_echo') or not sender.isdigit() or abs(time.time()-m.get('timestamp',0)/1000)>86400:continue
     if db.execute('INSERT OR IGNORE INTO webhook_ids VALUES(?,?)',(mid,time.time())).rowcount:self.queue(db,'meta-reply',{'sender':sender})
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass # No tokens or personal data in access logs.
 def output(self,status,data,plain=False):
  body=str(data).encode() if plain else json.dumps(data,ensure_ascii=False).encode();self.send_response(status)
  self.send_header('Content-Type','text/plain; charset=utf-8' if plain else 'application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  origin=self.headers.get('Origin')
  if origin in self.server.store.c['allowedOrigins']:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
  self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_OPTIONS(self):
  if self.headers.get('Origin') not in self.server.store.c['allowedOrigins']:return self.output(403,{'error':'origin_denied'})
  self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization, Idempotency-Key');self.send_header('Vary','Origin');self.end_headers()
 def do_GET(self):self.handle_api()
 def do_POST(self):self.handle_api()
 def handle_api(self):
  st=self.server.store;parts=urllib.parse.urlsplit(self.path);path=parts.path.rstrip('/');token=self.headers.get('Authorization','').removeprefix('Bearer ');admin=False
  try:
   if self.headers.get('Origin') and self.headers['Origin'] not in st.c['allowedOrigins']:raise ApiError(403,'origin_denied')
   if path.startswith('/admin'):
    if not hmac.compare_digest(token,st.c['adminToken']):raise ApiError(401,'unauthorized')
    admin=True
   data={};raw=b''
   if self.command=='POST':
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=8192:raise ApiError(413,'invalid_body_size')
    raw=self.rfile.read(length)
    if path!='/meta/webhook':
     if not self.headers.get('Content-Type','').startswith('application/json'):raise ApiError(415,'json_required')
     data=json.loads(raw)
     if not isinstance(data,dict):raise ApiError(400,'invalid_json')
   if self.command=='GET' and path=='/slots':return self.output(200,{'slots':st.list_slots()})
   if self.command=='POST' and path in ('/bookings','/contact'):
    st.rate(self.client_address[0]);key=self.headers.get('Idempotency-Key','');result=st.book(data,key) if path=='/bookings' else st.contact(data,key);return self.output(201,result)
   match=re.fullmatch(r'/bookings/([a-f0-9]{32})(/cancel)?',path)
   if match:
    if match[2] and self.command=='POST':return self.output(200,st.transition(match[1],'cancelled',token))
    if not match[2] and self.command=='GET':return self.output(200,st.get_booking(match[1],token))
   if self.command=='GET' and path=='/admin/bookings':return self.output(200,st.admin_snapshot())
   match=re.fullmatch(r'/admin/bookings/([a-f0-9]{32})/(approve|decline|cancel)',path)
   if match and self.command=='POST':return self.output(200,st.transition(match[1],{'approve':'confirmed','decline':'declined','cancel':'cancelled'}[match[2]],admin=True))
   if path=='/admin/retry' and self.command=='POST':
    with st.db() as db:db.execute('UPDATE outbox SET readyAt=? WHERE done=0 AND lastError IS NOT NULL',(time.time(),))
    return self.output(200,{'status':'queued'})
   if path=='/meta/webhook':
    if self.command=='POST':st.webhook(raw,self.headers.get('X-Hub-Signature-256'));return self.output(200,'EVENT_RECEIVED',plain=True)
    query=urllib.parse.parse_qs(parts.query);meta=st.c['meta']
    if not meta.get('enabled') or query.get('hub.mode')!=['subscribe'] or not hmac.compare_digest(query.get('hub.verify_token',[''])[0],meta['verifyToken']):raise ApiError(403,'invalid_verification')
    return self.output(200,query.get('hub.challenge',[''])[0],plain=True)
   raise ApiError(404,'not_found')
  except ApiError as ex:self.output(ex.status,{'error':ex.message})
  except (ValueError,TypeError,json.JSONDecodeError):self.output(400,{'error':'invalid_request'})
  except Exception:self.output(503,{'error':'integration_unavailable'})
def validate_config(c):
 for key in ('adminToken','ipHashSalt'):
  if len(c.get(key,''))<32 or 'REPLACE' in c[key]:raise ValueError('Set private '+key)
 if not c.get('contentApproved') or not c.get('legalApproved'):raise ValueError('Approval gates are not enabled')
 for key in ('calendarId','clientId','clientSecret','refreshToken'):
  if not c['google'].get(key):raise ValueError('Missing Google '+key)
 for key in ('host','from','ownerEmail'):
  if not c['smtp'].get(key):raise ValueError('Missing SMTP '+key)
 if not c.get('meetingDetails') or 'JÓVÁHAGYANDÓ' in c['meetingDetails']:raise ValueError('Set the confirmed meeting details and cancellation/payment terms')
 if not c['publicSiteUrl'].startswith('https://'):raise ValueError('HTTPS site URL required')
 if any(not x.startswith('https://') for x in c['allowedOrigins']):raise ValueError('HTTPS origins required')
 if c['meta'].get('enabled'):
  for key in ('graphVersion','pageId','appSecret','verifyToken','pageAccessToken'):
   if not c['meta'].get(key):raise ValueError('Missing Meta '+key)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--content',default=str(Path(__file__).resolve().parents[1]/'v2/config/content.json'));args=parser.parse_args()
 c=json.loads(Path(args.config).read_text());validate_config(c)
 if Path(args.config).resolve().is_relative_to(Path(__file__).resolve().parents[1]/'dist'):raise ValueError('Private config cannot be inside public dist')
 st=Store(c,json.loads(Path(args.content).read_text()));server=http.server.ThreadingHTTPServer((c['host'],c['port']),Handler);server.store=st
 stop=threading.Event()
 def worker():
  while not stop.is_set():
   try:st.work()
   except Exception:pass
   stop.wait(5)
 threading.Thread(target=worker,daemon=True).start()
 try:server.serve_forever()
 finally:stop.set();server.server_close()
if __name__=='__main__':main()
