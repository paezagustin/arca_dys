(() => {
  const page = document.querySelector('[data-restock]');
  if (!page) return;
  const main = page.closest('main');
  const search = page.querySelector('[data-restock-search]');
  const searchBox = search?.elements.buscar;
  const searchResults = page.querySelector('[data-restock-search-results]');
  const searchStatus = page.querySelector('[data-restock-search-status]');
  const feedback = page.querySelector('[data-restock-feedback]');
  let searchRequest;
  let searchTimer;
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

  async function findProducts() {
    searchRequest?.abort();
    if (!searchBox.value.trim()) {
      searchResults.replaceChildren();
      searchResults.removeAttribute('aria-busy');
      searchStatus.textContent = '';
      return;
    }
    const controller = new AbortController();
    searchRequest = controller;
    searchResults.setAttribute('aria-busy', 'true');
    searchStatus.textContent = 'Buscando productos…';
    try {
      const params = new URLSearchParams({ q: searchBox.value });
      const response = await fetch(`/faltantes/buscar?${params}`, { signal: controller.signal, cache: 'no-store' });
      if (!response.ok) throw new Error('No se pudo buscar. Volvé a intentar.');
      const result = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (controller.signal.aborted) return;
      const restoreFocus = searchResults.contains(document.activeElement);
      searchResults.replaceChildren(...result.body.childNodes);
      if (restoreFocus) searchBox.focus({ preventScroll: true });
      const count = searchResults.querySelectorAll('.restock-match').length;
      searchStatus.textContent = count ? `${count} productos encontrados.` : 'No se encontraron productos.';
    } catch (error) {
      if (!controller.signal.aborted) announce('No se pudo actualizar la búsqueda. Volvé a intentar.', true);
    } finally {
      if (searchRequest === controller) searchResults.removeAttribute('aria-busy');
    }
  }

  searchBox?.addEventListener('input', () => {
    searchRequest?.abort();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(findProducts, 200);
  });
  search?.addEventListener('submit', event => {
    event.preventDefault();
    clearTimeout(searchTimer);
    findProducts();
  });
  if (search) {
    search.classList.add('restock-live-search');
    search.querySelector('button').hidden = true;
  }

  function warnDuplicates(form, products) {
    const box = form.querySelector('[data-restock-duplicates]');
    if (!box) return;
    const entries = products.map(product => {
      const li = document.createElement('li');
      li.textContent = [product.name, product.presentation].filter(Boolean).join(' · ');
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
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    if (form.dataset.saving) return;
    const data = new URLSearchParams(new FormData(form));
    if (event.submitter?.name) data.append(event.submitter.name, event.submitter.value);
    const submit = form.querySelector('button[type=submit]');
    form.dataset.saving = 'true';
    form.setAttribute('aria-busy', 'true');
    if (submit) submit.disabled = true;
    outstandingWrites += 1;
    try {
      const response = await fetch(form.action, { method: 'POST', headers: { Accept: 'application/json' }, body: data });
      const result = await response.json();
      if (!response.ok) {
        announce(result.detail || 'No se pudo guardar. Volvé a intentar.', true);
        if (result.duplicates) warnDuplicates(form, result.duplicates);
        else if (response.status === 409) {
          if (searchBox?.value.trim()) findProducts();
          refreshReport();
        }
        return;
      }
      if (result.url) {
        location.assign(result.url);
        return;
      }
      announce(result.message);
      if (searchBox?.value.trim()) findProducts();
      refreshReport();
    } catch (error) {
      announce('No se pudo confirmar el guardado. Revisá la lista o volvé a intentar.', true);
    } finally {
      outstandingWrites -= 1;
      delete form.dataset.saving;
      form.removeAttribute('aria-busy');
      if (submit) submit.disabled = form.matches('[data-restock-draft]') && !form.querySelector('[name=need_id]:checked');
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
      const unit = form.elements[`unit_${id}`].value.trim();
      const notes = form.elements[`notes_${id}`].value.trim();
      const title = [row.dataset.name, row.dataset.presentation, row.dataset.description].filter(Boolean).join(' · ');
      return '- ' + [title, [quantity, unit].filter(Boolean).join(' '), notes].filter(Boolean).join(' — ');
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
    const copy = event.target.closest('[data-restock-copy]');
    if (copy) copyOrder(copy.form);
    const receipt = event.target.closest('[data-receipt-set]');
    if (receipt) {
      receipt.form.dataset.dirty = 'true';
      for (const select of receipt.form.querySelectorAll('[data-receipt-outcome]')) select.value = receipt.dataset.receiptSet;
    }
  });

  page.addEventListener('change', event => {
    const input = event.target;
    if (input.matches('[data-restock-select-all]')) {
      for (const choice of input.form.querySelectorAll('[name=need_id]')) choice.checked = input.checked;
      updateDraft(input.form);
    }
    const suppliers = input.closest('[data-restock-supplier-options]');
    if (!suppliers) return;
    const preferred = suppliers.querySelector('[name=preferred]');
    if (input === preferred && preferred.value) {
      const match = [...suppliers.querySelectorAll('[name=supplier_id]')].find(option => option.value === preferred.value);
      if (match) match.checked = true;
    } else if (input.name === 'supplier_id' && !input.checked && preferred.value === input.value) {
      preferred.value = '';
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
    if (region && !region.querySelector('form[data-dirty]')) refreshReport();
    if (searchBox?.value.trim() && !searchResults.querySelector('form[data-dirty]')) findProducts();
  }

  main.addEventListener('report:updated', initializeControls);
  document.addEventListener('visibilitychange', refreshOnReturn);
  window.addEventListener('pageshow', event => { if (event.persisted) refreshOnReturn(); });
  initializeControls();
})();
