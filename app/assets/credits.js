/* Mejora progresiva de los formularios Jinja. W3C APG: selección manual de combobox. */
(() => {
  'use strict';
  const dialog = document.querySelector('#credit-form-dialog');
  if (!dialog) return;
  const body = dialog.querySelector('[data-credit-dialog-body]');
  let busy = false, opener;
  function close() {
    if (busy) return;
    dialog.close();
    body.replaceChildren();
    opener?.focus();
  }
  dialog.querySelector('[data-credit-close]').addEventListener('click', close);
  dialog.addEventListener('cancel', event => {
    if (event.defaultPrevented) return;
    event.preventDefault(); close();
  });

  function picker(root) {
    const form = root.closest('form'), input = root.querySelector('[role=combobox]');
    const id = root.querySelector('[name=customer_id]'), version = form.querySelector('[name=version]');
    const status = root.querySelector('[data-suggestions-status]');
    const summary = root.querySelector('[data-person-summary]'), existing = root.querySelector('[data-person-existing]');
    const creating = root.querySelector('[data-person-new-fields]'), flag = root.querySelector('[name=new_customer]');
    const money = digits => '$\u00a0' + CreditMoney.format(String(digits));
    const lifecycle = new AbortController();
    const suggestions = AppSuggestions.attach(root, {
      signal: lifecycle.signal,
      async load(value, signal) {
        const response = await fetch('/fiados/personas/buscar?q=' + encodeURIComponent(value), { signal, headers: { Accept: 'application/json' } });
        if (!response.ok) throw Error('search');
        return response.json();
      },
      render(option, row) {
        const text = document.createElement('span'), name = document.createElement('strong'), alias = document.createElement('small'), amount = document.createElement('span');
        name.textContent = row.name; alias.textContent = row.alias; amount.textContent = money(row.balance); amount.className = 'money';
        text.append(name); if (row.alias) text.append(alias); option.append(text, amount);
      },
      choose(row) {
        input.value = row.name; id.value = row.id; version.value = row.version;
        input.setCustomValidity(''); summary.textContent = 'Saldo actual: ' + money(row.balance);
        const distinct = form.querySelector('[name=distinct_person]');
        if (distinct) distinct.disabled = true;
        status.textContent = row.name + ' seleccionada.';
      },
      edit() {
        id.value = ''; version.value = ''; summary.textContent = '';
        input.setCustomValidity('Seleccioná una persona de la lista o creá una nueva.');
      },
      emptyMessage() { return 'No hay coincidencias. Podés crear una persona nueva.'; },
    });
    if (dialog.contains(root)) {
      dialog.addEventListener('close', () => lifecycle.abort(), { once: true });
      // Una validación del servidor puede sustituir el formulario sin cerrar el diálogo.
      root.addEventListener('credit:replace', () => lifecycle.abort(), { once: true });
    }
    function switchMode(newPerson) {
      suggestions.close(); flag.value = newPerson ? '1' : '0'; existing.hidden = newPerson;
      input.disabled = newPerson; creating.hidden = !newPerson; creating.disabled = !newPerson;
      id.value = ''; version.value = ''; summary.textContent = ''; status.textContent = '';
      const distinct = form.querySelector('[name=distinct_person]');
      if (distinct) distinct.disabled = !newPerson;
      if (newPerson) {
        const name = creating.querySelector('[name=name]'); if (!name.value) name.value = input.value;
        name.focus();
      } else {
        input.setCustomValidity('Seleccioná una persona de la lista.'); input.focus();
      }
    }
    root.querySelector('[data-person-new]').addEventListener('click', event => { event.preventDefault(); switchMode(true); });
    root.querySelector('[data-person-existing-link]').addEventListener('click', event => { event.preventDefault(); switchMode(false); });
    if (!id.value && !input.disabled) input.setCustomValidity('Seleccioná una persona de la lista o creá una nueva.');
  }

  function phoneInput(input) {
    let previous = input.value;
    const invalid = () => window.AppNotifications?.show('El celular admite solo números, sin espacios ni signos.', {error:true});
    input.addEventListener('beforeinput', event => {
      if (event.data && /[^0-9]/.test(event.data)) {event.preventDefault(); invalid();}
    });
    input.addEventListener('paste', event => {
      const text = event.clipboardData?.getData('text');
      if (text !== undefined && (!/^[0-9]*$/.test(text) || input.value.length - (input.selectionEnd-input.selectionStart) + text.length > 10)) {
        event.preventDefault(); invalid();
      }
    });
    input.addEventListener('input', () => {
      if (/^[0-9]{0,10}$/.test(input.value)) previous = input.value;
      else {input.value = previous; invalid();}
    });
  }

  function initialize(root) {
    root.querySelectorAll('[data-credit-phone]').forEach(phoneInput);
    root.querySelectorAll('[data-credit-money]').forEach(CreditMoney.attach);
    root.querySelectorAll('[data-credit-person]').forEach(picker);
    root.querySelectorAll('[data-credit-cancel]').forEach(link => link.addEventListener('click',event => {
      if (dialog.open) { event.preventDefault(); close(); }
    }));
    root.querySelectorAll('form[data-credit-form]').forEach(form => form.addEventListener('submit',async event => {
      if (!dialog.open || !dialog.contains(form)) return;
      event.preventDefault();
      if (busy || !form.reportValidity()) return;
      busy = true; form.setAttribute('aria-busy','true');
      const button = form.querySelector('button[type=submit]'); button.disabled = true;
      const error = form.querySelector('[data-credit-submit-error]'); error.hidden = true;
      try {
        const response = await fetch(form.action,{method:'POST',body:new URLSearchParams(new FormData(form)),headers:{Accept:'text/html'}});
        if (response.redirected) { window.location.assign(response.url); return; }
        const document = new DOMParser().parseFromString(await response.text(),'text/html');
        const content = document.querySelector('[data-credit-form-content]');
        if (!content) throw Error('response');
        form.querySelector('[data-credit-person]')?.dispatchEvent(new Event('credit:replace'));
        body.replaceChildren(content); dialog.querySelector('#credit-dialog-title').textContent = content.dataset.title;
        initialize(body); (body.querySelector('input:not([type=hidden]):not([readonly]):not(:disabled)') || body.querySelector('button[type=submit]')).focus();
      } catch {
        error.textContent = 'No pudimos confirmar el resultado. Consultá el historial antes de repetir; conservá este formulario.';
        error.hidden = false;
      } finally { busy = false; form.removeAttribute('aria-busy'); button.disabled = false; }
    }));
  }
  initialize(document.querySelector('.credit-workspace'));
  const scopeForm = document.querySelector('[data-whatsapp-scope]');
  if (scopeForm) {
    const select = scopeForm.querySelector('select'), target = document.querySelector('[data-whatsapp-content]');
    let current = select.value, controller, request = 0;
    select.addEventListener('change', async () => {
      const value = select.value;
      const seq = ++request; controller?.abort();
      if (value === current) {
        target.removeAttribute('aria-busy');
        target.querySelectorAll('a[target=_blank]').forEach(link => {link.removeAttribute('aria-disabled'); link.removeAttribute('tabindex');});
        return;
      }
      controller = new AbortController();
      const url = new URL(scopeForm.action); url.search = new URLSearchParams(new FormData(scopeForm));
      target.setAttribute('aria-busy','true');
      // Evitar enviar un detalle viejo mientras se prepara la selección nueva.
      target.querySelectorAll('a[target=_blank]').forEach(link => {link.setAttribute('aria-disabled','true'); link.tabIndex=-1;});
      try {
        const response = await fetch(url,{signal:controller.signal,redirect:'error',headers:{Accept:'text/html'}});
        if (!response.ok) throw Error('response');
        const page = new DOMParser().parseFromString(await response.text(),'text/html');
        const updated = page.querySelector('[data-whatsapp-content]');
        if (!updated) throw Error('content');
        if (seq !== request) return;
        target.replaceChildren(...updated.childNodes); current = value;
        history.replaceState(null,'',url);
      } catch (error) {
        if (seq === request && error.name !== 'AbortError') {
          select.value = current;
          window.AppNotifications?.show('No se pudo actualizar el detalle. Se conserva el mensaje anterior.',{error:true});
        }
      } finally {
        if (seq === request) {
          target.removeAttribute('aria-busy');
          target.querySelectorAll('a[target=_blank]').forEach(link => {link.removeAttribute('aria-disabled'); link.removeAttribute('tabindex');});
        }
      }
    });
    scopeForm.addEventListener('submit',event => event.preventDefault());
    target.addEventListener('click',event => {if (event.target.closest('a[aria-disabled=true]')) event.preventDefault();});
  }
  document.addEventListener('click',async event => {
    const link = event.target.closest('a[data-credit-dialog]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || busy) return;
    event.preventDefault(); opener = link;
    try {
      const response = await fetch(link.href,{headers:{Accept:'text/html'}});
      if (!response.ok) throw Error('form');
      const document = new DOMParser().parseFromString(await response.text(),'text/html');
      const content = document.querySelector('[data-credit-form-content]');
      if (!content) throw Error('form');
      body.replaceChildren(content); dialog.querySelector('#credit-dialog-title').textContent = content.dataset.title;
      initialize(body); if (!dialog.open) dialog.showModal();
      const selected = body.querySelector('[name=customer_id]')?.value;
      ((content.dataset.title === 'Eliminar movimiento' ? body.querySelector('[data-credit-cancel]') : null)
        || (selected ? body.querySelector('[data-credit-money]:not([readonly])') : null)
        || body.querySelector('[role=combobox]:not(:disabled)')
        || body.querySelector('input:not([type=hidden]):not([readonly]):not(:disabled)')
        || body.querySelector('button[type=submit]')).focus();
    } catch { window.location.assign(link.href); }
  });
})();
