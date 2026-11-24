(() => {
  const main = document.querySelector('main');
  const resultSelector = '[data-report-results]';
  const filterSelector = 'form[data-report-filter]';
  if (!main?.querySelector(resultSelector)) return;

  const feedback = document.createElement('p');
  feedback.className = 'report-feedback sr-only';
  feedback.setAttribute('role', 'status');
  main.append(feedback);
  const filter = main.querySelector(filterSelector);
  let currentRequest;

  function announce(message, { visible = false, error = false } = {}) {
    feedback.classList.add('sr-only');
    if (visible) window.AppNotifications?.show(message, {error});
    feedback.classList.toggle('error', error);
    feedback.textContent = message;
  }

  function replaceResult(region, updated) {
    const focused = document.activeElement;
    const restoreFocus = region.contains(focused);
    const tableScroll = [...region.querySelectorAll('.table-wrap')].map(table => table.scrollLeft);
    region.replaceWith(updated);
    updated.querySelectorAll('.table-wrap').forEach((table, index) => {
      table.scrollLeft = tableScroll[index] ?? 0;
    });
    if (!restoreFocus) return;
    const pager = updated.querySelector('.pagination');
    const focusKey = focused.dataset.reportFocusKey;
    const destination = (focusKey && updated.querySelector(`[data-report-focus-key="${CSS.escape(focusKey)}"]`))
      || (focused.rel && pager?.querySelector(`a[rel="${focused.rel}"]`))
      || pager || updated.querySelector('.report-heading') || updated;
    if (destination.tabIndex < 0) destination.tabIndex = -1;
    destination.focus({ preventScroll: true });
  }

  function syncFilter(controls, updatedFilter) {
    for (const [control, sentValue] of controls) {
      const updated = control.name ? updatedFilter.elements.namedItem(control.name)
        : updatedFilter.querySelector(`#${CSS.escape(control.id)}`);
      if (!updated) continue;
      const unchanged = control.value === sentValue;
      // Preserve an edit that the user made while the previous query was in flight.
      if (unchanged && control.value !== updated.value) control.value = updated.value;
      if (control instanceof HTMLInputElement && control.type !== 'hidden') {
        if (!unchanged) {
          const current = control.value;
          control.defaultValue = updated.value;
          control.value = current;
        } else {
          control.defaultValue = updated.value;
        }
      }
    }
  }

  async function refresh(url, { key, restore = false, quiet = false } = {}) {
    currentRequest?.abort();
    const controller = new AbortController();
    currentRequest = controller;
    const regions = [...main.querySelectorAll(resultSelector)];
    const affected = regions.filter(region => !key || region.dataset.reportResults === key);
    const controls = !key && filter ? [...filter.elements]
      .filter(control => (control.name || control.matches('[data-report-value][id]')) && control.matches('input, select'))
      .map(control => [control, control.value]) : [];
    regions.forEach(region => region.removeAttribute('aria-busy'));
    affected.forEach(region => region.setAttribute('aria-busy', 'true'));
    announce('Actualizando resultados…', { visible: !quiet });

    try {
      const response = await fetch(url, {
        signal: controller.signal, redirect: 'manual', headers: { Accept: 'text/html' }
      });
      if (response.type === 'opaqueredirect' || response.redirected || response.status === 401 || response.status === 403) {
        throw new Error('No se pudo acceder al reporte. Volvé a abrir la página e intentá otra vez.');
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (controller.signal.aborted) return;
      if (!response.ok) {
        const validation = response.status === 422 && page.querySelector('main .notice.error')?.textContent;
        throw new Error(validation || 'No se pudo actualizar el reporte. Volvé a intentar.');
      }
      const results = new Map([...page.querySelectorAll(`main ${resultSelector}`)]
        .map(region => [region.dataset.reportResults, region]));
      const updatedFilter = page.querySelector(`main ${filterSelector}`);
      if (regions.some(region => !results.has(region.dataset.reportResults)) || (filter && !updatedFilter)) {
        throw new Error('No se pudo leer el reporte. Volvé a abrir la página e intentá otra vez.');
      }

      const { scrollX, scrollY } = window;
      if (!key && filter) syncFilter(controls, updatedFilter);
      for (const region of regions) {
        const updated = results.get(region.dataset.reportResults);
        if (!key || region.dataset.reportResults === key) {
          region.removeAttribute('aria-busy');
          if (!region.isEqualNode(updated)) replaceResult(region, updated);
        } else {
          // Other pagers must carry the newly applied page number in their links.
          for (const link of region.querySelectorAll('.pagination a[rel]')) {
            const newLink = updated.querySelector(`.pagination a[rel="${link.rel}"]`);
            if (newLink) link.setAttribute('href', newLink.getAttribute('href'));
          }
        }
      }
      if (!restore && url.href !== location.href) history.pushState(null, '', url);
      window.scrollTo(scrollX, scrollY);
      announce('Resultados actualizados.');
      main.dispatchEvent(new Event('report:updated'));
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = error instanceof TypeError ? 'No se pudo conectar. Volvé a intentar.' : error.message;
      announce(`${message} Se conservan los resultados anteriores.`, { visible: true, error: true });
    } finally {
      if (currentRequest === controller) {
        affected.forEach(region => region.removeAttribute('aria-busy'));
        currentRequest = undefined;
      }
    }
  }

  filter?.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    event.preventDefault();
    const url = new URL(filter.action);
    url.search = new URLSearchParams(new FormData(filter));
    refresh(url);
  });

  main.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[data-report-link], .pagination a[rel]');
    if (!link || link.target || link.hasAttribute('download')) return;
    const key = link.closest('.pagination') && link.closest(resultSelector)?.dataset.reportResults;
    if (!key && !link.hasAttribute('data-report-link')) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname) return;
    event.preventDefault();
    refresh(url, { key });
  });

  window.addEventListener('popstate', () => refresh(new URL(location.href), { restore: true }));
  main.addEventListener('report:refresh', () => refresh(new URL(location.href), { restore: true, quiet: true }));
})();
