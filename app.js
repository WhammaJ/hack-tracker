(function(){
  var data=null, tab='confirmed';
  var SEV={Critical:0,High:1,Medium:2,Low:3};
  var notes={
    confirmed:'Breaches and attacks confirmed by the affected organization, a government, or law enforcement. Biggest impact first.',
    speculated:'Big outages and incidents people suspected were hacks. These are NOT confirmed hacks. Each shows the official explanation. Biggest impact first.'
  };
  var $=function(id){return document.getElementById(id)};
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function fmtDate(e){
    if(e.dateLabel) return e.dateLabel;
    var d=new Date(e.date+'T12:00:00');
    return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
  }
  function card(e,i){
    var spec=tab==='speculated';
    var h='<article class="card '+esc(e.severity)+'">';
    h+='<div class="row"><h3><span class="rank">#'+(i+1)+'</span>'+esc(e.org)+'</h3><span class="date">'+esc(fmtDate(e))+'</span></div>';
    h+='<div class="meta"><span class="badge sev-'+esc(e.severity)+'">'+esc(e.severity)+'</span>';
    if(spec) h+='<span class="badge unconf">Unconfirmed / speculation</span>';
    e.sectors.forEach(function(s){h+='<span class="badge sector">'+esc(s)+'</span>'});
    h+='</div><p>'+esc(e.summary)+'</p>';
    if(spec){
      h+='<span class="lbl">What people speculated</span><p>'+esc(e.speculation)+'</p>';
      h+='<div class="official"><span class="lbl" style="margin-top:0">Official explanation</span><p>'+esc(e.official)+'</p></div>';
    }
    if(e.impact) h+='<span class="lbl">Impact</span><p>'+esc(e.impact)+'</p>';
    h+='<span class="lbl">Status</span><p class="status">'+esc(e.status)+'</p>';
    h+='<ul class="sources">'+e.sources.map(function(s){return '<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.name)+' ↗</a></li>'}).join('')+'</ul>';
    return h+'</article>';
  }
  function render(){
    var q=$('search').value.trim().toLowerCase(), sec=$('sector').value, sv=$('sev').value;
    var items=data[tab].filter(function(e){
      if(sec && e.sectors.indexOf(sec)<0) return false;
      if(sv && e.severity!==sv) return false;
      if(q){var t=[e.org,e.summary,e.impact,e.status,e.speculation,e.official,e.sectors.join(' ')].join(' ').toLowerCase(); if(t.indexOf(q)<0) return false;}
      return true;
    });
    $('list').innerHTML=items.map(card).join('');
    $('empty').hidden=items.length>0;
    $('tabnote').textContent=notes[tab];
  }
  function setTab(t){
    tab=t;
    document.querySelectorAll('.tab').forEach(function(b){b.classList.toggle('active',b.dataset.tab===t)});
    var secs={};data[t].forEach(function(e){e.sectors.forEach(function(s){secs[s]=1})});
    var cur=$('sector').value;
    $('sector').innerHTML='<option value="">All sectors</option>'+Object.keys(secs).sort().map(function(s){return '<option'+(s===cur?' selected':'')+'>'+esc(s)+'</option>'}).join('');
    render();
  }
  fetch('data.json',{cache:'no-cache'}).then(function(r){return r.json()}).then(function(d){
    data=d;
    ['speculated','confirmed'].forEach(function(k){d[k].sort(function(a,b){return SEV[a.severity]-SEV[b.severity]})});
    var u=new Date(d.lastUpdated+'T12:00:00').toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
    $('updated').textContent=u;$('updated2').textContent=u;
    $('c-confirmed').textContent=d.confirmed.length;$('c-speculated').textContent=d.speculated.length;
    document.querySelectorAll('.tab').forEach(function(b){b.onclick=function(){setTab(b.dataset.tab)}});
    $('search').oninput=render;$('sector').onchange=render;$('sev').onchange=render;
    setTab('confirmed');
  }).catch(function(){$('list').innerHTML='<p class="empty">Could not load data.json.</p>'});
})();
