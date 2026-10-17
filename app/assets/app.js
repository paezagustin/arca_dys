document.querySelectorAll('.site-menu').forEach(menu => {
  const current = menu.querySelector('[aria-current="page"]');
  if (current) menu.querySelector('summary').textContent = current.textContent.trim();
  const mobile = window.matchMedia('(max-width: 900px)');
  function adapt() { menu.open = !mobile.matches; }
  mobile.addEventListener('change', adapt);
  adapt();
});

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

document.querySelectorAll('[data-daily-sale]').forEach(form => {
  const cash = form.querySelector('[name=cash_amount]');
  const mp = form.querySelector('[name=mp_amount]');
  const date = form.querySelector('[name=entry_date]');
  const total = form.querySelector('[data-sale-total]');
  const status = form.querySelector('[data-mp-status]');
  let version = 0, controller;
  const format = new Intl.NumberFormat('es-AR', {style: 'currency', currency: 'ARS'});
  function cents(input) {
    if (!input.value) return 0n;
    if (!/^\d+(\.\d{1,2})?$/.test(input.value)) return null;
    const [whole, fraction = ''] = input.value.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  }
  function update() {
    if (!cash.value && !mp.value) { total.value = ''; return; }
    const a = cents(cash), b = cents(mp);
    if (a !== null && b !== null) {
      const sum = a + b;
      total.value = format.formatToParts(sum / 100n).map(part => part.type === 'fraction' ? String(sum % 100n).padStart(2, '0') : part.value).join('');
    }
    else total.value = '';
  }
  cash.addEventListener('input', update);
  mp.addEventListener('input', () => { ++version; controller?.abort(); status.textContent = ''; update(); });
  date.addEventListener('change', async () => {
    const current = ++version;
    controller?.abort(); controller = new AbortController();
    if (!date.value || !date.validity.valid) return;
    status.textContent = ''; status.classList.add('sr-only'); status.setAttribute('role', 'status');
    try {
      const response = await fetch('/business/sales/mp-total?date=' + encodeURIComponent(date.value), {signal: controller.signal});
      if (!response.ok) throw new Error('total');
      const data = await response.json();
      if (current !== version) return;
      mp.value = /^0+(\.0+)?$/.test(data.total) ? '' : data.total;
      status.textContent = 'Monto de Mercado Pago actualizado para la fecha elegida.'; update();
    } catch (error) {
      if (current === version && error.name !== 'AbortError') {
        status.classList.remove('sr-only'); status.setAttribute('role', 'alert');
        status.textContent = 'No se pudo consultar Mercado Pago. Ingresá el monto manualmente.';
      }
    }
  });
  const savedTotal = total.value;
  update();
  if (!cash.value && !mp.value && savedTotal) total.value = savedTotal;
});
