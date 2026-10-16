document.querySelectorAll('[data-select-all]').forEach(control => {
  const form = control.closest('form');
  const choices = Array.from(form.querySelectorAll('input[name="payment_ids"]:not(:disabled)'));
  const counter = form.querySelector('[data-selected-count]');
  function update() {
    const count = choices.filter(input => input.checked).length;
    if (counter) counter.textContent = `${count} seleccionados`;
    control.checked = count > 0 && count === choices.length;
    control.indeterminate = count > 0 && count < choices.length;
  }
  control.addEventListener('change', () => {
    choices.forEach(input => { input.checked = control.checked; });
    update();
  });
  choices.forEach(input => input.addEventListener('change', update));
  update();
});

document.querySelectorAll('form[data-busy-label]').forEach(form => {
  form.addEventListener('submit', event => {
    form.setAttribute('aria-busy', 'true');
    const button = event.submitter;
    if (button) {
      button.textContent = form.dataset.busyLabel;
      setTimeout(() => { button.disabled = true; }, 0);
    }
  });
});

const helpDialog = document.querySelector('#help-dialog');
document.querySelectorAll('[data-help], [data-help-next], [data-help-target]').forEach(button => {
  button.addEventListener('click', () => {
    const content = helpDialog.querySelector('[data-help-content]');
    content.replaceChildren();
    const template = button.nextElementSibling?.tagName === 'TEMPLATE' ? button.nextElementSibling
      : document.getElementById(button.dataset.helpTarget);
    if (template) content.append(template.content.cloneNode(true));
    else content.textContent = button.dataset.help;
    helpDialog.showModal();
  });
});
document.querySelector('[data-close-help]')?.addEventListener('click', () => helpDialog.close());

const confirmDialog = document.querySelector('#confirm-dialog');
let pendingDelete;
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.confirmed === 'yes') return;
    event.preventDefault();
    pendingDelete = form;
    confirmDialog.querySelector('[data-confirm-content]').textContent = form.dataset.confirm;
    confirmDialog.showModal();
  });
});
document.querySelector('[data-confirm-cancel]')?.addEventListener('click', () => confirmDialog.close());
document.querySelector('[data-confirm-accept]')?.addEventListener('click', () => {
  const form = pendingDelete;
  confirmDialog.close();
  form.dataset.confirmed = 'yes';
  form.requestSubmit();
});

document.querySelectorAll('[data-supplier-picker]').forEach(picker => {
  const input = picker.querySelector('[role=combobox]');
  const id = picker.querySelector('[name=supplier_id]');
  const options = picker.querySelector('[role=listbox]');
  const status = picker.querySelector('[data-supplier-status]');
  let timer, controller, active = -1, version = 0;
  function close() {
    ++version; clearTimeout(timer); controller?.abort();
    options.hidden = true; input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant'); active = -1;
  }
  function choose(item) { input.value = item.name; id.value = item.id; input.setCustomValidity(''); close(); input.focus(); }
  function highlight(index) {
    const items = [...options.children].filter(item => item.getAttribute('role') === 'option');
    active = Math.max(0, Math.min(index, items.length - 1));
    items.forEach((item, n) => item.setAttribute('aria-selected', String(n === active)));
    if (items[active]) { input.setAttribute('aria-activedescendant', items[active].id); items[active].scrollIntoView({block: 'nearest'}); }
  }
  async function search() {
    const current = ++version;
    controller?.abort(); controller = new AbortController();
    try {
      const response = await fetch('/business/suppliers/search?q=' + encodeURIComponent(input.value), {signal: controller.signal});
      if (!response.ok) throw new Error('search');
      const rows = await response.json();
      if (current !== version) return;
      options.replaceChildren(); active = -1;
      const empty = document.createElement('li'); empty.textContent = 'Sin proveedor'; empty.role = 'option'; empty.id = 'supplier-empty';
      empty.addEventListener('mousedown', event => event.preventDefault());
      empty.addEventListener('click', () => choose({id: '', name: ''})); options.append(empty);
      rows.forEach(row => {
        const item = document.createElement('li'); item.textContent = row.name; item.role = 'option'; item.id = 'supplier-' + row.id;
        item.addEventListener('mousedown', event => event.preventDefault()); item.addEventListener('click', () => choose(row)); options.append(item);
      });
      status.textContent = rows.length === 1 ? '1 proveedor encontrado' : rows.length ? `${rows.length} proveedores encontrados` : 'No se encontraron proveedores';
      options.hidden = false; input.setAttribute('aria-expanded', 'true');
    } catch (error) { if (error.name !== 'AbortError') { status.textContent = 'No se pudo buscar. Intentá otra vez.'; close(); } }
  }
  input.addEventListener('input', () => { close(); id.value = ''; input.setCustomValidity(input.value.trim() ? 'Elegí un proveedor de la lista o dejá el campo vacío.' : ''); timer = setTimeout(search, 180); });
  input.addEventListener('focus', search);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (options.hidden) search(); else highlight(active + (event.key === 'ArrowDown' ? 1 : -1)); }
    if (event.key === 'Enter' && !options.hidden) { event.preventDefault(); if (active >= 0) options.children[active]?.click(); }
  });
  input.addEventListener('blur', close);
});
