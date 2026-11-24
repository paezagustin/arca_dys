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

  function supplierList(section, input) {
    const list = section.querySelector('[data-supplier-list]');
    const template = section.querySelector('template');
    const status = section.querySelector('[data-association-status]');
    const empty = section.querySelector('[data-no-suppliers]');
    function ids() {
      return [...list.querySelectorAll('[name=supplier_id]')].map(field => field.value);
    }
    function add(supplier) {
      if (!ids().includes(String(supplier.id))) {
        const item = template.content.firstElementChild.cloneNode(true);
        item.querySelector('input').value = supplier.id;
        item.querySelector('[data-supplier-name]').textContent = supplier.name;
        item.querySelector('button').setAttribute('aria-label', `Eliminar ${supplier.name}`);
        list.append(item);
        empty.hidden = true;
        status.textContent = `${supplier.name} agregado a la lista.`;
      }
      input.value = '';
      input.setCustomValidity('');
    }
    section.addEventListener('click', event => {
      const remove = event.target.closest('[data-remove-supplier]');
      if (!remove) return;
      const item = remove.closest('tr');
      const next = item.nextElementSibling || item.previousElementSibling;
      status.textContent = `${item.querySelector('[data-supplier-name]').textContent} retirado de la lista.`;
      item.remove();
      empty.hidden = Boolean(list.childElementCount);
      (next?.querySelector('button') || input).focus({ preventScroll: true });
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') event.preventDefault();
    });
    input.addEventListener('input', () => input.setCustomValidity(input.value.trim()
      ? 'Elegí un proveedor de las sugerencias o borrá la búsqueda.' : ''));
    return { ids, add };
  }

  function initializePicker(root) {
    const mode = root.dataset.restockPicker;
    const input = root.querySelector('[role=combobox]');
    const key = root.querySelector('[data-picker-key]');
    const form = input.form;
    const isProduct = mode === 'register' || mode === 'product';
    const associated = mode === 'associate' ? supplierList(root.closest('[data-linked-suppliers]'), input) : null;

    AppSuggestions.attach(root, {
      async load(value, signal) {
        if (isProduct && !value.trim()) return [];
        const url = new URL(root.dataset.endpoint, location.origin);
        url.searchParams.set('q', value);
        if (associated) for (const id of associated.ids()) url.searchParams.append('excluir', id);
        const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
        if (!response.ok) throw Error('search');
        return response.json();
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
        if (associated) {
          associated.add(row);
          return;
        }
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
        form.requestSubmit();
      },
      edit() {
        if (mode === 'register') resetRegistration();
        else if (mode === 'supplier' && !input.value.trim() && key.value) {
          key.value = '';
          form.requestSubmit();
        } else if (key && mode !== 'supplier') {
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
    const details = form.closest('dialog[data-restock-details]');
    if (form.dataset.saving || details?.querySelector('form[data-saving]') || details?.hasAttribute('data-refresh-on-close')) return;
    const data = new URLSearchParams(new FormData(form));
    if (event.submitter?.name) data.append(event.submitter.name, event.submitter.value);
    const submit = event.submitter || form.querySelector('button[type=submit], [data-confirm-trigger]');
    const detailsError = details?.querySelector('[data-restock-details-error]');
    const dialogButtons = details?.querySelectorAll('button') || [];
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
    for (const button of dialogButtons) button.disabled = true;
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
      const stale = details?.hasAttribute('data-refresh-on-close');
      for (const button of dialogButtons) button.disabled = stale && !button.matches('[data-restock-details-close]');
      if (submit) submit.disabled = stale || (form.matches('[data-restock-draft]') && !form.querySelector('[name=need_id]:checked'));
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
    form.elements.confirmed.disabled = !message || Boolean(form.dataset.saving);
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
    if (quickCreate && event.target.closest('[data-cancel-quick]')) {
      event.preventDefault();
      resetRegistration();
      search.elements.buscar.value = '';
      search.elements.buscar.focus({ preventScroll: true });
      return;
    }
    const details = event.target.closest('[data-restock-details-open]');
    if (details) {
      const dialog = document.getElementById(details.getAttribute('aria-controls'));
      if (dialog.matches('[data-line-editor]')) {
        const row = details.closest('tr');
        dialog.querySelector('[data-line-title]').textContent = row.dataset.name;
        dialog.dataset.opener = details.dataset.reportFocusKey;
        for (const field of row.querySelectorAll('[data-line-field]')) {
          const editor = dialog.querySelector('form').elements.namedItem(field.dataset.lineField);
          editor.value = field.value;
          editor.setCustomValidity('');
        }
      }
      dialog.showModal();
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
      for (const select of receipt.form.querySelectorAll('[data-receipt-outcome]')) {
        select.value = receipt.dataset.receiptSet;
        displayLineField(select);
      }
    }
  });

  function displayLineField(field) {
    const value = field.selectedOptions ? field.selectedOptions[0].textContent : field.value.trim();
    field.closest('tr').querySelector(`[data-line-display="${field.dataset.lineField}"]`).textContent = value || '—';
  }

  page.addEventListener('submit', event => {
    const dialog = event.target.closest('dialog[data-line-editor]');
    if (!dialog) return;
    event.preventDefault();
    const editor = event.target;
    const quantity = editor.elements.quantity;
    if (quantity && quantity.value.trim()) {
      const value = quantity.value.trim().replace(',', '.');
      if (!/^\d{1,9}(?:\.\d{1,3})?$/.test(value) || Number(value) <= 0) {
        quantity.setCustomValidity('Ingresá una cantidad positiva de hasta 9 enteros y 3 decimales, o dejala vacía.');
        quantity.reportValidity();
        return;
      }
    }
    const row = page.querySelector(`[data-report-focus-key="${CSS.escape(dialog.dataset.opener)}"]`).closest('tr');
    for (const field of row.querySelectorAll('[data-line-field]')) {
      field.value = editor.elements.namedItem(field.dataset.lineField).value.trim();
      displayLineField(field);
    }
    const form = row.closest('form');
    form.dataset.dirty = 'true';
    if (form.matches('[data-restock-draft]')) updateDraft(form);
    dialog.close();
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
    for (const button of dialog.querySelectorAll('button')) button.disabled = false;
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
  });

  page.addEventListener('input', event => {
    if (event.target.matches('[data-line-editor] [name=quantity]')) event.target.setCustomValidity('');
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
