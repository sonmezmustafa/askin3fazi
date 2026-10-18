import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
SIIRLER = KOK / "_siirler"
KANIT = KOK / "kanit"
OTS_CLI = KOK / "_araclar" / "node_modules" / "opentimestamps" / "ots-cli.js"
TSA_URL = "https://freetsa.org/tsr"
TSA_DOSYALAR = {
    "freetsa-cacert.pem": "https://freetsa.org/files/cacert.pem",
    "freetsa-tsa.crt": "https://freetsa.org/files/tsa.crt",
}
KITAP = "Aşkın 3 Fazı"
TSI = timezone(timedelta(hours=3))


def openssl():
    yol = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
    if not Path(yol).exists() and not shutil.which(yol):
        sys.exit("openssl bulunamadı")
    return yol


def calistir(komut):
    sonuc = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        sys.exit(f"Komut başarısız: {' '.join(map(str, komut))}\n{sonuc.stdout}{sonuc.stderr}")
    return sonuc.stdout + sonuc.stderr


def sertifikalar():
    KANIT.mkdir(exist_ok=True)
    for ad, url in TSA_DOSYALAR.items():
        hedef = KANIT / ad
        if not hedef.exists():
            hedef.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    return KANIT / "freetsa-cacert.pem", KANIT / "freetsa-tsa.crt"


def oku(yol):
    ham = yol.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", ham, re.S)
    if not m:
        sys.exit(f"Ön bilgi yok: {yol.name}")
    satirlar = m.group(1).split("\n")
    bilgi = {}
    for s in satirlar:
        if ":" in s:
            k, v = s.split(":", 1)
            bilgi[k.strip()] = v.strip().strip('"').strip("'")
    return satirlar, bilgi, m.group(2)


def yaz(yol, satirlar, govde, degerler):
    satirlar = list(satirlar)
    for k, v in degerler.items():
        yeni = f'{k}: "{v}"'
        for i, s in enumerate(satirlar):
            if s.split(":", 1)[0].strip() == k:
                satirlar[i] = yeni
                break
        else:
            satirlar.append(yeni)
    yol.write_bytes(("---\n" + "\n".join(satirlar) + "\n---\n" + govde).encode("utf-8"))


def damga_metni(bilgi, govde):
    govde = unicodedata.normalize("NFC", govde)
    satirlar = [s.rstrip() for s in govde.split("\n")]
    while satirlar and not satirlar[0]:
        satirlar.pop(0)
    while satirlar and not satirlar[-1]:
        satirlar.pop()
    baslik = unicodedata.normalize("NFC", bilgi.get("baslik", ""))
    return f"{KITAP}\n{baslik}\n\n" + "\n".join(satirlar) + "\n"


def sha256(yol):
    return hashlib.sha256(yol.read_bytes()).hexdigest()


def tsa_damgala(dosya):
    ca, tsa = sertifikalar()
    with tempfile.TemporaryDirectory() as gecici:
        sorgu = Path(gecici) / "sorgu.tsq"
        calistir([openssl(), "ts", "-query", "-data", str(dosya), "-sha256", "-cert", "-out", str(sorgu)])
        istek = urllib.request.Request(
            TSA_URL, data=sorgu.read_bytes(), headers={"Content-Type": "application/timestamp-query"}
        )
        yanit = Path(f"{dosya}.tsr")
        yanit.write_bytes(urllib.request.urlopen(istek, timeout=60).read())
        cikti = calistir([openssl(), "ts", "-verify", "-in", str(yanit), "-queryfile", str(sorgu),
                          "-CAfile", str(ca), "-untrusted", str(tsa)])
        if "Verification: OK" not in cikti:
            sys.exit(f"TSA doğrulaması geçmedi: {dosya.name}\n{cikti}")
    return tsa_zamani(yanit)


def tsa_zamani(yanit):
    cikti = calistir([openssl(), "ts", "-reply", "-in", str(yanit), "-text"])
    m = re.search(r"Time stamp: (.+?) GMT", cikti)
    zaman = datetime.strptime(" ".join(m.group(1).split()).split(".")[0], "%b %d %H:%M:%S %Y")
    return zaman.replace(tzinfo=timezone.utc).astimezone(TSI)


