const el = id => document.getElementById(id);
const api = async (p,o={})=>{
  const r = await fetch(p,{headers:{'Content-Type':'application/json'},...o});
  if(!r.ok) throw new Error(await r.text()); return r.json();
};
async function search(){
  const q = el('q').value.trim();
  const url = q ? `/students?search=${encodeURIComponent(q)}` : '/students';
  const rows = await api(url);
  const body = el('resultsBody');
  body.innerHTML = rows.length ? rows.map(s=>`
    <tr>
      <td>${s.id}</td><td>${s.index_no}</td><td>${s.full_name}</td>
      <td><button class="btn-ghost" onclick="alert('Open student ${s.id}')">View</button></td>
    </tr>`).join('')
    : `<tr><td colspan="4" class="py-6 text-center text-slate-500">No matches.</td></tr>`;
}
el('searchBtn').onclick = search;
el('q').addEventListener('keydown', e => { if(e.key==='Enter') search(); });

el('addBtn').onclick = async ()=>{
  const index_no = el('idx').value.trim();
  const full_name = el('name').value.trim();
  if(!index_no || !full_name) return alert('Provide both fields');
  await api('/students',{method:'POST',body:JSON.stringify({index_no, full_name})});
  el('idx').value = ""; el('name').value = "";
  search();

};
