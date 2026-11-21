/* Importes de Fiados: agrupar cadenas enteras sin convertir dinero a Number. */
(() => {
  'use strict';
  const format = digits => digits.replace(/^0+(?=\d)/, '').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  function parse(value) {
    const raw = String(value).trim();
    if (!/^(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)$/.test(raw)) return null;
    const digits = raw.replace(/\./g, '').replace(/^0+(?=\d)/, '');
    return digits.length <= 16 ? digits : null;
  }
  function caret(value, digitsBefore) {
    if (!digitsBefore) return 0;
    let count = 0;
    for (let n = 0; n < value.length; n++) {
      if (/[0-9]/.test(value[n]) && ++count === digitsBefore) return n + 1;
    }
    return value.length;
  }
  function attach(input) {
    let previous = input.value;
    const initial = parse(previous);
    if (initial !== null) input.value = previous = format(initial);
    function invalid() { input.setCustomValidity('Ingresá un importe entero válido.'); input.reportValidity(); }
    function update(digitsBefore) {
      const raw = input.value;
      const digits = raw.replace(/\./g, '').replace(/^0+(?=\d)/, '');
      if (!/^[0-9.]*$/.test(raw) || digits.length > 16) { input.value = previous; invalid(); return; }
      const before = digitsBefore ?? raw.slice(0, input.selectionStart).replace(/[^0-9]/g, '').length;
      input.value = format(digits);
      previous = input.value;
      input.setCustomValidity('');
      const position = caret(input.value, before);
      input.setSelectionRange(position, position);
    }
    input.addEventListener('beforeinput', event => {
      if (input.readOnly || event.isComposing) return;
      if (event.data && /[^0-9.]/.test(event.data)) { event.preventDefault(); invalid(); return; }
      if (event.data === '.') { event.preventDefault(); return; }
      const start = input.selectionStart, end = input.selectionEnd;
      if (start !== end) return;
      if (event.inputType === 'deleteContentBackward' && input.value[start - 1] === '.') {
        event.preventDefault();
        const before = input.value.slice(0, start).replace(/\D/g, '').length - 1;
        input.value = input.value.slice(0, start - 2) + input.value.slice(start);
        update(before);
      } else if (event.inputType === 'deleteContentForward' && input.value[start] === '.') {
        event.preventDefault();
        const before = input.value.slice(0, start).replace(/\D/g, '').length;
        input.value = input.value.slice(0, start) + input.value.slice(start + 2);
        update(before);
      }
    });
    input.addEventListener('paste', event => {
      const raw = event.clipboardData?.getData('text');
      if (raw === undefined) return;
      event.preventDefault();
      const pasted = parse(raw);
      if (pasted === null) { invalid(); return; }
      const prefix = input.value.slice(0, input.selectionStart).replace(/\D/g, '');
      const suffix = input.value.slice(input.selectionEnd).replace(/\D/g, '');
      if ((prefix + pasted + suffix).replace(/^0+/, '').length > 16) { invalid(); return; }
      input.value = prefix + pasted + suffix;
      update((prefix + pasted).length);
      input.dispatchEvent(new Event('change', {bubbles:true}));
    });
    input.addEventListener('input', () => update());
    input.addEventListener('change', () => {
      if (input.value && parse(input.value) === null) invalid();
    });
  }
  globalThis.CreditMoney = {format, parse, caret, attach};
})();
