(() => {
  const page = document.querySelector('[data-restock]');
  if (!page) return;
  page.dataset.restockReady = '';
  const main = page.closest('main');
  const search = page.querySelector('[data-restock-search]');
  const choice = page.querySelector('[data-register-choice]');
  const choiceStatus = page.querySelector('[data-register-status]');
  const quickCreate = page.querySelector('[data-restock-new]');
  const feedback = page.querySelector('[data-restock-feedback]');
  let outstandingWrites = 0;

  function announce(message, error = false) {
    if (window.AppNotifications) {
      window.AppNotifications.show(message, { error });
      return;
    }
    feedback.hidden = false;
    feedback.classList.toggle('success', !error);
    feedback.classList.toggle('error', error);
    feedback.textContent = message;
  }

  function refreshReport() {
    main.dispatchEvent(new Event('report:refresh'));
  }

  function resetRegistration() {
    if (!choice) return;
    choice.hidden = true;
    choiceStatus.hidden = true;
    quickCreate.hidden = true;
    quickCreate.open = false;
    const approval = quickCreate.querySelector('[name=allow_duplicate]');
    approval.checked = false;
    approval.required = false;
    approval.closest('fieldset').hidden = true;
  }

  function initializePicker(root) {
    const mode = root.dataset.restockPicker;
    const input = root.querySelector('[role=combobox]');
    const key = root.querySelector('[data-picker-key]');
    const form = input.form;
    const isProduct = mode === 'register' || mode === 'product';
    const suppliers = mode === 'preferred' ? [...form.querySelectorAll('[name=supplier_id]')] : [];
    const allowed = new Set(suppliers.map(control => control.value));

    AppSuggestions.attach(root, {
      async load(value, signal) {
        if (isProduct && !value.trim()) return [];
        const url = new URL(root.dataset.endpoint, location.origin);
        url.searchParams.set('q', value);
        const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
        if (!response.ok) throw Error('search');
        const rows = await response.json();
        return mode === 'preferred' ? rows.filter(row => allowed.has(String(row.id))) : rows;
      },
      render(option, row) {
        const label = document.createElement('strong');
        label.textContent = row.name;
        option.append(label);
        if (row.status === 'ordered') {
          const badge = document.createElement('span');
          badge.className = 'restock-state restock-state-ordered';
          badge.textContent = 'Ya pedido';
          option.append(badge);
        }
      },
      choose(row) {
        input.value = row.name;
        if (mode === 'register') {
          resetRegistration();
          choice.hidden = Boolean(row.status);
          choice.action = `/faltantes/registrar/${row.id}`;
          choice.elements.request_key.value = row.key || '';
          if (row.status) {
            choiceStatus.textContent = row.status === 'ordered' ? 'Ya pedido' : 'Ya agregado a Faltantes';
            choiceStatus.hidden = false;
          }
          return;
        }
        key.value = row.id;
        if (mode === 'preferred') {
          const supplier = suppliers.find(control => control.value === key.value);
          if (supplier) supplier.checked = true;
        } else {
          form.requestSubmit();
        }
      },
      edit() {
        if (mode === 'register') resetRegistration();
        else if (mode === 'supplier' && !input.value.trim() && key.value) {
          key.value = '';
          form.requestSubmit();
        } else if (mode !== 'supplier') {
          key.value = '';
        }
      },
      results(rows) {
        if (mode === 'register' && input.value.trim() && !rows.length) {
          quickCreate.hidden = false;
          quickCreate.querySelector('[name=name]').value = input.value.trim();
        }
      },
      emptyMessage(value) { return mode !== 'register' && (value.trim() || !isProduct) ? 'No hay coincidencias.' : ''; },
    });
  }

  page.querySelectorAll('[data-restock-picker]').forEach(initializePicker);
  search?.addEventListener('submit', event => event.preventDefault());

  function warnDuplicates(form, products) {
    const box = form.querySelector('[data-restock-duplicates]');
    if (!box) return;
    const entries = products.map(name => {
      const li = document.createElement('li');
      li.textContent = name;
      return li;
    });
    box.querySelector('ul').replaceChildren(...entries);
    const approval = box.querySelector('input');
    approval.checked = false;
    approval.required = true;
    box.hidden = false;
    approval.focus();
  }

  page.addEventListener('submit', async event => {
    const form = event.target.closest('form[data-restock-write]');
    if (!form || event.defaultPrevented || (form.hasAttribute('data-confirm') && form.dataset.confirmed !== 'yes')) return;
    event.preventDefault();
    if (form.dataset.saving) return;
    const data = new URLSearchParams(new FormData(form));
    if (event.submitter?.name) data.append(event.submitter.name, event.submitter.value);
    const submit = event.submitter || form.querySelector('button[type=submit], [data-confirm-trigger]');
    const details = form.closest('dialog[data-restock-details]');
    const detailsError = details?.querySelector('[data-restock-details-error]');
    const cancel = details?.querySelector('[data-restock-details-close]');
    function showError(message) {
      if (detailsError) {
        detailsError.textContent = message;
        detailsError.hidden = false;
      } else {
        announce(message, true);
      }
    }
    form.dataset.saving = 'true';
    form.setAttribute('aria-busy', 'true');
    if (submit) submit.disabled = true;
    if (cancel) cancel.disabled = true;
    if (detailsError) detailsError.hidden = true;
    outstandingWrites += 1;
    try {
      const response = await fetch(form.action, { method: 'POST', headers: { Accept: 'application/json' }, body: data });
      const result = await response.json();
      if (!response.ok) {
        showError(result.detail || 'No se pudo guardar. Volvé a intentar.');
        if (details && (response.status === 409 || response.status === 404)) details.dataset.refreshOnClose = '';
        else if (result.duplicates) warnDuplicates(form, result.duplicates);
        else if (response.status === 409) {
          if (form === choice) resetRegistration();
          refreshReport();
        }
        return;
      }
      if (result.url) {
        location.assign(result.url);
        return;
      }
      details?.close();
      announce(result.message);
      if (form === choice || quickCreate?.contains(form)) {
        search.elements.buscar.value = '';
        quickCreate.querySelector('[name=request_key]').value = result.request_key;
        resetRegistration();
        search.elements.buscar.focus({ preventScroll: true });
      }
      refreshReport();
    } catch {
      showError('No se pudo confirmar el guardado. Volvé a intentar.');
    } finally {
      outstandingWrites -= 1;
      delete form.dataset.saving;
      form.removeAttribute('aria-busy');
      if (cancel) cancel.disabled = false;
      if (submit) submit.disabled = details?.hasAttribute('data-refresh-on-close')
        || (form.matches('[data-restock-draft]') && !form.querySelector('[name=need_id]:checked'));
    }
  });

  function updateDraft(form) {
    const lines = [...form.querySelectorAll('[data-draft-line]')];
    const selected = lines.filter(row => row.querySelector('[name=need_id]').checked);
    const all = form.querySelector('[data-restock-select-all]');
    all.checked = selected.length === lines.length;
    all.indeterminate = selected.length > 0 && selected.length < lines.length;
    form.querySelector('[data-restock-selection]').textContent = `${selected.length} de ${lines.length} seleccionados`;
    const products = selected.map(row => {
      const id = row.querySelector('[name=need_id]').value;
      const quantity = form.elements[`quantity_${id}`].value.trim();
      const notes = form.elements[`notes_${id}`].value.trim();
      return '- ' + [row.dataset.name, quantity, notes].filter(Boolean).join(' — ');
    });
    const note = form.elements.order_notes.value.trim();
    const message = selected.length ? [
      'Hola, buen día. Te paso el pedido:', products.join('\n'), note, 'Gracias.'
    ].filter(Boolean).join('\n\n') : '';
    form.querySelector('[data-restock-message]').value = message;
    form.querySelector('[data-restock-copy]').disabled = !message;
    form.querySelector('button[type=submit]').disabled = !message || Boolean(form.dataset.saving);
    const whatsapp = form.querySelector('[data-restock-whatsapp]');
    if (whatsapp) {
      whatsapp.hidden = !message;
      whatsapp.href = `https://wa.me/${whatsapp.dataset.restockWhatsapp}?text=${encodeURIComponent(message)}`;
    }
  }

  async function copyOrder(form) {
    const message = form.querySelector('[data-restock-message]');
    if (!message.value) return;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(message.value);
        announce('Pedido copiado.');
        return;
      } catch (error) {
        // HTTP local y algunos navegadores requieren copiar desde el campo visible.
      }
    }
    message.focus({ preventScroll: true });
    message.select();
    message.setSelectionRange(0, message.value.length);
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (error) { /* Selección manual disponible. */ }
    announce(copied ? 'Pedido copiado.' : 'El mensaje está seleccionado para que puedas copiarlo.');
  }

  page.addEventListener('click', event => {
    const details = event.target.closest('[data-restock-details-open]');
    if (details) {
      document.getElementById(details.getAttribute('aria-controls')).showModal();
      return;
    }
    const close = event.target.closest('[data-restock-details-close]');
    if (close) {
      close.closest('dialog').close();
      return;
    }
    const copy = event.target.closest('[data-restock-copy]');
    if (copy) copyOrder(copy.form);
    const receipt = event.target.closest('[data-receipt-set]');
    if (receipt) {
      receipt.form.dataset.dirty = 'true';
      for (const select of receipt.form.querySelectorAll('[data-receipt-outcome]')) select.value = receipt.dataset.receiptSet;
    }
  });

  page.addEventListener('cancel', event => {
    if (event.target.matches('dialog[data-restock-details]') && event.target.querySelector('form[data-saving]')) {
      event.preventDefault();
    }
  }, true);

  page.addEventListener('close', event => {
    const dialog = event.target;
    if (!dialog.matches('dialog[data-restock-details]')) return;
    const form = dialog.querySelector('form');
    form.reset();
    form.querySelector('button[type=submit]').disabled = false;
    delete form.dataset.dirty;
    form.querySelector('[data-restock-details-error]').hidden = true;
    if (dialog.hasAttribute('data-refresh-on-close')) {
      delete dialog.dataset.refreshOnClose;
      refreshReport();
    }
  }, true);

  page.addEventListener('change', event => {
    const input = event.target;
    if (input.matches('[data-restock-select-all]')) {
      for (const choice of input.form.querySelectorAll('[name=need_id]')) choice.checked = input.checked;
      updateDraft(input.form);
    }
    if (input.name === 'supplier_id' && !input.checked) {
      const preferred = input.form.querySelector('[data-restock-picker=preferred]');
      if (preferred?.querySelector('[data-picker-key]').value === input.value) {
        preferred.querySelector('[data-picker-key]').value = '';
        preferred.querySelector('[role=combobox]').value = '';
      }
    }
  });

  page.addEventListener('input', event => {
    const form = event.target.closest('form[data-restock-write]');
    if (!form) return;
    form.dataset.dirty = 'true';
    if (form.matches('[data-restock-draft]') && !event.target.matches('[data-restock-select-all]')) updateDraft(form);
  });

  function initializeControls() {
    for (const element of page.querySelectorAll('[data-restock-js]')) element.hidden = false;
    const draft = page.querySelector('[data-restock-draft]');
    if (draft) updateDraft(draft);
  }

  function refreshOnReturn() {
    if (document.visibilityState !== 'visible' || outstandingWrites) return;
    const region = page.querySelector('[data-restock-refresh]');
    if (region && !region.querySelector('form[data-dirty], dialog[open]')) refreshReport();
  }

  main.addEventListener('report:updated', initializeControls);
  document.addEventListener('visibilitychange', refreshOnReturn);
  window.addEventListener('pageshow', event => { if (event.persisted) refreshOnReturn(); });
  initializeControls();
})();
