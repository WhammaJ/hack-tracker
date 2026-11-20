(function(){
  var DISQUS_SHORTNAME = 'hacktracking';
  var tab = 'confirmed';
  var region = 'us';
  var disqusLoaded = false;
  var openId = null;
  var $ = function(id){ return document.getElementById(id); };

  function regionFromUrl(){
    var p = (new URLSearchParams(location.search).get('region') || '').toLowerCase();
    if(p === 'us' || p === 'usa') return 'us';
    if(p === 'world' || p === 'worldwide') return 'world';
    return null;
  }

  function preferredRegion(){
    var fromUrl = regionFromUrl();
    if(fromUrl) return fromUrl;
    var hash = (location.hash || '').replace(/^#/, '');
    if(hash){
      var el = document.getElementById(hash);
      if(el && el.classList.contains('card') && el.getAttribute('data-us') !== '1'){
        return 'world';
      }
    }
    try {
      if(localStorage.getItem('hacktracker-region') === 'world') return 'world';
    } catch (e) {}
    return 'us';
  }

  function cardsInTab(){
    var section = document.getElementById(tab + '-section');
    return section ? section.querySelectorAll('article.card') : [];
  }

  function inCurrentRegion(card){
    return region === 'world' || card.getAttribute('data-us') === '1';
  }

  function cardsInView(){
    return Array.prototype.filter.call(cardsInTab(), inCurrentRegion);
  }

  function allSectors(){
    var seen = {};
    cardsInView().forEach(function(card){
      (card.getAttribute('data-sectors') || '').split(',').forEach(function(s){
        s = s.trim();
        if(s) seen[s] = true;
      });
    });
    return Object.keys(seen).sort();
  }

  function fillSectors(){
    var sel = $('sector');
    var cur = sel.value;
    var options = allSectors();
    if(cur && options.indexOf(cur) < 0) cur = '';
    var html = '<option value="">All sectors</option>';
    options.forEach(function(s){
      var selAttr = s === cur ? ' selected' : '';
      html += '<option' + selAttr + '>' + s + '</option>';
    });
    sel.innerHTML = html;
  }

  function updateCounts(){
    document.querySelectorAll('.view-count').forEach(function(el){
      var val = region === 'us' ? el.getAttribute('data-count-us') : el.getAttribute('data-count-world');
      if(val != null) el.textContent = val;
    });
  }

  function updateRegionUi(){
    document.documentElement.setAttribute('data-region', region);
    var kicker = $('region-kicker');
    if(kicker){
      kicker.textContent = region === 'us'
        ? 'Showing hacks in the United States'
        : 'Showing hacks worldwide';
    }
    document.querySelectorAll('.region-btn').forEach(function(btn){
      var on = btn.getAttribute('data-region') === region;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    updateCounts();
  }

  function persistRegion(){
    try { localStorage.setItem('hacktracker-region', region); } catch (e) {}
    var url = new URL(location.href);
    url.searchParams.set('region', region);
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }

  function setRegion(next, persist){
    region = next === 'world' ? 'world' : 'us';
    updateRegionUi();
    if(persist !== false) persistRegion();
    fillSectors();
    render();
  }

  function render(){
    var q = $('search').value.trim().toLowerCase();
    var sec = $('sector').value;
    var sv = $('sev').value;
    var visible = 0;
    cardsInTab().forEach(function(card){
      var ok = inCurrentRegion(card);
      if(ok && sv && card.getAttribute('data-severity') !== sv) ok = false;
      if(ok && sec){
        var sectors = (card.getAttribute('data-sectors') || '').split(',');
        if(sectors.indexOf(sec) < 0) ok = false;
      }
      if(ok && q){
        var blob = (card.getAttribute('data-search') || '').toLowerCase();
        if(blob.indexOf(q) < 0) ok = false;
      }
      card.hidden = !ok;
      if(ok) visible++;
    });
    var empty = $('empty');
    empty.hidden = visible > 0;
    if(region === 'us'){
      empty.textContent = 'No matching entries in the United States. Switch to Worldwide, or try a different search or filter.';
    } else {
      empty.textContent = 'No matches. Try a different search or filter.';
    }
  }

  function setTab(t){
    tab = t;
    document.querySelectorAll('.tab').forEach(function(el){
      var on = el.getAttribute('data-tab') === t;
      el.classList.toggle('is-active', on);
      el.classList.toggle('active', on);
      el.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.querySelectorAll('.results').forEach(function(sec){
      var on = sec.getAttribute('data-tab') === t;
      sec.classList.toggle('is-active', on);
    });
    fillSectors();
    render();
  }

  function moveThread(host){
    var thread = $('disqus_thread');
    if(!thread){
      thread = document.createElement('div');
      thread.id = 'disqus_thread';
    }
    host.appendChild(thread);
    return thread;
  }

  function closeComments(){
    if(!openId) return;
    var panel = $('comments-' + openId);
    var btn = document.querySelector('.comments-toggle[data-entry-id="' + openId + '"]');
    if(panel) panel.hidden = true;
    if(btn) btn.setAttribute('aria-expanded', 'false');
    openId = null;
  }

  function disqusConfig(id){
    return function(){
      this.page.identifier = id;
      this.page.url = 'https://hacktracking.com/#' + id;
    };
  }

  function loadOrResetDisqus(id){
    if(window.DISQUS){
      window.DISQUS.reset({ reload: true, config: disqusConfig(id) });
      return;
    }
    window.disqus_config = disqusConfig(id);
    if(disqusLoaded) return;
    var s = document.createElement('script');
    s.src = 'https://' + DISQUS_SHORTNAME + '.disqus.com/embed.js';
    s.setAttribute('data-timestamp', String(Date.now()));
    s.async = true;
    document.body.appendChild(s);
    disqusLoaded = true;
  }

  function openComments(id){
    if(openId === id){
      closeComments();
      return;
    }
    closeComments();
    var panel = $('comments-' + id);
    var btn = document.querySelector('.comments-toggle[data-entry-id="' + id + '"]');
    if(!panel || !btn) return;
    var host = panel.querySelector('.comments-host');
    moveThread(host);
    panel.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    openId = id;
    loadOrResetDisqus(id);
  }

  function entryIdFromHash(){
    var hash = (location.hash || '').replace(/^#/, '');
    if(!hash) return null;
    if(hash === 'confirmed-section' || hash === 'speculated-section' || hash === 'about' || hash === 'definition' || hash === 'main'){
      return { section: hash };
    }
    var el = document.getElementById(hash);
    if(el && el.classList.contains('card')){
      var section = el.closest('.results');
      return { entry: hash, tab: section ? section.getAttribute('data-tab') : 'confirmed' };
    }
    return null;
  }

  function applyHash(){
    var info = entryIdFromHash();
    if(!info) return;
    if(info.entry){
      var card = document.getElementById(info.entry);
      if(card && card.getAttribute('data-us') !== '1' && region === 'us' && !regionFromUrl()){
        setRegion('world');
      }
    }
    if(info.tab) setTab(info.tab);
    if(info.section === 'speculated-section') setTab('speculated');
    if(info.section === 'confirmed-section') setTab('confirmed');
    var target = document.getElementById((info.entry || info.section || ''));
    if(target){
      target.scrollIntoView({ block: 'start' });
    }
  }

  document.querySelectorAll('.tab').forEach(function(el){
    el.addEventListener('click', function(ev){
      ev.preventDefault();
      setTab(el.getAttribute('data-tab'));
    });
  });
  document.querySelectorAll('.region-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      setRegion(btn.getAttribute('data-region'));
    });
  });
  $('search').addEventListener('input', render);
  $('sector').addEventListener('change', render);
  $('sev').addEventListener('change', render);
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.comments-toggle');
    if(!btn) return;
    openComments(btn.getAttribute('data-entry-id'));
  });
  window.addEventListener('hashchange', applyHash);

  setRegion(preferredRegion(), false);
  if(location.hash) applyHash();
  else setTab('confirmed');
  persistRegion();
})();
