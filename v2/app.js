import {createAdapter,calendarFile} from './integrations.js';
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const [content,runtime]=await Promise.all(['content.json','runtime.json'].map(p=>fetch(p).then(r=>{if(!r.ok)throw new Error('Config unavailable');return r.json();})));
const api=createAdapter(runtime,content);const t=content.booking;
const menu=$('.menu-toggle');menu?.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));$('#navigation').classList.toggle('open',open);});
$('#navigation')?.addEventListener('click',e=>{if(e.target.closest('a')){menu.setAttribute('aria-expanded','false');$('#navigation').classList.remove('open');}});
const format=(date,opts)=>new Intl.DateTimeFormat('hu-HU',{timeZone:runtime.calendar.timezone,...opts}).format(new Date(date));
const dateKey=date=>new Intl.DateTimeFormat('en-CA',{timeZone:runtime.calendar.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(date));
const summary=s=>`${s.title} · ${format(s.start,{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'})} · ${new Intl.NumberFormat('hu-HU').format(s.price)} Ft`;
let slots=[],selected=null,booking=null,formKey=null,view='list',selectedDay=null;
let month=new Date();month=new Date(month.getFullYear(),month.getMonth(),1);
const serviceFilter=$('#service-filter');if(serviceFilter&&$('#main').dataset.service)serviceFilter.value=$('#main').dataset.service;
if($('#offline-notice'))$('#offline-notice').hidden=!api.demo;
function filtered(){return slots.filter(s=>!serviceFilter.value||s.serviceId===serviceFilter.value);}
function renderSlots(){const list=filtered().filter(s=>!selectedDay||dateKey(s.start)===selectedDay);
  $('#slots').innerHTML=list.length?list.map(s=>`<article class="slot ${s.available?'':'full'}"><div class="slot-date"><strong>${esc(format(s.start,{day:'numeric'}))}</strong><span>${esc(format(s.start,{month:'short',weekday:'short'}))}</span></div><div><h3>${esc(s.title)}</h3><p>${esc(format(s.start,{hour:'2-digit',minute:'2-digit'}))}–${esc(format(s.end,{hour:'2-digit',minute:'2-digit'}))} · ${new Intl.NumberFormat('hu-HU').format(s.price)} Ft</p><p>${s.available?`${s.available} ${esc(t.seats)}`:esc(t.full)}</p></div>${s.available?`<button class="button primary" data-slot="${esc(s.id)}">${esc(t.choose)} ↗</button>`:`<span class="badge">${esc(t.full)}</span>`}</article>`).join(''):`<p>${esc(t.empty)}</p>`;
}
function renderCalendar(){const year=month.getFullYear(),m=month.getMonth();$('#month-label').textContent=new Intl.DateTimeFormat('hu-HU',{year:'numeric',month:'long'}).format(month);
  const week=Array.from({length:7},(_,i)=>new Intl.DateTimeFormat('hu-HU',{weekday:'short'}).format(new Date(2026,0,5+i))).map(w=>`<div class="calendar-weekday">${esc(w)}</div>`).join('');
  const offset=(new Date(year,m,1).getDay()+6)%7;const count=new Date(year,m+1,0).getDate();let cells='<span></span>'.repeat(offset);
  for(let day=1;day<=count;day++){const key=`${year}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;const matches=filtered().filter(s=>dateKey(s.start)===key);const available=matches.filter(s=>s.available>0).length;
   cells+=`<button class="calendar-day ${available?'available':''} ${selectedDay===key?'selected':''}" data-date="${key}" aria-label="${key}: ${available} ${esc(t.seats)}" ${matches.length?'':'disabled'}>${day}${matches.length?`<span>${available?`${available} ${esc(t.seats)}`:esc(t.full)}</span>`:''}</button>`;}
  $('#calendar-grid').innerHTML=week+cells;
}
async function loadSlots(){try{$('#slots').textContent=t.loading;slots=await api.listSlots();slots.sort((a,b)=>new Date(a.start)-new Date(b.start));renderSlots();renderCalendar();}catch{$('#slots').innerHTML=`<p role="alert">${esc(t.error)}</p><button class="button secondary" id="retry-slots">${esc(t.retry)}</button>`;$('#retry-slots').onclick=loadSlots;}}
if($('#slots')){
 if(!runtime.features.booking){$('.booking').hidden=true;}else{await loadSlots();}
 serviceFilter.onchange=()=>{selectedDay=null;renderSlots();renderCalendar();};
 $('#list-view').onclick=()=>{view='list';selectedDay=null;$('#calendar').hidden=true;$('#list-view').setAttribute('aria-pressed','true');$('#calendar-view').setAttribute('aria-pressed','false');renderSlots();};
 $('#calendar-view').onclick=()=>{view='calendar';$('#calendar').hidden=false;$('#calendar-view').setAttribute('aria-pressed','true');$('#list-view').setAttribute('aria-pressed','false');renderCalendar();};
 if(!runtime.features.calendar)$('#calendar-view').hidden=true;
 $('#prev-month').onclick=()=>{month=new Date(month.getFullYear(),month.getMonth()-1,1);selectedDay=null;renderCalendar();renderSlots();};
 $('#next-month').onclick=()=>{month=new Date(month.getFullYear(),month.getMonth()+1,1);selectedDay=null;renderCalendar();renderSlots();};
 $('#calendar-grid').onclick=e=>{const b=e.target.closest('[data-date]');if(!b)return;selectedDay=b.dataset.date;renderCalendar();renderSlots();};
 $('#slots').onclick=e=>{const b=e.target.closest('[data-slot]');if(!b)return;selected=slots.find(s=>s.id===b.dataset.slot);formKey=crypto.randomUUID();$('#booking-form').reset();$('#booking-error').textContent='';$('#selected-slot').textContent=summary(selected);$('#booking-dialog').showModal();};
 $('#close-dialog').onclick=()=>$('#booking-dialog').close();
 $('#booking-form').onsubmit=async e=>{e.preventDefault();const form=e.target;const data=Object.fromEntries(new FormData(form));if(!data.name?.trim()||!data.privacy||!form.checkValidity()){$('#booking-error').textContent=t.invalid;return;}const submit=form.querySelector('[type=submit]');submit.disabled=true;submit.textContent=t.submitting;
  try{booking=await api.book({slotId:selected.id,name:data.name.trim(),email:data.email.trim(),baby:!!data.baby,privacy:true,website:data.website},formKey);$('#booking-dialog').close();showResult();await loadSlots();$('#booking-result').scrollIntoView({behavior:'smooth',block:'center'});}catch(err){$('#booking-error').textContent=err.code===409?t.conflict:t.submitError;if(err.code===409)await loadSlots();}finally{submit.disabled=false;submit.textContent=t.submit;}};
}
function downloadCalendar(){const title=content.offers.items.find(s=>s.id===booking.serviceId)?.title||content.brand.name;const blob=new Blob([calendarFile(booking,title,booking.status==='confirmed')],{type:'text/calendar;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=api.demo?'proba-idopont.ics':'idopont.ics';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function showResult(){const box=$('#booking-result');box.hidden=false;const confirmed=booking.status==='confirmed';box.innerHTML=`<h3>${esc(booking.status==='cancelled'?t.cancelled:confirmed?t.confirmedTitle:t.successTitle)}</h3><p>${esc(summary(booking))}</p>${booking.status==='cancelled'?'':`<p>${esc(api.demo?(confirmed?t.confirmed:t.demoSuccess):t.success)}</p>${api.demo&&!confirmed?`<div class="email-preview"><h4>${esc(t.demoMailTitle)}</h4><p>${esc(t.demoMailBody)}</p></div>`:''}<div class="actions">${api.demo&&!confirmed?`<button class="button primary" id="demo-approve">${esc(t.demoApprove)}</button>`:''}<button class="button secondary" id="download-ics">${esc(t.addCalendar)}</button><button class="text-link" id="cancel-booking">${esc(t.cancel)}</button></div>`}`;
 $('#demo-approve')?.addEventListener('click',async()=>{booking=await api.approveDemo(booking.id);showResult();});$('#download-ics')?.addEventListener('click',downloadCalendar);$('#cancel-booking')?.addEventListener('click',async()=>{try{booking=await api.cancel(booking.id,booking.token);showResult();await loadSlots();}catch{$('#booking-result').append(Object.assign(document.createElement('p'),{textContent:t.submitError}));}});
}
const contactForm=$('#contact-form');let contactKey=crypto.randomUUID();if(contactForm){if(!runtime.features.contact)contactForm.hidden=true;contactForm.addEventListener('input',()=>{contactKey=crypto.randomUUID();});contactForm.onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(contactForm));const submit=contactForm.querySelector('[type=submit]');submit.disabled=true;try{await api.contact({...data,privacy:!!data.privacy},contactKey);$('#contact-result').textContent=api.demo?content.contact.demoSuccess:content.contact.success;contactForm.reset();contactKey=crypto.randomUUID();}catch{$('#contact-result').textContent=t.submitError;}finally{submit.disabled=false;}};}
const messenger=$('#messenger-button');if(messenger){messenger.hidden=!runtime.features.messenger;messenger.onclick=()=>{const result=api.messenger();if(result.demo)$('#messenger-message').textContent=content.contact.messengerDemo;else window.open(result.url,'_blank','noopener,noreferrer');};}
