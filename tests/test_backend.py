import concurrent.futures,datetime as dt,importlib.util,json,tempfile,threading,time,unittest,hashlib,hmac,http.client
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('backend',ROOT/'backend/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FakeGoogle:
 def __init__(self):self.items=[];self.calls=[];self.fail=False
 def events(self):return self.items
 def sync(self,b,status):
  if self.fail:raise RuntimeError('fake outage')
  self.calls.append((b['id'],status))
class BookingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.g=FakeGoogle();self.mails=[]
  self.c=json.loads((ROOT/'backend/config.example.json').read_text());self.c.update(database=self.tmp.name+'/db.sqlite3',contentApproved=True,legalApproved=True,adminToken='x'*40,ipHashSalt='y'*40,meetingDetails='Pontos cím és feltételek.');self.c['smtp'].update(ownerEmail='judit@example.test')
  self.content=json.loads((ROOT/'v2/config/content.json').read_text());self.st=m.Store(self.c,self.content,self.g,lambda *a:self.mails.append(a))
  start=m.now()+dt.timedelta(days=5);end=start+dt.timedelta(hours=1)
  self.g.items=[{'id':'slot1','summary':'[HJ:FOGLALHATO] Coaching','description':'{"service":"coaching","capacity":1}','start':{'dateTime':m.iso(start)},'end':{'dateTime':m.iso(end)}}]
  self.data={'slotId':'slot1','name':'Teszt Anna','email':'anna@example.test','privacy':True}
 def book(self,key='abcdefghijklmnop'):return self.st.book(self.data,key)
 def test_capacity_and_idempotency(self):
  b=self.book();self.assertEqual(self.book()['id'],b['id']);self.assertEqual(self.st.list_slots()[0]['available'],0)
  with self.assertRaises(m.ApiError) as ctx:self.book('qrstuvwxyzabcdef')
  self.assertEqual(ctx.exception.status,409)
 def test_concurrent_last_place(self):
  barrier=threading.Barrier(2)
  def go(key):
   barrier.wait()
   try:return self.book(key)['id']
   except m.ApiError as ex:return ex.status
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(go,['abcdefghijklmnop','qrstuvwxyzabcdef']))
  self.assertEqual(results.count(409),1)
 def test_token_authorization_and_transition(self):
  b=self.book()
  with self.assertRaises(m.ApiError):self.st.get_booking(b['id'],'wrong')
  with self.assertRaises(m.ApiError):self.st.transition(b['id'],'confirmed',b['token'])
  self.assertEqual(self.st.transition(b['id'],'confirmed',admin=True)['status'],'confirmed');self.assertEqual(self.st.transition(b['id'],'cancelled',b['token'])['status'],'cancelled');self.assertEqual(self.st.list_slots()[0]['available'],1)
 def test_failure_does_not_send_confirmation_before_calendar(self):
  b=self.book();self.st.transition(b['id'],'confirmed',admin=True);self.g.fail=True
  for _ in range(5):self.st.work()
  self.assertEqual(self.mails,[])
  self.g.fail=False
  with self.st.db() as db:db.execute('UPDATE outbox SET readyAt=? WHERE lastError IS NOT NULL',(time.time()-1,))
  for _ in range(5):self.st.work()
  self.assertTrue(any('megerősítve' in x[1] for x in self.mails));self.assertEqual(self.g.calls[-1][1],'confirmed')
 def test_only_whitelisted_slots_no_private_content(self):
  self.g.items.append({'id':'private','summary':'Privát titok','description':'Orvosi adat','start':{'dateTime':m.iso(m.now()+dt.timedelta(days=8))},'end':{'dateTime':m.iso(m.now()+dt.timedelta(days=8,hours=1))}})
  self.assertNotIn('Privát',json.dumps(self.st.list_slots()));self.g.items[0]['description']='broken';self.assertEqual(self.st.list_slots(),[])
 def test_busy_overlap_hides_slot(self):
  event=dict(self.g.items[0]);event.update(id='private',summary='Személyes ügy');self.g.items.append(event);self.assertEqual(self.st.list_slots(),[])
 def test_expiry_releases_capacity(self):
  b=self.book()
  with self.st.db() as db:db.execute('UPDATE bookings SET expiresAt=? WHERE id=?',(m.iso(m.now()-dt.timedelta(seconds=1)),b['id']))
  self.st.expire();self.assertEqual(self.st.get_booking(b['id'],b['token'])['status'],'expired');self.assertEqual(self.st.list_slots()[0]['available'],1)
 def test_group_capacity(self):
  self.g.items[0]['description']='{"service":"anyakor","capacity":2}';self.g.items[0]['end']['dateTime']=m.iso(m.parse(self.g.items[0]['start']['dateTime'])+dt.timedelta(hours=2))
  self.book();self.book('qrstuvwxyzabcdef')
  with self.assertRaises(m.ApiError):self.book('1234567890abcdef')
 def test_webhook_signature_and_deduplication(self):
  self.c['meta'].update(enabled=True,appSecret='test-secret')
  raw=json.dumps({'object':'page','entry':[{'id':self.c['meta']['pageId'],'messaging':[{'sender':{'id':'123'},'timestamp':int(time.time()*1000),'message':{'mid':'m1','text':'private'}}]}]}).encode()
  with self.assertRaises(m.ApiError):self.st.webhook(raw,'bad')
  signature='sha256='+hmac.new(b'test-secret',raw,'sha256').hexdigest();self.st.webhook(raw,signature);self.st.webhook(raw,signature)
  with self.st.db() as db:rows=db.execute("SELECT payload FROM outbox WHERE kind='meta-reply'").fetchall()
  self.assertEqual(len(rows),1);self.assertNotIn('private',rows[0][0])
 def test_rate_limit(self):
  self.c['rateLimitPerHour']=1;self.st.rate('127.0.0.1')
  with self.assertRaises(m.ApiError) as ctx:self.st.rate('127.0.0.1')
  self.assertEqual(ctx.exception.status,429)
 def test_validation(self):
  for change in ({'privacy':False},{'name':'A\nB'},{'email':'bad'},{'website':'spam'}):
   with self.subTest(change=change),self.assertRaises(m.ApiError):self.st.book({**self.data,**change},'abcdefghijklmnop')
 def test_http_boundary(self):
  server=m.http.server.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);server.store=self.st;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def request(method,path,body=None,headers=None):
   conn=http.client.HTTPConnection('127.0.0.1',server.server_port);conn.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {});response=conn.getresponse();status=response.status;payload=response.read();conn.close();return status,json.loads(payload)
  try:
   self.assertEqual(request('GET','/admin/bookings')[0],401)
   self.assertEqual(request('GET','/slots',headers={'Origin':'https://evil.example.test'})[0],403)
   headers={'Origin':'https://realabu.github.io','Content-Type':'application/json','Idempotency-Key':'abcdefghijklmnop'}
   status,b=request('POST','/bookings',self.data,headers);self.assertEqual(status,201)
   self.assertEqual(request('GET','/bookings/'+b['id'])[0],404)
   self.assertEqual(request('GET','/bookings/'+b['id'],headers={'Authorization':'Bearer '+b['token']})[0],200)
   self.assertEqual(request('POST','/admin/bookings/'+b['id']+'/approve',{},headers={'Content-Type':'application/json','Authorization':'Bearer '+'x'*40})[1]['status'],'confirmed')
  finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
