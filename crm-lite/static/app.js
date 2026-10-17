const STAGES = ['Поиск', 'Квалификация', 'Предложение', 'Переговоры', 'Успешно', 'Отказ'];
const COLORS = ['#1677f2', '#7847d7', '#f59e0b', '#12b8a6', '#32b367', '#e95d66', '#7f93b1'];
const state = { view: 'dashboard', leads: [], overview: null, selectedId: null, search: '', status: '' };
const el = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const money = value => '$' + new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(value) || 0);
const number = value => new Intl.NumberFormat('ru-RU').format(Number(value) || 0);
const dateText = value => value ? new Date(value.slice(0,10) + 'T00:00:00').toLocaleDateString('ru-RU') : '—';
const pct = (part, total) => total ? Math.round(part / total * 100) : 0;

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Ошибка запроса');
  return data;
}
function toast(message, error = false) {
  const node = el('toast'); node.textContent = message; node.classList.toggle('error', error); node.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('show'), 3500);
}
async function refresh() {
  try {
    [state.leads, state.overview] = await Promise.all([api('/api/leads'), api('/api/overview')]);
    render();
  } catch (err) { toast(err.message, true); }
}
function setView(view) {
  state.view = view;
  document.querySelectorAll('.nav-link').forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
  el('breadcrumb').textContent = ({dashboard:'Обзор', leads:'Клиенты', pipeline:'Сделки', reports:'Отчёты'})[view];
  render();
}
function pageHead(eyebrow, title, description, action = '') {
  return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${action}</div>`;
}
function empty(text) { return `<div class="empty"><div class="empty-icon">◈</div><strong>Пока нет данных</strong><p>${text}</p><button class="button button-primary" data-action="add">Добавить клиента</button></div>`; }
function metric(label, value, icon, tint, sub = '') {
  return `<div class="metric"><div class="metric-top"><span>${label}</span><span class="metric-icon ${tint}">${icon}</span></div><div class="metric-value">${value}</div><div class="metric-sub">${sub || '&nbsp;'}</div></div>`;
}
function section(title, body, extra = '') { return `<section class="panel"><div class="panel-head"><h2>${title}</h2>${extra}</div>${body}</section>`; }
function sourceDonut(data) {
  const entries = Object.entries(data).sort((a,b) => b[1]-a[1]).slice(0,7), total = entries.reduce((s,e) => s+e[1],0);
  if (!total) return '<div class="panel-empty">Добавьте клиентов, чтобы увидеть источники</div>';
  let cursor = 0; const stops = entries.map(([_, count], i) => { const from = cursor; cursor += pct(count,total); return `${COLORS[i]} ${from}% ${cursor}%`; }).join(', ');
  return `<div class="donut-layout"><div class="donut" style="background:conic-gradient(${stops})"><div class="donut-hole"><strong>${total}</strong><span>клиентов</span></div></div><div class="legend">${entries.map(([name,count],i) => `<div><i style="background:${COLORS[i]}"></i><span>${esc(name)}</span><strong>${count}</strong></div>`).join('')}</div></div>`;
}
function stageBars(byStage) {
  const max = Math.max(1, ...STAGES.map(s => byStage[s]?.count || 0));
  return `<div class="stage-bars">${STAGES.map((stage,i) => {const item=byStage[stage]||{count:0,amount:0}; return `<div class="stage-row"><span>${stage}</span><div class="bar-track"><div class="bar-fill" style="width:${item.count/max*100}%;background:${COLORS[i]}"></div></div><b>${item.count}</b></div>`}).join('')}</div>`;
}
function trend(data) {
  const entries = Object.entries(data), width = 600, height = 155, top = 18, bottom = 130;
  if (!entries.length) return '<div class="panel-empty">Доход появится после выигранных сделок с датой закрытия</div>';
  const max = Math.max(1,...entries.map(e=>e[1]));
  const pts = entries.map((e,i) => ({x: 24 + i * (width-48)/Math.max(1,entries.length-1), y: bottom - e[1]/max*(bottom-top), label:e[0], value:e[1]}));
  const line = pts.map(p=>`${p.x},${p.y}`).join(' ');
  return `<div class="trend-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Выручка по месяцам"><line x1="24" y1="${bottom}" x2="576" y2="${bottom}" stroke="#dce5ef"/><polyline points="${line}" fill="none" stroke="#1677f2" stroke-width="3" stroke-linejoin="round"/>${pts.map(p=>`<circle cx="${p.x}" cy="${p.y}" r="4" fill="#1677f2"><title>${esc(p.label)}: ${money(p.value)}</title></circle>`).join('')}</svg><div class="trend-labels">${entries.map(([month])=>`<span>${esc(month)}</span>`).join('')}</div></div>`;
}
function dealRows(rows) {
  if (!rows.length) return '<div class="panel-empty">Сделок пока нет</div>';
  return `<div class="table-wrap"><table><thead><tr><th>Клиент / компания</th><th>Этап</th><th>Сумма</th><th>Дата закрытия</th></tr></thead><tbody>${rows.map(r=>`<tr data-open="${r.id}"><td><strong>${esc(r.name)}</strong><small>${esc(r.company || 'Без компании')}</small></td><td><span class="stage-chip">${esc(r.stage)}</span></td><td class="amount">${money(r.amount)}</td><td>${dateText(r.close_date)}</td></tr>`).join('')}</tbody></table></div>`;
}
function dashboard() {
  const o=state.overview; if (!o) return '';
  return pageHead('АНАЛИТИКА И ПРОДАЖИ', 'Обзор CRM', 'Ключевые показатели и движение сделок в одном месте.') +
    `<div class="metrics">${metric('Всего клиентов',number(o.total),'♙','blue','В базе CRM')}${metric('Квалифицированы',number(o.qualified),'✓','green',`${pct(o.qualified,o.total)}% от всех клиентов`)}${metric('Выиграно сделок',number(o.won),'◈','purple',`Конверсия ${o.win_rate}%`)}${metric('Выручка',money(o.revenue),'$','orange','По успешным сделкам')}</div>` +
    `<div class="metrics metrics-small">${metric('Открытый портфель',money(o.pipeline),'▥','blue','Сумма активных сделок')}${metric('Прогноз',money(o.forecast),'↗','green','С учётом вероятности')}${metric('Задачи к сегодня',number(o.due),'◷','orange','Просроченные и на сегодня')}${metric('Обращения открыты',number(o.open_cases),'◉','purple',o.satisfaction == null ? 'Оценка не указана' : `Средняя оценка ${o.satisfaction}/10`)}</div>` +
    `<div class="grid two">${section('Клиенты по источникам',sourceDonut(o.by_source))}${section('Воронка сделок',stageBars(o.by_stage),`<span class="panel-extra">${number(o.total)} всего</span>`)}</div>` +
    `<div class="grid two">${section('Динамика выручки',trend(o.revenue_months))}${section('Крупнейшие сделки',dealRows(o.top_deals))}</div>`;
}
function filteredLeads() {
  const query=state.search.toLocaleLowerCase('ru');
  return state.leads.filter(r => (!query || [r.name,r.company,r.email,r.phone].some(v=>String(v||'').toLocaleLowerCase('ru').includes(query))) && (!state.status || r.status===state.status));
}
function statusChip(status) { return `<span class="status-chip status-${({Новый:'new','В работе':'work',Квалифицирован:'qualified',Выигран:'won',Проигран:'lost'})[status]||'new'}">${esc(status)}</span>`; }
function leadsPage() {
  const rows=filteredLeads();
  const action='<a class="button button-muted" href="/api/export.csv">↓ Экспорт CSV</a>';
  return pageHead('КЛИЕНТСКАЯ БАЗА','Клиенты','Контакты, статусы и следующие шаги по каждому клиенту.',action) +
    `<div class="panel"><div class="toolbar"><input id="searchInput" type="search" placeholder="Поиск по имени, компании, email или телефону" value="${esc(state.search)}"><select id="statusFilter"><option value="">Все статусы</option>${['Новый','В работе','Квалифицирован','Выигран','Проигран'].map(s=>`<option ${state.status===s?'selected':''}>${s}</option>`).join('')}</select><span class="result-count">${rows.length} из ${state.leads.length}</span></div>`+
    (rows.length ? `<div class="table-wrap"><table class="leads-table"><thead><tr><th>Клиент</th><th>Компания</th><th>Статус</th><th>Этап</th><th>Ответственный</th><th>Сумма</th><th>Напомнить</th></tr></thead><tbody>${rows.map(r=>`<tr data-open="${r.id}"><td><strong>${esc(r.name)}</strong><small>${esc(r.email||r.phone||'Контакт не указан')}</small></td><td>${esc(r.company||'—')}</td><td>${statusChip(r.status)}</td><td>${esc(r.stage)}</td><td>${esc(r.assignee||'—')}</td><td class="amount">${money(r.amount)}</td><td>${dateText(r.follow_up)}</td></tr>`).join('')}</tbody></table></div>` : empty(state.leads.length ? 'Попробуйте изменить фильтр или строку поиска.' : 'Добавьте первого клиента, чтобы начать работу.')) + '</div>';
}
function pipelinePage() {
  const active=STAGES.filter(s=>s!=='Отказ');
  return pageHead('ПРОДАЖИ','Воронка сделок','Открывайте карточки, чтобы обновлять этапы и суммы.') + `<div class="pipeline">${active.map((stage,i)=>{const rows=state.leads.filter(r=>r.stage===stage); return `<section class="pipeline-col"><div class="pipeline-head"><div><span class="stage-dot" style="background:${COLORS[i]}"></span><strong>${stage}</strong></div><span>${rows.length}</span></div><div class="pipeline-total">${money(rows.reduce((s,r)=>s+r.amount,0))}</div><div class="pipeline-cards">${rows.map(r=>`<button class="deal-card" data-open="${r.id}"><strong>${esc(r.name)}</strong><span>${esc(r.company||'Без компании')}</span><div><b>${money(r.amount)}</b><small>${r.probability}%</small></div></button>`).join('') || '<div class="col-empty">Нет сделок</div>'}</div></section>`}).join('')}</div>`;
}
function reportsPage() {
  const o=state.overview; if(!o) return '';
  const reps=Object.entries(o.by_rep).sort((a,b)=>b[1].amount-a[1].amount);
  const priority={Высокий:0,Средний:0,Низкий:0}; state.leads.forEach(r=>{if(r.priority in priority) priority[r.priority]++});
  return pageHead('ОТЧЁТЫ','Продажи и клиенты','Показатели рассчитаны по текущим данным CRM.')+
    `<div class="metrics">${metric('Клиенты',number(o.total),'♙','blue')}${metric('Доля выигранных',`${o.win_rate}%`,'✓','green')}${metric('Прогноз',money(o.forecast),'↗','purple')}${metric('Средняя оценка',o.satisfaction == null ? '—' : `${o.satisfaction}/10`,'★','orange')}</div>`+
    `<div class="grid two">${section('Продажи по сотрудникам',reps.length ? `<div class="rep-list">${reps.map(([name,v])=>`<div><span>${esc(name)}</span><strong>${money(v.amount)}</strong><small>${v.count} клиентов</small></div>`).join('')}</div>`:'<div class="panel-empty">Назначьте ответственных в карточках клиентов</div>')}${section('Приоритет клиентов',`<div class="priority-list">${Object.entries(priority).map(([name,count],i)=>`<div><span>${esc(name)}</span><div class="bar-track"><div class="bar-fill" style="width:${pct(count,o.total)}%;background:${[COLORS[5],COLORS[2],COLORS[4]][i]}"></div></div><b>${count}</b></div>`).join('')}</div>`)}</div>`+
    `<div class="grid two">${section('Клиенты по источникам',sourceDonut(o.by_source))}${section('Доход по месяцам',trend(o.revenue_months))}</div>`;
}
function render() {
  el('content').innerHTML=({dashboard:dashboard,leads:leadsPage,pipeline:pipelinePage,reports:reportsPage})[state.view]();
  const search=el('searchInput'); if(search){search.addEventListener('input',e=>{const pos=e.target.selectionStart;state.search=e.target.value;render();const input=el('searchInput');input.focus();input.setSelectionRange(pos,pos)});el('statusFilter').addEventListener('change',e=>{state.status=e.target.value;render()})}
}
async function openLead(id=null) {
  state.selectedId=id;
  const form=el('leadForm'); form.reset(); el('dialogTitle').textContent=id?'Карточка клиента':'Новый клиент';
  el('notesSection').hidden=!id; el('deleteLead').hidden=!id;
  if(id){try{const r=await api(`/api/leads/${id}`);for(const [key,value] of Object.entries(r)){const field=form.elements.namedItem(key);if(field)field.value=value??''}renderNotes(r.notes)}catch(err){toast(err.message,true);return}}
  el('leadDialog').showModal();
}
function renderNotes(notes) {
  el('notesList').innerHTML=notes.length ? notes.map(n=>`<div class="note"><div><p>${esc(n.body)}</p><small>${dateText(n.created_at)}</small></div><button type="button" data-note-delete="${n.id}" aria-label="Удалить заметку">×</button></div>`).join('') : '<p class="no-notes">Заметок пока нет</p>';
}
async function saveLead(e) {
  e.preventDefault();const form=e.target;const raw=Object.fromEntries(new FormData(form));
  raw.amount=raw.amount||0;raw.probability=raw.probability||0;raw.satisfaction=raw.satisfaction===''?null:raw.satisfaction;
  try{await api(state.selectedId?`/api/leads/${state.selectedId}`:'/api/leads',{method:state.selectedId?'PUT':'POST',body:JSON.stringify(raw)});el('leadDialog').close();toast(state.selectedId?'Карточка обновлена':'Клиент добавлен');await refresh()}catch(err){toast(err.message,true)}
}
async function addNote(){const body=el('noteInput').value.trim();if(!body)return;try{await api(`/api/leads/${state.selectedId}/notes`,{method:'POST',body:JSON.stringify({body})});el('noteInput').value='';const r=await api(`/api/leads/${state.selectedId}`);renderNotes(r.notes);toast('Заметка добавлена')}catch(err){toast(err.message,true)}}

document.addEventListener('click',async e=>{
  const nav=e.target.closest('[data-view]');if(nav){setView(nav.dataset.view);return}
  if(e.target.closest('#addLeadTop,[data-action="add"]')){openLead();return}
  const row=e.target.closest('[data-open]');if(row){openLead(Number(row.dataset.open));return}
  const note=e.target.closest('[data-note-delete]');if(note){try{await api(`/api/notes/${note.dataset.noteDelete}`,{method:'DELETE'});const r=await api(`/api/leads/${state.selectedId}`);renderNotes(r.notes)}catch(err){toast(err.message,true)}}
});
el('leadForm').addEventListener('submit',saveLead);
el('closeDialog').addEventListener('click',()=>el('leadDialog').close());
el('cancelDialog').addEventListener('click',()=>el('leadDialog').close());
el('addNote').addEventListener('click',addNote);
el('deleteLead').addEventListener('click',async()=>{if(!confirm('Удалить клиента и все его заметки?'))return;try{await api(`/api/leads/${state.selectedId}`,{method:'DELETE'});el('leadDialog').close();toast('Клиент удалён');await refresh()}catch(err){toast(err.message,true)}});
el('today').textContent=new Date().toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'});
refresh();
