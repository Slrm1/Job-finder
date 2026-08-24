document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.name !== "resume") return;
  const slot = document.querySelector("[data-file-name]");
  const file = input.files && input.files[0];
  if (slot && file) slot.textContent = file.name;
});
