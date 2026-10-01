#!/usr/bin/env python3
"""Build a fully static site from config/content.json. Python standard library only."""
from pathlib import Path
import json,html,urllib.parse,shutil
ROOT=Path(__file__).resolve().parent
c=json.loads((ROOT/'config/content.json').read_text())
def e(s):return html.escape(str(s),quote=True)
def link(url,label,cls=''):
 if not (url.startswith(('https://','mailto:','#'))):raise ValueError('Unsupported link: '+url)
 ext=' target="_blank" rel="noopener noreferrer"' if url.startswith('https://') else ''
 return f'<a class="{e(cls)}" href="{e(url)}"{ext}>{e(label)}</a>'
def section_head(d):return f'<p class="eyebrow">{e(d["eyebrow"])}</p><h2>{e(d["heading"])}</h2>'
nav=''.join(link(x['href'],x['label']) for x in c['navigation'])
h=c['hero'];a=c['about'];sv=c['services'];p=c['process'];k=c['cards'];f=c['faq'];ct=c['contact']
services=''.join(f'<article class="service"><div class="service-top"><span class="number">{e(x["number"])}</span><span class="service-label">{e(x["label"])}</span></div><h3>{e(x["title"])}</h3><p>{e(x["description"])}</p><details><summary>{e(c["labels"]["details"])}</summary><div class="details-body">'+''.join(f'<p>{e(t)}</p>' for t in x['details'])+'</div></details></article>' for x in sv['items'])
qual=''.join(f'<li><strong>{e(x["title"])}</strong><span>{e(x["text"])}</span></li>' for x in a['qualifications'])
steps=''.join(f'<li><span class="step-number">{i+1:02}</span><div><h3>{e(x["title"])}</h3><p>{e(x["text"])}</p></div></li>' for i,x in enumerate(p['steps']))
faq=''.join(f'<details><summary>{e(x["question"])}</summary><p>{e(x["answer"])}</p></details>' for x in f['items'])
contact=[]
if ct['email']:
 if '\n' in ct['email'] or '@' not in ct['email']:raise ValueError('Invalid email')
 contact.append(link('mailto:'+urllib.parse.quote(ct['email'],safe='@.'),ct['emailButton'],'button lime'))
if ct['messengerUrl']:contact.append(link(ct['messengerUrl'],ct['messengerButton'],'button outline-light'))
if ct['facebookUrl']:contact.append(link(ct['facebookUrl'],ct['facebookLabel'],'text-link light'))
contact_html='<div class="actions">'+''.join(contact)+'</div><p class="response">'+e(ct['response'])+'</p>' if contact else '<p class="pending">'+e(ct['pending'])+'</p>'
portrait=f'<img src="{e(a["portrait"])}" alt="{e(a["portraitAlt"])}" loading="lazy">' if a['portrait'] else f'<div class="about-note"><span class="monogram" aria-hidden="true">{e(c["brand"]["initials"])}</span><p>{e(a["note"])}</p></div>'
favicon=urllib.parse.quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="{c["theme"]["ink"]}"/><text x="32" y="43" text-anchor="middle" fill="{c["theme"]["accent"]}" font-family="Georgia" font-size="32">HJ</text></svg>')
canonical=f'<link rel="canonical" href="{e(c["meta"]["canonicalUrl"])}">' if c['meta']['canonicalUrl'] else ''
head=f'''<!doctype html><html lang="{e(c['meta']['language'])}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(c['meta']['title'])}</title><meta name="description" content="{e(c['meta']['description'])}"><meta name="theme-color" content="{e(c['theme']['ink'])}"><meta property="og:title" content="{e(c['meta']['title'])}"><meta property="og:description" content="{e(c['meta']['description'])}"><meta property="og:type" content="website">{canonical}<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon}"><link rel="stylesheet" href="styles.css"></head>'''
body=f'''<body id="top"><a class="skip" href="#main">{e(c['labels']['skip'])}</a><header><div class="container nav-row"><a class="brand" href="#top"><span>{e(c['brand']['name'])}</span><small>{e(c['brand']['role'])}</small></a><button class="menu-toggle" aria-expanded="false" aria-controls="navigation">{e(c['labels']['menu'])}</button><nav id="navigation" aria-label="{e(c['labels']['menu'])}">{nav}</nav></div></header><main id="main"><section class="hero container"><div class="hero-copy"><p class="eyebrow">{e(h['eyebrow'])}</p><h1>{e(h['heading'])}</h1><p class="lead">{e(h['text'])}</p><div class="actions">{link('#lehetosegek',h['primary'],'button dark')}{link('#rolam',h['secondary'],'text-link')}</div><div class="hero-meta"><span>{e(h['location'])}</span><span>{e(h['format'])}</span></div></div><figure class="hero-art"><img src="{e(h['image'])}" alt="{e(c['labels']['illustration'])}" width="1536" height="1024" fetchpriority="high"></figure></section><section class="intro"><div class="container intro-grid">{section_head(c['intro'])}<p>{e(c['intro']['text'])}</p></div></section><section class="section container about" id="rolam"><div class="about-copy">{section_head(a)}<p class="lead">{e(a['lead'])}</p>{''.join('<p>'+e(t)+'</p>' for t in a['paragraphs'])}</div><aside>{portrait}<ul class="qualifications">{qual}</ul></aside></section><section class="services section" id="lehetosegek"><div class="container"><div class="section-heading">{section_head(sv)}<p>{e(sv['text'])}</p></div><div class="service-grid">{services}</div></div></section><section class="section container process">{section_head(p)}<ol>{steps}</ol></section><section class="cards" id="kartyak"><div class="container cards-grid"><div class="product-photo"><img src="{e(k['image'])}" alt="{e(k['imageAlt'])}" width="900" height="900" loading="lazy"></div><div>{section_head(k)}<p>{e(k['text'])}</p><p>{e(k['secondary'])}</p>{link(k['url'],k['button'],'button dark')}</div></div></section><section class="section container faq"><div>{section_head(f)}</div><div class="faq-list">{faq}</div></section><section class="contact" id="kapcsolat"><div class="container contact-grid"><div>{section_head(ct)}<p>{e(ct['text'])}</p></div><div class="contact-side"><p class="contact-location">{e(ct['location'])}</p>{contact_html}</div></div></section></main><footer class="container"><div><a href="#top" class="footer-brand">{e(c['brand']['name'])}</a><p>{e(c['footer']['text'])}</p></div><span>© {e(c['footer']['year'])} {e(c['labels']['copyright'])}</span>{link('#top',c['labels']['backTop'],'text-link')}</footer><script src="site.js" defer></script></body></html>'''
(ROOT/'dist/index.html').write_text(head+body)
(ROOT/'dist/content.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
(ROOT/'dist/theme.css').write_text(':root{'+''.join('--'+key+':'+value+';' for key,value in c['theme'].items())+'}\n')
print('Built dist/index.html from config/content.json')
