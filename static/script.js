document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("search-input");
  const filter = document.getElementById("department-filter");
  const cards = [...document.querySelectorAll(".employee-card")];
  const noResults = document.getElementById("no-results");
  const resultCount = document.getElementById("result-count");

  function applyFilters() {
    if (!search) return;
    const query = search.value.trim().toLocaleLowerCase("ru");
    const department = filter ? filter.value.toLocaleLowerCase("ru") : "";
    let visible = 0;
    cards.forEach(card => {
      const haystack = [
        card.dataset.name,
        card.dataset.position,
        card.dataset.department,
        card.dataset.phone,
        card.dataset.office,
        card.dataset.city,
        card.dataset.birthDate,
      ].filter(Boolean).join(" ");
      const matchesText = haystack.includes(query);
      const matchesDepartment = !department || card.dataset.department === department;
      const show = matchesText && matchesDepartment;
      card.classList.toggle("hidden", !show);
      if (show) visible++;
    });
    if (resultCount) resultCount.textContent = `${visible} из ${cards.length}`;
    if (noResults) noResults.classList.toggle("hidden", visible !== 0 || cards.length === 0);
  }
  if (search) search.addEventListener("input", applyFilters);
  if (filter) filter.addEventListener("change", applyFilters);

  const photoInput = document.getElementById("photo-input");
  const fileHint = document.getElementById("file-hint");
  if (photoInput) photoInput.addEventListener("change", () => {
    const file = photoInput.files[0];
    if (file && file.size > 5 * 1024 * 1024) {
      alert("Размер фотографии не должен превышать 5 МБ.");
      photoInput.value = "";
      fileHint.textContent = "Файл не выбран · до 5 МБ";
    } else if (file) fileHint.textContent = file.name;
    else fileHint.textContent = "Файл не выбран · до 5 МБ";
  });

  const form = document.getElementById("employee-form");
  const title = document.getElementById("form-title");
  const save = document.getElementById("save-button");
  const cancel = document.getElementById("cancel-edit");
  if (form) {
    document.querySelectorAll(".edit-button").forEach(button => {
      button.addEventListener("click", () => {
        form.action = `/employees/${button.dataset.id}/edit`;
        form.elements.full_name.value  = button.dataset.name || "";
        form.elements.birth_date.value = button.dataset.birthDate || "";
        form.elements.office.value     = button.dataset.office || "";
        form.elements.department.value = button.dataset.department || "";
        form.elements.position.value   = button.dataset.position || "";
        form.elements.city.value       = button.dataset.city || "";
        form.elements.phone.value      = button.dataset.phone || "";
        form.elements.username.value   = button.dataset.username || "";
        form.elements.password.value   = "";
        form.elements.password.required = false;
        title.textContent = "Редактировать сотрудника";
        save.textContent = "Сохранить изменения";
        cancel.classList.remove("hidden");
        document.getElementById("add-form").scrollIntoView({behavior:"smooth"});
      });
    });
    function resetForm() {
      form.reset();
      form.action = "/employees";
      form.elements.password.required = true;
      title.textContent = "Добавить сотрудника";
      save.textContent = "Добавить сотрудника";
      cancel.classList.add("hidden");
      if (fileHint) fileHint.textContent = "Файл не выбран · до 5 МБ";
    }
    if (cancel) cancel.addEventListener("click", resetForm);
  }

  document.querySelectorAll('input[type="tel"]').forEach(input => {
    input.addEventListener("input", () => input.value = input.value.replace(/[^\d+\-()\s]/g, ""));
  });
});