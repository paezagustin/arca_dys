(() => {
  function attach(root, { load, render, choose, edit, results, emptyMessage, signal }) {
    const input = root.querySelector('[role=combobox]');
    const options = root.querySelector('[role=listbox]');
    const status = root.querySelector('[data-suggestions-status]');
    let controller, timer, rows = [], active = -1, touching = false, selecting = false;

    function close() {
      clearTimeout(timer);
      controller?.abort();
      options.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    }

    function position() {
      if (options.hidden || !root.isConnected) return;
      const rect = input.getBoundingClientRect(), viewport = window.visualViewport;
      const top = viewport?.offsetTop || 0;
      const bottom = top + (viewport?.height || window.innerHeight);
      const below = bottom - rect.bottom - 12, above = rect.top - top - 12;
      const flip = below < 150 && above > below;
      const height = Math.max(60, Math.min(280, flip ? above : below));
      options.style.left = `${rect.left}px`;
      options.style.width = `${rect.width}px`;
      options.style.maxHeight = `${height}px`;
      options.style.top = `${flip ? Math.max(top + 4, rect.top - Math.min(options.scrollHeight, height) - 4) : rect.bottom + 4}px`;
    }

    function highlight(index) {
      if (!rows.length) return;
      active = Math.max(0, Math.min(index, rows.length - 1));
      [...options.children].forEach((item, n) => item.setAttribute('aria-selected', String(n === active)));
      const current = options.children[active];
      input.setAttribute('aria-activedescendant', current.id);
      if (current.offsetTop < options.scrollTop) options.scrollTop = current.offsetTop;
      if (current.offsetTop + current.offsetHeight > options.scrollTop + options.clientHeight) {
        options.scrollTop = current.offsetTop + current.offsetHeight - options.clientHeight;
      }
    }

    function pick(index) {
      selecting = true;
      touching = false;
      close();
      choose(rows[index]);
      input.focus({ preventScroll: true });
      selecting = false;
    }

    async function search(first = null) {
      controller?.abort();
      controller = new AbortController();
      const searchSignal = controller.signal;
      try {
        const found = await load(input.value, searchSignal);
        if (searchSignal.aborted || input.disabled || document.activeElement !== input) return;
        rows = found;
        active = -1;
        input.removeAttribute('aria-activedescendant');
        options.replaceChildren();
        rows.forEach((row, index) => {
          const option = document.createElement('li');
          option.id = `${options.id}-${index + 1}`;
          option.setAttribute('role', 'option');
          option.setAttribute('aria-selected', 'false');
          render(option, row);
          option.addEventListener('mousedown', event => event.preventDefault());
          option.addEventListener('pointerdown', () => { touching = true; });
          option.addEventListener('pointercancel', () => { touching = false; });
          option.addEventListener('click', () => pick(index));
          options.append(option);
        });
        const empty = emptyMessage(input.value);
        if (!rows.length && empty) {
          const item = document.createElement('li');
          item.className = 'suggestion-empty';
          item.textContent = empty;
          options.append(item);
        }
        const show = Boolean(options.children.length);
        options.hidden = !show;
        input.setAttribute('aria-expanded', String(show));
        status.textContent = rows.length ? `${rows.length} ${rows.length === 1 ? 'coincidencia' : 'coincidencias'}. Usá las flechas y Enter para elegir.` : empty;
        results?.(rows);
        position();
        if (rows.length && first !== null) highlight(first < 0 ? rows.length - 1 : 0);
      } catch {
        if (!searchSignal.aborted) {
          close();
          status.textContent = 'No se pudo buscar. Volvé a escribir para intentarlo otra vez.';
        }
      }
    }

    const events = { signal };
    input.addEventListener('input', () => {
      close();
      status.textContent = '';
      edit?.();
      timer = setTimeout(search, 150);
    }, events);
    input.addEventListener('focus', () => { if (!selecting) search(); }, events);
    input.addEventListener('blur', () => { setTimeout(() => { if (!touching) close(); }, 0); }, events);
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !options.hidden) {
        event.preventDefault(); event.stopPropagation(); close();
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const direction = event.key === 'ArrowDown' ? 1 : -1;
        if (options.hidden) search(direction);
        else highlight(active === -1 && direction === -1 ? rows.length - 1 : active + direction);
      } else if (event.key === 'Enter' && !options.hidden && (active >= 0 || root.hasAttribute('data-manual-choice'))) {
        event.preventDefault();
        if (active >= 0) pick(active);
      } else if (event.key === 'Tab') close();
    }, events);
    window.addEventListener('resize', position, events);
    window.addEventListener('scroll', position, { ...events, capture: true });
    window.visualViewport?.addEventListener('resize', position, events);
    window.visualViewport?.addEventListener('scroll', position, events);
    document.addEventListener('pointerup', () => { touching = false; }, events);
    signal?.addEventListener('abort', close, { once: true });
    return { close };
  }

  window.AppSuggestions = { attach };
})();
