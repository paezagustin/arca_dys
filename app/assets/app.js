document.querySelectorAll('.site-menu').forEach(menu => {
  const current = menu.querySelector('[aria-current="page"]');
  if (current) menu.querySelector('[data-menu-label]').textContent = current.textContent.trim();
  const mobile = window.matchMedia('(max-width: 900px)');
  function adapt() { menu.open = !mobile.matches; }
  mobile.addEventListener('change', adapt);
  adapt();
});

document.querySelectorAll('form[method="get"][data-auto-filter]').forEach(form => {
  const dates = [...form.querySelectorAll('input[type="date"]')];
  const [from, to] = dates;
  const calendar = [...form.querySelectorAll('[data-calendar-period]')];
  const feedback = document.createElement('span');
  feedback.className = 'muted sr-only';
  feedback.setAttribute('role', 'status');
  form.querySelector('.actions').append(feedback);
  let timer, typingDate = false;

  function showRangeError(error) {
    feedback.classList.toggle('sr-only', !error);
    feedback.textContent = error;
  }

  function rangeError(requirePair) {
    if (!from || !to) return '';
    if (dates.some(field => field.validity.badInput || (field.value && field.value.length !== 10))) {
      return 'Revisá las fechas ingresadas.';
    }
    if (requirePair && Boolean(from.value) !== Boolean(to.value)) {
      return calendar.length ? 'Completá las dos fechas para aplicar el rango.'
        : 'Completá las dos fechas o pulsá Buscar para filtrar con una sola.';
    }
    return from.value && to.value && from.valueAsNumber > to.valueAsNumber
      ? 'La fecha desde no puede ser posterior a la fecha hasta.' : '';
  }

  function datesChanged() {
    return dates.some(field => field.value !== field.defaultValue);
  }

  function schedule(control) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (calendar.includes(control) && calendar.every(field => field.validity.valid)) {
        dates.forEach(field => { field.value = ''; });
      }
      const error = rangeError(calendar.length > 0 || datesChanged());
      showRangeError(error);
      if (!error && form.checkValidity()) form.requestSubmit();
    }, dates.includes(control) ? 300 : 0);
  }

  // Al escribir una fecha, esperar hasta que termine de editar el rango.
  form.addEventListener('input', event => {
    if (dates.includes(event.target)) clearTimeout(timer);
  });
  form.addEventListener('keydown', event => {
    if (dates.includes(event.target) && !event.altKey &&
        (event.key.length === 1 || ['Backspace', 'Delete', 'ArrowUp', 'ArrowDown'].includes(event.key))) {
      clearTimeout(timer);
      typingDate = true;
    }
  });
  form.addEventListener('focusout', event => {
    if (typingDate && dates.includes(event.target) && !dates.includes(event.relatedTarget)) {
      typingDate = false;
      if (datesChanged()) schedule(event.target);
    }
  });
  form.addEventListener('change', event => {
    const control = event.target;
    if (dates.includes(control) ? !typingDate : control.matches('select, [data-calendar-period]')) {
      schedule(control);
    }
  });
  form.addEventListener('submit', event => {
    clearTimeout(timer);
    const error = rangeError(calendar.length > 0);
    if (error) {
      event.preventDefault();
      showRangeError(error);
    }
  });
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
  const format = new Intl.NumberFormat('es-AR', {
    style: 'currency', currency: 'ARS', minimumFractionDigits: 0, maximumFractionDigits: 0
  });
  function pesos(input) {
    if (!input.value) return 0n;
    if (!/^\d+$/.test(input.value)) return null;
    return BigInt(input.value);
  }
  function update() {
    if (!cash.value && !mp.value) { total.value = ''; return; }
    const a = pesos(cash), b = pesos(mp);
    total.value = a === null || b === null ? '' : format.format(a + b);
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
      mp.value = data.total;
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
