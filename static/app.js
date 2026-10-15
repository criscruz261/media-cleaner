const $ = id => document.getElementById(id);
let result = null;
let polling = false;
const bytes = value => { if (!value) return '0 B'; const i = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4); return `${(value / 1024 ** i).toFixed(i ? 1 : 0)} ${['B','KB','MB','GB','TB'][i]}`; };
function status(message, error = false) { $('status').textContent = message; $('status').className = error ? 'error' : ''; }
function busy(value) { $('scan-button').disabled = value; $('scan-button').textContent = value ? 'Scanning…' : 'Scan for duplicates ↗'; }
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function renderGroups() {
  const groups = [...result.groups];
  groups.sort($('sort').value === 'name' ? (a,b) => a.files[0].name.localeCompare(b.files[0].name) : $('sort').value === 'copies' ? (a,b) => b.files.length-a.files.length : (a,b) => b.recoverable-a.recoverable);
  $('groups').replaceChildren();
  if (!groups.length) $('groups').append(element('div', 'All clear. No exact duplicate photos found in this folder.', 'no-matches'));
  groups.forEach((group, index) => {
    const card = element('article', undefined, 'group');
    const heading = element('div', undefined, 'group-top');
    heading.append(element('strong', `Group ${index+1} · ${group.files.length} identical files`), element('span', `${bytes(group.recoverable)} extra`));
    const photos = element('div', undefined, 'photos');
    group.files.forEach(file => {
      const photo = element('div', undefined, 'photo');
      const preview = element('div', undefined, 'preview');
      const img = document.createElement('img'); img.src = `/api/photo?id=${encodeURIComponent(file.id)}`; img.alt = file.name; img.loading = 'lazy';
      img.addEventListener('error', () => preview.replaceChildren(element('span', 'Preview unavailable', 'fallback')));
      preview.append(img);
      const link = element('a', 'Open original ↗'); link.href = img.src; link.target = '_blank'; link.rel = 'noopener';
      photo.append(preview, element('h4', file.name), element('p', file.path), element('p', bytes(group.size)), link); photos.append(photo);
    });
    card.append(heading, photos); $('groups').append(card);
  });
}
function render(data) {
  result = data; $('results').hidden = false; $('empty').hidden = true;
  $('folder-label').textContent = data.folder;
  $('scanned').textContent = data.scanned.toLocaleString(); $('duplicates').textContent = data.duplicates.toLocaleString(); $('space').textContent = bytes(data.recoverable); $('group-count').textContent = data.groups.length;
  $('result-title').textContent = data.errors.length ? 'Scan complete with skipped files' : 'Scan complete';
  $('warnings').hidden = !data.errors.length; $('warning-title').textContent = `${data.errors.length} files or folders could not be scanned`;
  $('warning-list').replaceChildren(...data.errors.map(message => element('li', message)));
  renderGroups();
}
async function poll() {
  if (polling) return; polling = true;
  try {
    const response = await fetch('/api/status'); if (!response.ok) throw new Error('Could not read scan progress.');
    const state = await response.json();
    if (state.status === 'scanning') {
      busy(true); status(state.phase === 'hashing' ? `Comparing file contents · ${state.hashed.toLocaleString()} of ${state.candidates.toLocaleString()} candidates checked` : `Finding photos · ${(state.scanned || 0).toLocaleString()} discovered`);
      setTimeout(poll, 500);
    } else { busy(false); if (state.status === 'done') { render(state.result); status('Finished. Your files have not been changed.'); } else if (state.status === 'error') status(state.error, true); }
  } catch (error) { busy(false); status(`${error.message} Check that the local server is running. Reload to reconnect.`, true); }
  finally { polling = false; }
}
$('scan-form').addEventListener('submit', async event => {
  event.preventDefault(); busy(true); status('Starting local scan…');
  try {
    const response = await fetch('/api/scan', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({directory: $('directory').value.trim()})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Unable to start scan.');
    $('results').hidden = true; await poll();
  } catch (error) { busy(false); status(error.message, true); }
});
$('sort').addEventListener('change', renderGroups);
$('export').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'}));
  const link = element('a'); link.href = url; link.download = 'photofold-duplicates.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
poll();
