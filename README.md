# HauberJudit.hu — statikus bemutatkozó oldal

A weboldal összes szövege, navigációja, képhivatkozása és színkódja a `config/content.json` fájlban szerkeszthető. A generálás Python 3-mal, külső csomag nélkül fut:

```sh
python3 build.py
```

A kész oldal a `dist` könyvtárban található. Ennek a könyvtárnak a tartalmát kell bármely statikus tárhelyre feltölteni. Nincs WordPress, adatbázis vagy szerveroldali futtatási igény. A szövegek már az elkészült HTML-ben szerepelnek, így a tartalom JavaScript nélkül is olvasható. A JavaScript csak a mobilmenüt kezeli. A `dist/content.json` a konfiguráció olvasható másolata; az éles módosítást a `config/content.json` fájlban végezd, majd generáld újra az oldalt.

## GitHub Pages és frissítés

A `.github/workflows/pages.yml` minden `main` ágra kerülő módosítás után futtatja a `build.py` generátort, majd a `dist` tartalmát publikálja GitHub Pagesre. A repó Settings → Pages beállításában a forrás **GitHub Actions** legyen. A munkafolyamat az Actions fülön kézzel is indítható.

A szövegmódosításhoz szerkeszd a `config/content.json` fájlt, és commitold a `main` ágra. A publikus oldal automatikusan frissül a sikeres munkafolyamat után; a generált `dist/index.html`, `dist/content.json` és `dist/theme.css` fájlokat nem szükséges kézzel szerkeszteni. Helyi előnézethez futtasd a fenti generálást, majd `python3 -m http.server 8000 --directory dist`.

RackForest tárhelyen a `dist` könyvtár **tartalmát** kell a domain dokumentumgyökerébe másolni. Egy egyszerű `git pull` önmagában nem építi újra az oldalt: utána futtasd a generátort, vagy használj külön CI/SFTP publikálást. A GitHub Pages telepítés nem állít be RackForest-hozzáférést és nem módosít DNS-t.

A repo kizárólag a weboldal publikálható forrását és képeit tartalmazza; hangfelvétel, interjúleirat, belépési adat és Google Calendar-kulcs nem kerül bele. A tervezett foglalóhoz és levélküldő űrlaphoz külön szerveroldali szolgáltatás szükséges; titkokat soha ne tegyél a konfigurációba.

## Elsőként kitöltendő mezők

- `contact.email`: coachinghoz használható e-mail-cím. Ha ki van töltve, automatikusan megjelenik az e-mail gomb. Az olvasó levelezőjét nyitja meg; nincs adatokat gyűjtő vagy levélküldést színlelő űrlap.
- `contact.messengerUrl`: a választott Messenger-oldal HTTPS-linkje.
- `contact.facebookUrl`: a végleges Facebook-oldal HTTPS-linkje.
- `about.portrait`: saját portré helyi képfájlja, például `assets/judit.webp`. Másold a képet a `dist/assets` mappába. Kitöltve a monogramot a valódi portré váltja.
- `meta.canonicalUrl`: csak a végleges domain tényleges bekötése után állítsd `https://hauberjudit.hu/` értékre. A `meta.domain` a tervezett domain, nem jelent domainregisztrációt vagy DNS-beállítást.
- Díjak és meghirdetett anyakör-időpontok: a `faq`, `services` és `contact` szövegeiben módosíthatók. Az interjúban még nem volt végleges ár, időpont vagy kedvezmény, ezért ilyen adatokat nem találtunk ki.

A `null` értékek szándékosan hiányzó adatok. A kapcsolat rész addig tájékoztató szöveget jelenít meg, amíg e-mail vagy Messenger-link nem kerül a konfigurációba. A kéziratot Judit szakmai és személyes bemutatkozásként jóvá kell hagyja; az interjúban kimondott képesítésekre épül, nem állít befejezett pszichológus-végzettséget.

## Képek és tartalomforrások

- `assets/anyakor-illusztracio.webp`: ehhez az oldalhoz készített AI-illusztráció; nem Judit portréja, és nem valódi résztvevők fényképe.
- `assets/anya-lettem-kartyak.webp`: az Anya lettem kártyák saját webáruházának termékfotója. Forrás: https://anyalettemkartyak.hu/ . A kérés és az interjú a terméket a saját terméketekhez kapcsolta.
- A bemutatkozás és a szolgáltatási keretek forrása a 2026. október 1-jén átadott interjú. A marketingmegfogalmazások szerkesztett induló szövegek, nem szó szerinti idézetek.
- Mother Nature módszertani háttér: https://mothernaturemagyarorszag.hu/mother-nature-anyakorok-segitoknek/
- Perinatus képzési háttér: https://perinatus.hu/program/szuleselmeny-feldolgozas-szakembereknek/
- Színvilág-referencia az interjú szerint: https://okostimi.hu/ . Átvett szöveg és fénykép nincs erről az oldalról.

## Felépítés

`config/content.json` — tartalom és színek

`build.py` — statikus HTML-generátor

`dist/index.html` — kész, keresőmotorok által olvasható oldal

`dist/styles.css` — reszponzív stílusok

`dist/theme.css` — konfigurációból generált színváltozók

`dist/site.js` — akadálymentes mobilmenü

`dist/assets/` — helyi, optimalizált WebP képek

Az első változat egyoldalas: bemutatkozás, képesítések, részletezhető szolgáltatások, a folyamat, kártyák, gyakori kérdések és kapcsolat. Nincs időpontfoglaló, vásárlási funkció vagy online szolgáltatás elérhetőségét ígérő gomb; a kártyák a meglévő webáruházban vásárolhatók meg.
