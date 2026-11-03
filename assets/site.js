document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "URL copiada";
    } catch {
      window.prompt("Copie a URL do feed:", button.dataset.copy);
    }
    window.setTimeout(() => { button.textContent = original; }, 1800);
  });
});
