(function(){
  var DISQUS_SHORTNAME = 'hacktracking';
  var tab = 'confirmed';
  var disqusLoaded = false;
  var openId = null;
  var $ = function(id){ return document.getElementById(id); };

  function cardsInTab(){
    var section = document.getElementById(tab + '-section');
    return section ? section.querySelectorAll('article.card') : [];
  }

  function allSectors(){
    var seen = {};
    cardsInTab().forEach(function(card){
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
    var html = '<option value="">All sectors</option>';
    allSectors().forEach(function(s){
      var selAttr = s === cur ? ' selected' : '';
      html += '<option' + selAttr + '>' + s + '</option>';
    });
    sel.innerHTML = html;
  }

  function render(){
    var q = $('search').value.trim().toLowerCase();
    var sec = $('sector').value;
    var sv = $('sev').value;
    var visible = 0;
    cardsInTab().forEach(function(card){
      var ok = true;
      if(sv && card.getAttribute('data-severity') !== sv) ok = false;
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
    $('empty').hidden = visible > 0;
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
  $('search').addEventListener('input', render);
  $('sector').addEventListener('change', render);
  $('sev').addEventListener('change', render);
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.comments-toggle');
    if(!btn) return;
    openComments(btn.getAttribute('data-entry-id'));
  });
  window.addEventListener('hashchange', applyHash);

  fillSectors();
  if(location.hash) applyHash();
  else setTab('confirmed');
})();
