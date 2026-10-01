#!/usr/bin/env python3
"""Build the separate v2 without modifying the original site's files."""
import html,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'v2'
OUT=ROOT/'dist/v2'
def e(value):return html.escape(str(value),quote=True)
def paragraphs(items):return ''.join('<p>'+e(x)+'</p>' for x in items)
def section_head(d):return '<p class="eyebrow">'+e(d['eyebrow'])+'</p><h2>'+e(d['heading'])+'</h2>'
def button(url,label,kind='primary'):return f'<a class="button {kind}" href="{e(url)}">{e(label)} <span aria-hidden="true">↗</span></a>'
def build():
 c=json.loads((SRC/'config/content.json').read_text());r=json.loads((SRC/'config/runtime.json').read_text())
 # A public config must never grow a private credential field.
 def check(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if any(s in k.lower() for s in ('secret','password','privatekey','accesstoken','refreshtoken','admintoken')):raise ValueError('Private field in public runtime: '+k)
    check(v)
  elif isinstance(x,list):
   for v in x:check(v)
 check(r)
 if r['mode'] not in ('offline','online'):raise ValueError('Unknown mode')
 if r['mode']=='online' and (not r['legalApproved'] or not r['contentApproved'] or c['review']['enabled'] or not r['apiBaseUrl'].startswith('https://')):raise ValueError('Online requires approved content/legal, review disabled, HTTPS API')
 OUT.mkdir(parents=True,exist_ok=True)
 for f in ('styles.css','app.js','integrations.js','admin.html','admin.js','status.html','status.js','compare.html'):shutil.copyfile(SRC/f,OUT/f)
 for name,obj in [('content',c),('runtime',r)]: (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 version=hashlib.sha256((SRC/'styles.css').read_bytes()+(SRC/'app.js').read_bytes()+(SRC/'integrations.js').read_bytes()).hexdigest()[:12]
 rv=c['review']; b=c['brand'];h=c['hero'];a=c['about'];o=c['offers'];bk=c['booking'];ct=c['contact']
 def price(s):return f'{s["price"]:,}'.replace(',',' ')+' '+e(s['priceUnit'])
 def form_fields():return f'<label>{e(bk["name"])}<input name="name" autocomplete="name" required minlength="2" maxlength="100"></label><label>{e(bk["email"])}<input name="email" type="email" autocomplete="email" required maxlength="200"></label>'
 def privacy():return f'<label class="checkbox"><input name="privacy" type="checkbox" required><span>{e(bk["privacy"])} <a href="adatkezeles/">{e(c["footer"]["privacy"])}</a></span></label><label class="trap" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label>'
 booking=f'<section class="section booking" id="idopontok"><div class="container">{section_head(bk)}<p class="section-lead">{e(bk["text"])}</p><p class="demo-note" id="offline-notice">{e(bk["offlineNotice"])}</p><div class="booking-tools"><label class="sr-only" for="service-filter">{e(bk["filterAll"])}</label><select id="service-filter"><option value="">{e(bk["filterAll"])}</option>'+''.join(f'<option value="{e(s["id"])}">{e(s["title"])}</option>' for s in o['items'])+f'</select><div class="view-toggle"><button id="list-view" aria-pressed="true">{e(bk["listView"])}</button><button id="calendar-view" aria-pressed="false">{e(bk["calendarView"])}</button></div></div><div id="calendar" hidden><div class="calendar-toolbar"><button id="prev-month" aria-label="{e(bk["previous"])}">←</button><h3 id="month-label"></h3><button id="next-month" aria-label="{e(bk["next"])}">→</button></div><div id="calendar-grid" class="calendar-grid"></div></div><div id="slots" aria-live="polite"><p>{e(bk["loading"])}</p></div><div id="booking-result" class="result" hidden aria-live="polite"></div></div></section>'
 dialog=f'<dialog id="booking-dialog"><div class="dialog-top"><h2>{e(bk["formTitle"])}</h2><button id="close-dialog" type="button" aria-label="{e(bk["close"])}">×</button></div><p id="selected-slot"></p><form id="booking-form">{form_fields()}<label class="checkbox"><input type="checkbox" name="baby"><span>{e(bk["baby"])}</span></label>{privacy()}<button class="button primary" type="submit">{e(bk["submit"])}</button><p id="booking-error" role="alert"></p></form></dialog>'
 contact=f'<section class="section contact" id="kapcsolat"><div class="container contact-grid"><div>{section_head(ct)}<p>{e(ct["text"])}</p><p class="response">{e(ct["response"])}</p><button class="button secondary" id="messenger-button" type="button">{e(ct["messenger"])} ↗</button><p id="messenger-message" role="status"></p></div><form id="contact-form">{form_fields()}<label>{e(ct["topicLabel"])}<select name="topic">'+''.join('<option>'+e(x)+'</option>' for x in ct['topics'])+f'</select></label><label>{e(ct["messageLabel"])}<textarea name="message" maxlength="1000" rows="3" aria-describedby="message-hint"></textarea></label><p class="hint" id="message-hint">{e(ct["messageHint"])}</p>{privacy()}<button type="submit" class="button primary">{e(ct["submit"])}</button><p id="contact-result" role="status"></p></form></div></section>'
 def shell(body,title,base='',description=None):
  nav=''.join(f'<a href="{e(x["href"])}">{e(x["label"])}</a>' for x in c['navigation'])
  # The v2 stays a comparison preview until content has been accepted.
  robots='<meta name="robots" content="noindex,nofollow">' if rv['enabled'] else ''
  bar=f'<div class="review-bar"><div class="container"><strong>{e(rv["label"])}</strong><span>{e(rv["text"])}</span><a href="{e(rv["originalUrl"])}">{e(rv["original"])}</a></div></div>' if rv['enabled'] else ''
  return f'<!doctype html><html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base href="{e(base)}"><title>{e(title)}</title><meta name="description" content="{e(description or c["meta"]["description"])}">{robots}<meta name="theme-color" content="#451b2c"><link rel="icon" href="icon.svg"><link rel="stylesheet" href="styles.css?v={version}"></head><body id="top"><a class="skip" href="#main">{e(c["labels"]["skip"])}</a>{bar}<header><div class="container nav-row"><a class="brand" href="./"><strong>{e(b["name"])}</strong><span>{e(b["role"])}</span></a><button class="menu-toggle" aria-controls="navigation" aria-expanded="false">{e(c["labels"]["menu"])}</button><nav id="navigation">{nav}{button("#idopontok",c["labels"]["details"],"small")}</nav></div></header><main id="main">{body}</main><footer><div class="container footer-grid"><div class="brand"><strong>{e(b["name"])}</strong><p>{e(c["footer"]["text"])}</p><small>© {e(c["footer"]["year"])}</small></div><div><a href="adatkezeles/">{e(c["footer"]["privacy"])}</a><a href="../">{e(c["footer"]["original"])}</a><a href="{e(ct["facebookUrl"])}" target="_blank" rel="noopener">{e(ct["socialLabel"])}</a></div><a href="#top">{e(c["footer"]["top"])} ↑</a></div></footer>{dialog}<script type="module" src="app.js?v={version}"></script></body></html>'
 hero=f'<section class="hero container"><div class="hero-copy"><p class="eyebrow">{e(h["eyebrow"])}</p><h1>{e(h["heading"]).replace(chr(10),"<br>")}</h1><p class="lead">{e(h["text"])}</p><div class="actions">{button("#lehetosegek",h["primary"])}<a class="text-link" href="#rolam">{e(h["secondary"])} →</a></div><div class="hero-meta"><span>⌁ {e(h["location"])}</span><span>{e(h["audience"])}</span></div></div><figure class="hero-art"><img src="{e(h["image"])}" alt="{e(h["imageAlt"])}" width="1536" height="1024" fetchpriority="high"><figcaption>{e(h["imageCaption"])}</figcaption></figure></section>'
 welcome=f'<section class="welcome"><div class="container welcome-grid"><div><h2>{e(c["welcome"]["heading"])}</h2><p>{e(c["welcome"]["text"])}</p></div><div class="story-note"><span class="avatar"><img src="{e(a["portrait"])}" alt="{e(a["portraitAlt"])}" loading="lazy"></span><p>{e(c["welcome"]["note"])}</p></div></div></section>'
 situations='<section class="section container">'+section_head(c['situations'])+'<div class="three-grid">'+''.join('<article class="situation"><span class="tiny-number">0'+str(i+1)+'</span><h3>'+e(x['title'])+'</h3><p>'+e(x['text'])+'</p></article>' for i,x in enumerate(c['situations']['items']))+'</div></section>'
 offers='<section class="section offers" id="lehetosegek"><div class="container">'+section_head(o)+'<p class="section-lead">'+e(o['text'])+'</p><div class="offer-grid">'+''.join(f'<article class="offer"><div class="offer-meta"><span>{e(s["number"])}</span><span>{e(s["tag"])}</span></div><h3>{e(s["title"])}</h3><p class="offer-subtitle">{e(s["subtitle"])}</p><p>{e(s["description"])}</p><ul>'+''.join('<li>'+e(x)+'</li>' for x in s['points'])+f'</ul><div class="offer-price"><strong>{price(s)}</strong><span>{e(s["duration"])}</span></div><p class="hint">{e(s["format"])}</p>{button(s["landing"],s["cta"])}<p class="hint">{e(o["priceNote"])}</p></article>' for s in o['items'])+'</div></div></section>'
 process='<section class="section container">'+section_head(c['process'])+'<ol class="steps">'+''.join('<li><span>0'+str(i+1)+'</span><div><h3>'+e(s['title'])+'</h3><p>'+e(s['text'])+'</p></div></li>' for i,s in enumerate(c['process']['steps']))+'</ol></section>'
 about='<section class="section about" id="rolam"><div class="container about-grid"><div>'+section_head(a)+'<p class="lead">'+e(a['lead'])+'</p>'+paragraphs(a['paragraphs'])+'</div><aside><div class="about-photo"><img src="'+e(a['portrait'])+'" alt="'+e(a['portraitAlt'])+'" loading="lazy"></div><div class="qualifications">'+''.join('<div><h3>'+e(q['title'])+'</h3><p>'+e(q['text'])+'</p></div>' for q in a['qualifications'])+'</div></aside></div><div class="container three-grid values">'+''.join('<div><h3>'+e(x['title'])+'</h3><p>'+e(x['text'])+'</p></div>' for x in a['values'])+'</div><p class="container scope">'+e(a['scope'])+'</p></section>'
 practical='<section class="section container">'+section_head(c['practical'])+'<div class="three-grid">'+''.join('<article><h3>'+e(x['title'])+'</h3><p>'+e(x['text'])+'</p></article>' for x in c['practical']['items'])+'</div></section>'
 k=c['cards'];cards=f'<section class="cards"><div class="container cards-grid"><img src="{e(k["image"])}" alt="{e(k["imageAlt"])}" loading="lazy"><div>{section_head(k)}<p>{e(k["text"])}</p>{button(k["url"],k["cta"],"secondary")}</div></div></section>'
 faq='<section class="section container faq" id="kerdesek"><div>'+section_head(c['faq'])+'</div><div>'+''.join('<details><summary>'+e(x['question'])+'</summary><p>'+e(x['answer'])+'</p></details>' for x in c['faq']['items'])+'</div></section>'
 gallery=''
 if c.get('gallery',{}).get('enabled'):
  g=c['gallery'];gallery='<section class="section container gallery">'+section_head(g)+'<p>'+e(g['text'])+'</p><div class="gallery-grid">'
  for item in g['items']:
   if not item['src'].startswith(('assets/','../assets/','https://')):raise ValueError('Invalid gallery image')
   gallery+=f'<figure><img src="{e(item["src"])}" alt="{e(item["alt"])}" loading="lazy"><figcaption>{e(item["caption"])}</figcaption></figure>'
  gallery+='</div></section>'
 video=''
 if c.get('video',{}).get('enabled'):
  v=c['video']
  media=(f'<video controls preload="none" poster="{e(v["poster"])}"><source src="{e(v["src"])}" type="video/mp4">'+(f'<track src="{e(v["captionsSrc"])}" kind="captions" srclang="hu" label="Magyar" default>' if v['captionsSrc'] else '')+'</video>') if v['src'] else f'<div class="video-placeholder" role="img" aria-label="{e(v["placeholder"])}"><img src="{e(v["poster"])}" alt="{e(a["portraitAlt"])}" loading="lazy"><span aria-hidden="true">▷</span><p>{e(v["placeholder"])}</p></div>'
  video='<section class="section container video-section" id="bemutatkozo-video"><div>'+section_head(v)+'<p>'+e(v['text'])+'</p><details><summary>'+e(v['transcriptTitle'])+'</summary><p>'+e(v['transcript'])+'</p></details></div><div>'+media+'</div></section>'
 testimonial=''
 if c.get('testimonial',{}).get('enabled'):
  t=c['testimonial'];testimonial='<section class="section testimonial"><div class="container">'+section_head(t)+'<blockquote><p>„'+e(t['quote'])+'”</p><footer>'+e(t['attribution'])+'</footer></blockquote><p class="hint">'+e(t['context'])+'</p></div></section>'
 ap=c['appearances']
 appearances='<section class="section container appearances-preview">'+section_head(ap)+'<p class="section-lead">'+e(ap['text'])+'</p><div class="appearance-tags">'+''.join('<span>'+e(x['title'])+'</span>' for x in ap['items'][2:])+'</div>'+button('megjelenesek/',ap['cta'],'secondary')+'</section>'
 (OUT/'index.html').write_text(shell(hero+welcome+situations+offers+process+about+video+testimonial+appearances+practical+gallery+booking+faq+cards+contact,c['meta']['title']))
 press=OUT/'megjelenesek';press.mkdir(exist_ok=True)
 pressbody='<section class="section container"><p class="eyebrow">'+e(ap['eyebrow'])+'</p><h1>'+e(ap['heading'])+'</h1><p class="section-lead">'+e(ap['text'])+'</p><div class="appearance-grid">'+''.join('<article class="appearance"><p class="eyebrow">'+e(x['tag'])+'</p><h2>'+e(x['title'])+'</h2><p>'+e(x['text'])+'</p>'+(f'<a href="{e(x["url"])}" target="_blank" rel="noopener">{e(ap["linkLabel"])} ↗</a>' if x['url'] else '')+'</article>' for x in ap['items'])+'</div><p class="section-lead">'+e(ap['closing'])+'</p>'+button('#kapcsolat',ap['contactLabel'])+'</section>'+contact
 presshtml=shell(pressbody,ap['heading']+' · '+b['name'],base='../')
 for anchor in ('main','top','kapcsolat'):presshtml=presshtml.replace(f'href="#{anchor}"',f'href="megjelenesek/#{anchor}"')
 (press/'index.html').write_text(presshtml)

 for s in o['items']:
  body=f'<section class="container service-hero"><a class="text-link" href="./">← {e(c["labels"]["backHome"])}</a><p class="eyebrow">{e(s["tag"])}</p><h1>{e(s["title"])}</h1><p class="lead">{e(s["subtitle"])}</p><p>{e(s["forWhom"])}</p><div class="service-summary"><strong>{price(s)}</strong><span>{e(s["duration"])}</span><span>{e(s["format"])}</span></div><p class="hint">{e(o["priceNote"])}</p>{button("#idopontok",s["bookingLabel"])}<p>{e(s["description"])}</p></section><section class="section container service-details"><div><h2>{e(c["labels"]["serviceProcess"])}</h2><ol>'+''.join('<li>'+e(x)+'</li>' for x in s['process'])+f'</ol><p>{e(s["outcome"])}</p></div><div><h2>{e(c["labels"]["serviceTopics"])}</h2><ul>'+''.join('<li>'+e(x)+'</li>' for x in s['topics'])+f'</ul><h3>{e(c["labels"]["servicePractical"])}</h3><p>{e(s["logistics"])}</p></div></section><p class="container scope">{e(s["boundary"])}</p>'+booking+faq+contact
  page=OUT/s['id'];page.mkdir(exist_ok=True)
  rendered=shell(body,s['title']+' · '+b['name'],base='../').replace('<main id="main">',f'<main id="main" data-service="{e(s["id"])}">')
  for anchor in ('idopontok','main','top'):rendered=rendered.replace(f'href="#{anchor}"',f'href="{s["id"]}/#{anchor}"')
  (page/'index.html').write_text(rendered)
 legal=OUT/'adatkezeles';legal.mkdir(exist_ok=True)
 legal_rendered=shell('<section class="section container legal"><h1>'+e(c['legal']['title'])+'</h1>'+paragraphs([c['legal'][x] for x in ('demo','scope','liveGate')])+'</section>',c['legal']['title'],base='../')
 for anchor in ('main','top'):legal_rendered=legal_rendered.replace(f'href="#{anchor}"',f'href="adatkezeles/#{anchor}"')
 (legal/'index.html').write_text(legal_rendered)
 (OUT/'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#451b2c"/><text x="32" y="42" text-anchor="middle" fill="#e1e452" font-family="Georgia" font-size="30">HJ</text></svg>')
 print('Built separate v2: home, service pages, offline booking, admin and status')
if __name__=='__main__':build()
