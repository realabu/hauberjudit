// Only this adapter may contact the backend. Offline mode never calls it.
export function calendarFile(booking, title, confirmed = false) {
  const esc = s => String(s).replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/[,;]/g,'\\$&');
  const utc = s => new Date(s).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Hauber Judit//Booking//HU','CALSCALE:GREGORIAN','METHOD:PUBLISH','BEGIN:VEVENT',`UID:${esc(booking.id)}@hauberjudit.hu`,`DTSTAMP:${utc(new Date())}`,`DTSTART:${utc(booking.start)}`,`DTEND:${utc(booking.end)}`,`SUMMARY:${esc(title)}`,`STATUS:${confirmed?'CONFIRMED':'TENTATIVE'}`,'TRANSP:OPAQUE','END:VEVENT','END:VCALENDAR'];
  return lines.map(line=>{let out='',part='';for(const ch of line){if(new TextEncoder().encode(part+ch).length>73){out+=part+'\r\n';part=' ';}part+=ch;}return out+part;}).join('\r\n')+'\r\n';
}
export function createAdapter(runtime,content,{fetchImpl=globalThis.fetch,now=()=>new Date()}={}) {
  const demo=runtime.mode==='offline';
  const bookings=new Map();
  const service=id=>content.offers.items.find(x=>x.id===id);
  const slots=demo?runtime.calendar.mockSlots.map(s=>{
    const d=new Date(now());d.setDate(d.getDate()+s.daysAhead);d.setHours(s.hour,s.minute,0,0);
    // Mock wall-clock times belong to Europe/Budapest, independent of viewer timezone.
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:runtime.calendar.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
    const val=k=>parts.find(x=>x.type===k).value;
    let wall=Date.UTC(+val('year'),+val('month')-1,+val('day'),s.hour,s.minute);
    const probe=new Date(wall);const zparts=new Intl.DateTimeFormat('en-GB',{timeZone:runtime.calendar.timezone,timeZoneName:'longOffset'}).formatToParts(probe);
    const offset=zparts.find(x=>x.type==='timeZoneName').value.match(/GMT([+-])(\d{2}):(\d{2})/);
    if(offset)wall-=(offset[1]==='+'?1:-1)*(+offset[2]*60 + +offset[3])*60000;
    return {...s,title:service(s.serviceId).title,price:service(s.serviceId).price,start:new Date(wall).toISOString(),end:new Date(wall+s.durationMinutes*60000).toISOString(),available:s.capacity-s.reserved};
  }):[];
  const publicBooking=b=>({...b});
  async function request(path,{method='GET',body,token,idempotencyKey}={}) {
    if(demo)throw new Error('Offline backend request forbidden');
    const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),runtime.timeoutMs);
    try{const headers={'Accept':'application/json'};if(body)headers['Content-Type']='application/json';if(token)headers.Authorization=`Bearer ${token}`;if(idempotencyKey)headers['Idempotency-Key']=idempotencyKey;
      const response=await fetchImpl(runtime.apiBaseUrl.replace(/\/$/,'')+path,{method,headers,body:body?JSON.stringify(body):undefined,signal:abort.signal,credentials:'omit'});
      const result=await response.json();if(!response.ok){const error=new Error(result.error||'request_failed');error.code=response.status;throw error;}return result;
    }finally{clearTimeout(timer);}
  }
  return {demo,
    async listSlots(){return demo?slots.map(s=>({...s,available:s.capacity-s.reserved-[...bookings.values()].filter(b=>b.slotId===s.id&&['pending','confirmed'].includes(b.status)).length})): (await request('/slots')).slots;},
    async book(data,key){if(!demo)return request('/bookings',{method:'POST',body:data,idempotencyKey:key});
      const existing=[...bookings.values()].find(b=>b.key===key);if(existing)return publicBooking(existing);
      const slot=(await this.listSlots()).find(s=>s.id===data.slotId);if(!slot||slot.available<1){const e=new Error('full');e.code=409;throw e;}
      const b={id:crypto.randomUUID(),token:crypto.randomUUID(),key,slotId:slot.id,serviceId:slot.serviceId,name:data.name,email:data.email,start:slot.start,end:slot.end,status:'pending',price:slot.price,expiresAt:new Date(now().getTime()+48*3600000).toISOString()};bookings.set(b.id,b);return publicBooking(b);},
    async approveDemo(id){if(!demo)throw new Error('Demo approval disabled');const b=bookings.get(id);if(!b||b.status!=='pending')throw new Error('Invalid transition');b.status='confirmed';return publicBooking(b);},
    async cancel(id,token){if(!demo)return request(`/bookings/${encodeURIComponent(id)}/cancel`,{method:'POST',body:{},token});const b=bookings.get(id);if(!b||b.token!==token)throw new Error('Invalid token');b.status='cancelled';return publicBooking(b);},
    async status(id,token){if(!demo)return request(`/bookings/${encodeURIComponent(id)}`,{token});const b=bookings.get(id);if(!b||b.token!==token)throw new Error('Missing demo booking');return publicBooking(b);},
    async contact(data,key){return demo?{status:'demo'}:request('/contact',{method:'POST',body:data,idempotencyKey:key});},
    messenger(){if(demo)return {demo:true};const url=runtime.messenger.link;if(!/^https:\/\/m\.me\/[a-zA-Z0-9_.-]+$/.test(url))throw new Error('Invalid Messenger link');return {demo:false,url};}
  };
}
