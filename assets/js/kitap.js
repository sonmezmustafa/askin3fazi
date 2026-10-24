(function () {
  var kitap = document.getElementById('kitap');
  var konum = document.getElementById('konum');

  function sayfa(sinif) {
    var p = document.createElement('div');
    p.className = 'page' + (sinif ? ' ' + sinif : '');
    var ic = document.createElement('div');
    ic.className = 'ic';
    p.appendChild(ic);
    return p;
  }

  function tasiyor(p) {
    var ic = p.firstChild;
    return ic.scrollHeight > ic.clientHeight + 1;
  }

  function dizeler(metin) {
    return metin.replace(/\r/g, '').split('\n').map(function (s) {
      var d = document.createElement('div');
      d.className = s.trim() ? 'dize' : 'dize bos';
      d.textContent = s || ' ';
      return d;
    });
  }

  function yerlestir(oge, sinif, ilk, parcalar, onEk) {
    var sayfalar = [];
    var p = sayfa(sinif);
    if (onEk) onEk(p.firstChild);
    ilk.forEach(function (x) { p.firstChild.appendChild(x); });
    oge.parentNode.insertBefore(p, oge);
    sayfalar.push(p);
    parcalar.forEach(function (x) {
      p.firstChild.appendChild(x);
      if (tasiyor(p) && p.firstChild.children.length > 1) {
        var eski = p.firstChild;
        eski.removeChild(x);
        p = sayfa(sinif + ' devam');
        oge.parentNode.insertBefore(p, oge);
        sayfalar.push(p);
        if (x.classList.contains('bos')) return;
        var bos = eski.querySelectorAll('.dize.bos');
        var kes = bos[bos.length - 1];
        if (kes && kes !== eski.firstChild) {
          while (kes.nextSibling) p.firstChild.appendChild(kes.nextSibling);
          eski.removeChild(kes);
        }
        p.firstChild.appendChild(x);
      }
    });
    oge.parentNode.removeChild(oge);
    return sayfalar;
  }

  var kayitlar = [];

  Array.prototype.forEach.call(kitap.querySelectorAll('.page[data-bolum]'), function (b) {
    kayitlar.push({ tur: 'bolum', ad: b.getAttribute('data-ad'), sayfa: b, id: 'b-' + b.getAttribute('data-bolum') });
  });

  Array.prototype.forEach.call(kitap.querySelectorAll('template.metin-k'), function (t) {
    var tmp = document.createElement('div');
    tmp.innerHTML = t.innerHTML;
    var parcalar = tmp.textContent.replace(/\r/g, '').split('\n').filter(function (s) { return s.trim(); }).map(function (s) {
      var p = document.createElement('p');
      p.textContent = s.trim();
      return p;
    });
    var s = yerlestir(t, 'metin-s', parcalar.splice(0, 1), parcalar);
    kayitlar.push({ tur: 'metin', ad: t.getAttribute('data-baslik'), sayfa: s[0], id: 'o-' + t.getAttribute('data-slug') });
  });

  Array.prototype.forEach.call(kitap.querySelectorAll('template.siir-k'), function (t) {
    var h = document.createElement('h2');
    h.textContent = t.getAttribute('data-baslik');
    var tmp = document.createElement('div');
    tmp.innerHTML = t.innerHTML;
    var parcalar = dizeler(tmp.textContent.replace(/^\n+|\n+$/g, ''));
    var tarih = t.getAttribute('data-tarih');
    if (tarih) {
      var tr = document.createElement('p');
      tr.className = 'tarih';
      tr.textContent = tarih;
      parcalar.push(tr);
    }
    var ilk = [h].concat(parcalar.splice(0, 1));
    var s = yerlestir(t, 'siir-s', ilk, parcalar);
    kayitlar.push({ tur: 'siir', ad: h.textContent, sayfa: s[0], id: 's-' + t.getAttribute('data-slug') });
  });

  var fk = kitap.querySelector('template.fihrist-k');
  var tum = Array.prototype.slice.call(kitap.querySelectorAll('.page'));
  kayitlar.sort(function (a, b) { return tum.indexOf(a.sayfa) - tum.indexOf(b.sayfa); });

  var satirlar = kayitlar.map(function (k) {
    var a = document.createElement('a');
    a.className = 'f-' + k.tur;
    a.href = '#' + k.id;
    a.setAttribute('data-hedef', k.id);
    var ad = document.createElement('span');
    ad.textContent = k.ad;
    var no = document.createElement('span');
    no.className = 'f-no';
    a.appendChild(ad);
    a.appendChild(no);
    return a;
  });
  var kunye = document.getElementById('kunye-k').content.firstElementChild.cloneNode(true);
  satirlar.push(kunye);
  var fb = document.createElement('h2');
  fb.textContent = 'Fihrist';
  yerlestir(fk, 'fihrist-s', [fb], satirlar);

  var sayfalar = Array.prototype.slice.call(kitap.querySelectorAll('.page'));
  var sira = {};
  kayitlar.forEach(function (k) { sira[k.id] = sayfalar.indexOf(k.sayfa); });
  var fihristSayfa = sayfalar.indexOf(kitap.querySelector('.fihrist-s'));
  Array.prototype.forEach.call(kitap.querySelectorAll('a[data-hedef]'), function (a) {
    a.lastChild.textContent = sira[a.getAttribute('data-hedef')];
  });
  sayfalar.forEach(function (p, i) {
    if (i === 0 || i === sayfalar.length - 1 || p.classList.contains('koyu')) return;
    var n = document.createElement('span');
    n.className = 'sayfa-no';
    n.textContent = i;
    p.appendChild(n);
  });

  kitap.classList.remove('olc');

  var pf = new St.PageFlip(kitap, {
    width: 540,
    height: 840,
    size: 'stretch',
    minWidth: 240,
    maxWidth: 720,
    minHeight: 373,
    maxHeight: 1120,
    showCover: true,
    usePortrait: true,
    mobileScrollSupport: true,
    maxShadowOpacity: 0.45,
    flippingTime: 800
  });
  pf.loadFromHTML(sayfalar);

  function yaz() {
    var i = pf.getCurrentPageIndex();
    konum.textContent = i === 0 ? '' : i + ' / ' + (sayfalar.length - 2);
  }

  function hash() {
    var h = location.hash.slice(1);
    if (h && sira[h] !== undefined) pf.turnToPage(sira[h]);
  }

  pf.on('flip', yaz);
  hash();
  yaz();
  window.addEventListener('hashchange', hash);

  kitap.addEventListener('mousedown', function (e) {
    if (e.target.closest('.dize, .ic p, .ic h2')) e.stopPropagation();
  }, true);

  kitap.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-hedef]');
    if (!a) return;
    e.preventDefault();
    e.stopPropagation();
    pf.flip(sira[a.getAttribute('data-hedef')]);
  }, true);

  document.getElementById('geri').addEventListener('click', function () { pf.flipPrev(); });
  document.getElementById('ileri').addEventListener('click', function () { pf.flipNext(); });
  document.getElementById('fihrist-git').addEventListener('click', function () { pf.flip(fihristSayfa); });
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight') pf.flipNext();
    if (e.key === 'ArrowLeft') pf.flipPrev();
  });
})();
