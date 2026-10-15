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
