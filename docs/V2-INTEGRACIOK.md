# V2 – konfiguráció, kipróbálás és élesítés

Az eredeti a gyökérben marad, az új bemutató a `/v2/` alatt. A két konfiguráció és a két build független. A v2 alapállapota offline és noindex; a mintaárak és a szövegek még jóváhagyandók.

## Tartalom és működési mód

* `config/content.json`: eredeti oldal, változatlan.
* `v2/config/content.json`: új szövegek, ajánlatok, árak, képek, gombfeliratok, GYIK, bemutató adatkezelési szöveg.
* `v2/config/runtime.json`: `mode: "offline"` vagy `"online"`; funkciókapcsolók; API alapcím; nyilvános Messenger-azonosító; mintaidőpontok. **Titkos kulcsot ide tilos írni.**
* `backend/config.example.json`: privát szerverkonfiguráció mintája. A kitöltött példányt a repón és a webgyökéren kívül kell tárolni, pl. `/etc/hauberjudit/config.private.json`, 600-as jogosultsággal. A valódi példány nem kerül GitHubra.

`python3 build.py` és `python3 build_v2.py` készíti a Pages-csomagot. Az eredeti build és a fájljai nem változtak. Helyi előnézet: `python3 -m http.server 8080 --directory dist`.

Offline módban a statikus konfiguráció és helyi kép betöltésén kívül nincs hálózati integráció. A kontakt, foglalás, Messenger és elfogadás szimuláció. A próbaadatok kizárólag memóriában vannak. Frissítés után elvesznek. Az ICS a látogató saját kattintására letölthető minta; nem küld meghívót.

## Élesítés előfeltételei

1. Judit jóváhagyja a szövegeket, képzési megnevezéseket, árakat, szolgáltatási és lemondási feltételeket, helyszínt és tényleges kapacitást.
2. Az éles adatkezelési tájékoztatót és szükséges szolgáltatási feltételeket véglegesíteni kell. A bemutató szöveg nem éles jogi dokumentum. Az `adatkezeles` oldal tartalmát ennek megfelelően kell lecserélni. Ha hosszabb jogi dokumentum szükséges, a buildet új tartalmi szekciókkal kell bővíteni.
3. Külön HTTPS API tárhely kell. GitHub Pages nem futtatja a Python háttérszolgáltatást. Ez a megvalósítás **Python 3.12+ folyamatot futtató környezetre/VPS-re** készült. Egy hagyományos PHP-s megosztott RackForest tárhely kompatibilitása nincs igazolva; oda a backend nem tölthető fel futtatható szolgáltatásként ellenőrzés nélkül.
4. A szerver reverse proxy mögött fusson, `127.0.0.1` kötésen. A proxy biztosítson TLS-t, 8 KB kéréslimitet, időlimitet és rate limitet. Az IP-alapú alkalmazáslimit a közvetlen peer IP-t használja; proxy mögött a proxy szűrje a valódi kliens IP-ket. Ne bízzunk ellenőrizetlen X-Forwarded-For fejlécekben.
5. Az engedélyezett webes origin pontos legyen (`https://realabu.github.io`, később `https://hauberjudit.hu`). Az API adatbázisának könyvtára 700-as jogosultsággal és titkosított, korlátozott hozzáférésű mentéssel működjön. WAL fájlok is személyes adatot tartalmazhatnak.
6. Az adatmegőrzési/törlési idők jóváhagyása és a tényleges törlési folyamat beállítása szükséges. A rendszer nem talál ki jogi megőrzési időt, és még nincs automatikus adatmegőrzési törlőfeladat. A levelező, naptár és mentések adataira is vonatkozzon a folyamat. Az idempotencia és outbox táblákban is lehet név, e-mail és állapottoken.
7. A publikus runtime `legalApproved` és `contentApproved` legyen true, a review sáv enabled false, a `mode` online és az API HTTPS. A build ellenőrzi ezt. A szerver saját jóváhagyási kapcsolói is kötelezők.

Futtatás: `python3 backend/server.py --config /etc/hauberjudit/config.private.json`. A backend nem indul el hiányzó hitelesítéssel, jóváhagyásokkal vagy találkozási részletekkel.

## Google Calendar

Judit saját dedikált naptárát használjuk, a naptár nem lesz nyilvános. A privát konfiguráció: `calendarId`, OAuth `clientId`, `clientSecret`, `refreshToken`, timezone. **API key önmagában nem ad írási jogosultságot.**

Google Cloud projektben engedélyezni kell a Calendar API-t, OAuth consent screen és kliens szükséges. A Judit által megadott naptárra olvasási/írási engedély kell, OAuth offline hozzáféréssel (`calendar.events` scope). A refresh tokent Judit saját engedélyezése adja. Teszt státuszú OAuth alkalmazásoknál a refresh token élettartama korlátozott lehet; az éles consent státuszt és szükséges ellenőrzést a Google aktuális szabályai szerint kell beállítani.

A foglalható esemény neve például:

`[HJ:FOGLALHATO] Egyéni coaching`

Leírása **csak JSON**, pl.:

```json
{"service":"coaching","capacity":1}
```

Anyakörnél:

```json
{"service":"anyakor","capacity":6}
```