def ots(*argumanlar):
    if not OTS_CLI.exists():
        sys.exit("OpenTimestamps kurulu değil: _araclar klasöründe 'npm install' çalıştırın")
    return subprocess.run(["node", str(OTS_CLI), *map(str, argumanlar)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def ots_damgala(dosya):
    sonuc = ots("stamp", dosya)
    if not Path(f"{dosya}.ots").exists():
        sys.exit(f"OpenTimestamps damgası oluşmadı: {dosya.name}\n{sonuc.stdout}{sonuc.stderr}")


def surumler(klasor):
    return sorted(klasor.glob("v*.txt"), key=lambda p: int(p.stem[1:]))


def zaman_yazisi(zaman):
    return zaman.strftime("%d.%m.%Y %H:%M") + " (TSİ)"


def damgala(_):
    if not SIIRLER.exists():
        print("Henüz şiir yok.")
        return
    for yol in sorted(SIIRLER.glob("*.html")):
        satirlar, bilgi, govde = oku(yol)
        metin = damga_metni(bilgi, govde).encode("utf-8")
        klasor = KANIT / yol.stem
        klasor.mkdir(parents=True, exist_ok=True)
        mevcut = surumler(klasor)
        if mevcut and mevcut[-1].read_bytes() == metin:
            son = mevcut[-1]
            if bilgi.get("damga_sha256") != sha256(son):
                yaz(yol, satirlar, govde, {
                    "damga_sha256": sha256(son),
                    "damga_zaman": zaman_yazisi(tsa_zamani(Path(f"{son}.tsr"))),
                    "damga_surum": son.stem,
                })
            print(f"{yol.stem}: değişmemiş ({son.stem})")
            continue
        yeni = klasor / f"v{len(mevcut) + 1}.txt"
        yeni.write_bytes(metin)
        zaman = tsa_damgala(yeni)
        ots_damgala(yeni)
        yaz(yol, satirlar, govde, {
            "damga_sha256": sha256(yeni),
            "damga_zaman": zaman_yazisi(zaman),
            "damga_surum": yeni.stem,
        })
        print(f"{yol.stem}: {yeni.stem} damgalandı · {zaman_yazisi(zaman)} · {sha256(yeni)}")


def dogrula_dosya(dosya):
    ca, tsa = sertifikalar()
    tsr = Path(f"{dosya}.tsr")
    tsa_durum = "yok"
    if tsr.exists():
        sonuc = subprocess.run([openssl(), "ts", "-verify", "-data", str(dosya), "-in", str(tsr),
                                "-CAfile", str(ca), "-untrusted", str(tsa)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        tsa_durum = ("TAMAM " + zaman_yazisi(tsa_zamani(tsr))) if "Verification: OK" in sonuc.stdout + sonuc.stderr else "HATALI"
    ots_durum = "yok"
    if Path(f"{dosya}.ots").exists():
        cikti = ots("verify", f"{dosya}.ots").stdout
        if "attests" in cikti or "Success" in cikti:
            ots_durum = "TAMAM (Bitcoin)"
        elif "ending" in cikti:
            ots_durum = "bekliyor (Bitcoin onayı yok, 'yukselt' çalıştırın)"
        else:
            ots_durum = "HATALI"
    print(f"{dosya.parent.name}/{dosya.name}  {sha256(dosya)}\n  TSA: {tsa_durum}\n  OTS: {ots_durum}")


def dogrula(_):
    for dosya in sorted(KANIT.glob("*/v*.txt")):
        dogrula_dosya(dosya)


def yukselt(_):
    for dosya in sorted(KANIT.glob("*/v*.txt.ots")):
        cikti = ots("upgrade", dosya)
        print(f"{dosya.parent.name}/{dosya.name}: {(cikti.stdout + cikti.stderr).strip().splitlines()[-1:]}")


def beyan(arg):
    klasor = Path(arg.klasor)
    if KOK in klasor.resolve().parents or klasor.resolve() == KOK:
        sys.exit("Beyan site klasörünün dışında tutulmalı")
    klasor.mkdir(parents=True, exist_ok=True)
    satirlar = []
    for dosya in sorted(KANIT.glob("*/v*.txt")):
        satirlar.append(f"{dosya.parent.name}/{dosya.name}  {sha256(dosya)}")
    if not satirlar:
        sys.exit("Damgalanmış şiir yok")
    simdi = datetime.now(TSI)
    metin = (
        "BEYAN\n\n"
        f"askin3fazi.com alan adının sahibi ve bu alan adında yayımlanan \"{KITAP}\" adlı şiir kitabının "
        f"yazarı {arg.ad}'dır.\n\n"
        "Aşağıda SHA-256 parmak izi verilen metinlerin tamamı bana aittir.\n\n"
        + "\n".join(satirlar)
        + f"\n\nBeyan tarihi: {zaman_yazisi(simdi)}\n"
    )
    dosya = klasor / f"beyan-{simdi:%Y%m%d-%H%M}.txt"
    dosya.write_bytes(unicodedata.normalize("NFC", metin).encode("utf-8"))
    zaman = tsa_damgala(dosya)
    ots_damgala(dosya)
    print(f"Beyan damgalandı: {dosya}\n  {zaman_yazisi(zaman)} · {sha256(dosya)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ayristirici = argparse.ArgumentParser(prog="damgala")
    alt = ayristirici.add_subparsers(dest="komut")
    alt.add_parser("damgala").set_defaults(is_=damgala)
    alt.add_parser("dogrula").set_defaults(is_=dogrula)
    alt.add_parser("yukselt").set_defaults(is_=yukselt)
    b = alt.add_parser("beyan")
    b.add_argument("--ad", required=True)
    b.add_argument("--klasor", default=str(Path.home() / "askin3fazi-ozel"))
    b.set_defaults(is_=beyan)
    arg = ayristirici.parse_args()
    (getattr(arg, "is_", None) or damgala)(arg)


if __name__ == "__main__":
    main()
