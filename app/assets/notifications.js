/* Mensajes transitorios compartidos. El popover queda sobre los diálogos nativos. */
(() => {
  'use strict';
  const host = document.createElement('div');
  host.className = 'notification-stack'; host.id = 'notification-stack';
  host.setAttribute('popover', 'manual'); document.body.append(host);
  function raise() {
    if (!host.children.length) return;
    if (host.showPopover) {
      if (host.matches(':popover-open')) host.hidePopover();
      host.showPopover();
    } else {
      (document.querySelector('dialog[open]') || document.body).append(host);
    }
  }
  function show(message, {error = false, warning = false} = {}) {
    const toast = document.createElement('div'), content = document.createElement('div');
    toast.className = 'app-notification' + (error ? ' error' : warning ? ' warning' : '');
    toast.setAttribute('role', error || warning ? 'alert' : 'status');
    if (typeof message === 'string') content.textContent = message;
    else content.append(message);
    const close = document.createElement('button');
    close.type = 'button'; close.className = 'notification-close';
    close.setAttribute('aria-label', 'Cerrar notificación'); close.textContent = '×';
    const dismiss = () => {
      clearTimeout(timer); toast.remove();
      if (!host.children.length && host.hidePopover && host.matches(':popover-open')) host.hidePopover();
    };
    close.addEventListener('click', dismiss);
    toast.append(content, close); host.append(toast); raise();
    const timer = setTimeout(dismiss, 2000);
    return dismiss;
  }
  window.AppNotifications = {show};
  const previous = new WeakMap();
  function scan() {
    document.querySelectorAll('.notice[role="status"],.notice[role="alert"]').forEach(source => {
      if (source.hidden || source.closest('#notification-stack,template')
          || source.matches('[data-inline-notice],.report-feedback,.sr-only')) return;
      const signature = source.textContent.trim() + ':' + source.classList.contains('error') + ':' + source.classList.contains('warning');
      if (!source.textContent.trim() || previous.get(source) === signature) return;
      previous.set(source, signature);
      const content = document.createElement('div');
      source.childNodes.forEach(node => content.append(node.cloneNode(true)));
      source.classList.add('notification-source');
      show(content, {error:source.classList.contains('error'), warning:source.classList.contains('warning')});
    });
  }
  scan();
  new MutationObserver(records => {
    scan();
    if (records.some(record => record.attributeName === 'open')) raise();
  }).observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['hidden','class','open']});
})();
