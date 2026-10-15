const $ = id => document.getElementById(id);
let result = null;
let polling = false;
let keep = new Set();
let deleting = false;
let groupDeleteButtons = [];
const bytes = value => { if (!value) return '0 B'; const i = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4); return `${(value / 1024 ** i).toFixed(i ? 1 : 0)} ${['B','KB','MB','GB','TB'][i]}`; };
function status(message, error = false) { $('status').textContent = message; $('status').className = error ? 'error' : ''; }
function busy(value) { $('scan-button').disabled = value; $('scan-button').textContent = value ? 'Scanning…' : 'Scan media ↗'; }
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function renderGroups() {
  const groups = [...result.groups];
  groups.sort($('sort').value === 'name' ? (a,b) => a.files[0].name.localeCompare(b.files[0].name) : $('sort').value === 'copies' ? (a,b) => b.files.length-a.files.length : (a,b) => b.recoverable-a.recoverable);
  $('groups').replaceChildren();
  groupDeleteButtons = [];
  if (!groups.length) $('groups').append(element('div', 'All clear. No matching photos or videos found in this folder.', 'no-matches'));
  groups.forEach((group, index) => {
    const card = element('article', undefined, 'group');
    const heading = element('div', undefined, 'group-top');
    heading.append(element('strong', `Group ${index+1} · ${group.files.length} ${group.kind === 'exact' ? 'identical' : 'similar'} files`), element('span', `${bytes(group.recoverable)} extra`));
    const deleteGroup = element('button', 'Delete unchecked in this group', 'danger');
    deleteGroup.type = 'button';
    deleteGroup.addEventListener('click', () => deleteFiles(group.files, `Group ${index + 1}`));
    groupDeleteButtons.push({button: deleteGroup, group});
    heading.append(deleteGroup);
    const photos = element('div', undefined, 'photos');
    group.files.forEach(file => {
      const photo = element('div', undefined, 'photo');
      const choice = element('label', undefined, 'keep-choice');
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = keep.has(file.id);
      checkbox.addEventListener('change', () => {
        if (!checkbox.checked && group.files.filter(item => keep.has(item.id)).length === 1) { checkbox.checked = true; return; }
        if (checkbox.checked) keep.add(file.id); else keep.delete(file.id);
        updateSelection();
      });
      choice.append(checkbox, document.createTextNode('Keep this file'));
      const preview = element('div', undefined, 'preview');
      const img = document.createElement('img'); if (file.media_type !== 'video') img.src = `/api/photo?id=${encodeURIComponent(file.id)}`; img.alt = file.name; img.loading = 'lazy';
      img.addEventListener('error', () => preview.replaceChildren(element('span', 'Preview unavailable', 'fallback')));
      if (file.media_type === 'video') {
        const video = document.createElement('video');
        video.controls = true; video.preload = 'metadata'; video.playsInline = true;
        video.setAttribute('aria-label', file.name);
        video.src = `/api/photo?id=${encodeURIComponent(file.id)}`;
        video.addEventListener('error', () => preview.replaceChildren(element('span', 'This video format cannot play in your browser. Open or download the original to review it.', 'fallback')));
        preview.append(video);
      } else { preview.append(img); }
      const link = element('a', 'Open original ↗'); link.href = `/api/photo?id=${encodeURIComponent(file.id)}`; link.target = '_blank'; link.rel = 'noopener';
      photo.append(preview, element('h4', file.name), element('p', file.path), element('p', bytes(file.size)), choice, link); photos.append(photo);
    });
    card.append(heading, photos); $('groups').append(card);
  });
}
function updateSelection() {
  const photos = result.groups.flatMap(group => group.files);
  const unselected = photos.filter(file => !keep.has(file.id));
  $('delete').disabled = deleting || unselected.length === 0;
  groupDeleteButtons.forEach(({button, group}) => { button.disabled = deleting || group.files.every(file => keep.has(file.id)); });
  $('duplicates').textContent = unselected.length.toLocaleString();
  $('space').textContent = bytes(unselected.reduce((sum, file) => sum + file.size, 0));
}
function render(data) {
  result = data;
  keep = new Set(data.groups.map(group => group.preferred_keeper)); $('results').hidden = false; $('empty').hidden = true;
  $('folder-label').textContent = data.folder;
  $('scanned').textContent = data.scanned.toLocaleString(); $('duplicates').textContent = data.duplicates.toLocaleString(); $('space').textContent = bytes(data.recoverable); $('group-count').textContent = data.groups.length;
  $('result-title').textContent = data.errors.length ? 'Scan complete with skipped files' : 'Scan complete';
  $('warnings').hidden = !data.errors.length; $('warning-title').textContent = `${data.errors.length} files or folders could not be scanned`;
  $('warning-list').replaceChildren(...data.errors.map(message => element('li', message)));
  renderGroups(); updateSelection();
}
async function poll() {
  if (polling) return; polling = true;
  try {
    const response = await fetch('/api/status'); if (!response.ok) throw new Error('Could not read scan progress.');
    const state = await response.json();
    if (state.status === 'scanning') {
      busy(true); status(state.phase === 'similarity' ? `Comparing appearance · ${state.compared} of ${state.candidates} photos` : state.phase === 'hashing' ? `Comparing file contents · ${state.hashed.toLocaleString()} of ${state.candidates.toLocaleString()} candidates checked` : `Finding photos · ${(state.scanned || 0).toLocaleString()} media files discovered`);
      setTimeout(poll, 500);
    } else { busy(false); if (state.status === 'done') { render(state.result); status('Finished. Your files have not been changed.'); } else if (state.status === 'error') status(state.error, true); }
  } catch (error) { busy(false); status(`${error.message} Check that the local server is running. Reload to reconnect.`, true); }
  finally { polling = false; }
}
$('scan-form').addEventListener('submit', async event => {
  event.preventDefault(); busy(true); status('Starting local scan…');
  try {
    const response = await fetch('/api/scan', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({directory: $('directory').value.trim(), mode: $('mode').value})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Unable to start scan.');
    $('results').hidden = true; await poll();
  } catch (error) { busy(false); status(error.message, true); }
});
async function deleteFiles(files, scope) {
  if (!result || deleting) return;
  const unchecked = files.filter(file => !keep.has(file.id));
  if (!unchecked.length) return;
  const total = unchecked.reduce((sum, file) => sum + file.size, 0);
  if (!window.confirm(`Permanently delete ${unchecked.length} unchecked files (${bytes(total)}) from ${scope}?\n\nChecked files will be kept. This cannot be undone and does not move files to Trash. Review similar-photo matches carefully.\n\n${unchecked.slice(0, 8).map(file => file.path).join('\n')}${unchecked.length > 8 ? '\n…see the unchecked cards for the remaining files.' : ''}`)) return;
  deleting = true; updateSelection(); busy(true);
  $('groups').querySelectorAll('input').forEach(input => { input.disabled = true; });
  try {
    const response = await fetch('/api/delete', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: unchecked.map(file => file.id), confirmed: true, delete_token: result.delete_token})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Deletion failed.');
    result = data.result;
    const remaining = new Set(result.groups.flatMap(group => group.files).map(file => file.id));
    keep = new Set([...keep].filter(id => remaining.has(id)));
    $('group-count').textContent = result.groups.length;
    renderGroups();
    status(`Deleted ${data.deleted.length} files from ${scope}. ${data.errors.join(' · ')}`, data.errors.length > 0);
  } catch (error) { status(error.message, true); updateSelection(); }
  finally { deleting = false; busy(false); updateSelection(); $('groups').querySelectorAll('input').forEach(input => { input.disabled = false; }); }
}
$('delete').addEventListener('click', () => { if (result) deleteFiles(result.groups.flatMap(group => group.files), 'all groups'); });
$('sort').addEventListener('change', renderGroups);
$('export').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify({...result, groups: result.groups.map(group => ({...group, files: group.files.map(file => ({...file, decision: keep.has(file.id) ? 'keep' : 'review-for-removal'}))}))}, null, 2)], {type: 'application/json'}));
  const link = element('a'); link.href = url; link.download = 'photofold-duplicates.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
poll();