A kezdés és befejezés az eseményből jön; időtartam egyezzen a konfigurált szolgáltatással (60/120 perc). Ismétlődő Google-esemény is használható; a backend az előfordulásokat kéri le. 120 napra előre jelenít meg időpontokat, a hibás paraméterű és egész napos foglalási jelölőket kihagyja. Nem jelölt privát foglaltságokkal átfedő időpontokat elrejti. Csak az engedélyezett szolgáltatás címe, ára, időpontja és kapacitása kerül ki az API-n; privát leírás nem.

A függő és elfogadott jelentkezések SQLite-tranzakcióval foglalják a férőhelyet. Google-esemény létrehozása és az e-mail-küldés tartós feldolgozási sorból történik. A naptáresemény azonosítója determinisztikus, így egy újrapróbálás nem hoz létre második eseményt. Google-hiba esetén a kapcsolódó megerősítő e-mail vár. Az admin felületen látszik a sor és az újrapróbálás.

Függőben nincs vendégmeghívó: az ügyfél visszaigazoló levelet kap, az állapot egyedi hivatkozáson ellenőrizhető. Elfogadás után a Google-eseménybe `needsAction` állapottal vendégként bekerül, és meghívót kap; az e-mail melléklete ICS is. **Az ügyfél saját naptárába kerülést a Google és az ügyfél beállításai befolyásolják; ezt nem lehet garantálni.** Csoportnál minden ügyfél külön, privát eseményt kap, a vendégek nem látják egymás adatait.

Az admin jóváhagyás ellenőrzi, hogy az eredeti naptárablak még megvan-e. A marker és a már beérkezett foglalások időpontjának utólagos módosítása jelenleg nem szinkronizálja át automatikusan a foglalásokat: előbb adminban visszavonás, ügyfél-egyeztetés, majd új időpont szükséges. A naptárt kizárólag ez a szolgáltatás használja foglalásokra; több független foglalási rendszer összehangolása nincs implementálva.

## Admin, e-mail, emlékeztető

`/v2/admin.html`: éles módban privát admin tokennel elérhető kezelő. Generálás: `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. A kulcs nem kerül URL-be vagy localStorage-ba. Az admin egyelőre egy felhasználóhoz készült; több admin, szerepkör és auditnapló későbbi bővítés.

SMTP: host, port, username, password, from, ownerEmail; STARTTLS vagy implicit TLS. `meetingDetails`: jóváhagyott pontos cím, fizetési és lemondási feltételek. A foglalás állapothivatkozása az első levélben szerepel, a token SHA-256 hashével ellenőrizhető. A webes URL fragmentjéből a kliens rögtön eltávolítja; az admin vagy a naptár nem kapja meg.

A függő foglalás alapértelmezetten 48 óra után lejár. Elfogadás után, ha még több mint 24 óra van hátra, 24 órás emlékeztető kerül sorba. Visszavont alkalomhoz nem küld emlékeztetőt. SMTP legalább-egyszer kézbesítés: ha a szolgáltató fogadta a levelet, de a kapcsolat megszakad, újrapróbálásnál ritkán duplikált levél lehet. Ez a saját SMTP protokoll korlátja; idempotens e-mail API-val tovább javítható.

## Messenger és Meta

A webes kapcsolatfelvétel a szakmai oldal `m.me` hivatkozásával működik. A régi beágyazott Facebook Customer Chat Pluginra nem építünk. Az oldalon nincs Meta tracking pixel, SDK vagy automatikusan betöltődő iframe. Offline módban a Messenger gomb is csak helyi visszajelzést ad.

Opcionális valódi Messenger webhook: privát `appSecret`, `verifyToken`, `pageAccessToken`, `pageId`, aktuális és engedélyezett `graphVersion`. A Graph API verziót nem találjuk ki; az appban elérhető, érvényes verziót kell megadni. Meta app és a szükséges oldal-/Messenger-jogosultságok, előfizetés a messages eseményekre és esetleges app review kell. A POST üzenetek HMAC-aláírását ellenőrizzük, a duplikált message id-kat kihagyjuk, echo és 24 óránál régebbi eseményre nem válaszolunk. A visszajelzés egyszerű, előre megírt nyugtázás; nem AI-tanácsadás. Az üzenet tartalmát nem tároljuk a webhookból.

A Messenger integráció éles fiókkal és jóváhagyott jogosultságokkal nincs még végigpróbálva. A foglalási e-mailt nem küldjük önkényesen Messengerre: ahhoz külön ügyfélazonosítás és engedélyezett üzenetküldési folyamat kellene.

## Tesztek és éles átadás

`python3 -m unittest discover -s tests -p 'test_*.py'` és `node --test tests/offline.test.mjs`.

Tesztelt: utolsó férőhely egyidejű foglalása, csoportkapacitás, ismételt beküldés, jogosulatlan állapotolvasás, tiltott átmenet, lemondás, lejárat, privát események elrejtése, naptárhiba miatti e-mail-várakozás, webhook-aláírás és deduplikáció, offline nulla backendhívás. Google és SMTP tesztadapterrel; az éles szolgáltatókhoz a saját beállításokkal külön végponttól végpontig próba kell.

Indulás előtt valós teszt naptár és e-mail címek: függő levél → Google pending esemény → elfogadás → privát meghívó → megerősítő e-mail → ICS → ügyfél-visszavonás → eseménytörlés → emlékeztető törlésének ellenőrzése. Ezután eredeti/v2 mobil összehasonlítás három leendő érdeklődővel.
