document.addEventListener("DOMContentLoaded", () => {
    animateCounters();
    setupInventoryFilters();
    setupMovementFilters();
    setupAlertFilters();
    setupProductForm();
    setupShoppingItemForm();
    setupToastButtons();
    setupLogoutConfirmation();
    setupDeleteConfirmation();
    setupAuthToggle();
    setupGlobalSearch();
});

function showToast(message) {
    const toastElement = document.getElementById("appToast");
    const toastMessage = document.getElementById("appToastMessage");

    if (!toastElement || !toastMessage || !window.bootstrap) {
        alert(message);
        return;
    }

    toastMessage.textContent = message;
    const toast = bootstrap.Toast.getOrCreateInstance(toastElement);
    toast.show();
}

function animateCounters() {
    document.querySelectorAll("[data-counter]").forEach((counter) => {
        const target = Number(counter.dataset.counter);
        const duration = 700;
        const start = performance.now();

        function update(now) {
            const progress = Math.min((now - start) / duration, 1);
            counter.textContent = Math.round(target * progress);

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    });
}

function setupInventoryFilters() {
    const table = document.getElementById("inventoryTable");
    const search = document.getElementById("inventorySearch");
    const category = document.getElementById("categoryFilter");
    const status = document.getElementById("statusFilter");
    const clear = document.getElementById("clearFilters");
    const count = document.getElementById("inventoryCount");

    if (!table || !search || !category || !status || !clear || !count) return;

    const params = new URLSearchParams(window.location.search);
    const searchFromUrl = params.get("buscar");
    if (searchFromUrl) search.value = searchFromUrl;

    const rows = Array.from(table.querySelectorAll("tbody tr"));

    function applyFilters() {
        const text = search.value.trim().toLowerCase();
        const selectedCategory = category.value;
        const selectedStatus = status.value;
        let visible = 0;

        rows.forEach((row) => {
            const rowText = row.textContent.toLowerCase();
            const matchesText = !text || rowText.includes(text);
            const matchesCategory = !selectedCategory || row.dataset.category === selectedCategory;
            const matchesStatus = !selectedStatus || row.dataset.status === selectedStatus;
            const shouldShow = matchesText && matchesCategory && matchesStatus;

            row.classList.toggle("d-none", !shouldShow);
            if (shouldShow) visible += 1;
        });

        count.textContent = `${visible} producto${visible === 1 ? "" : "s"}`;
    }

    [search, category, status].forEach((control) => {
        control.addEventListener("input", applyFilters);
        control.addEventListener("change", applyFilters);
    });

    clear.addEventListener("click", () => {
        search.value = "";
        category.value = "";
        status.value = "";
        applyFilters();
        showToast("Filtros limpiados.");
    });

    applyFilters();
}

function setupMovementFilters() {
    const table = document.getElementById("movementsTable");
    const search = document.getElementById("movementSearch");
    const type = document.getElementById("movementTypeFilter");
    const clear = document.getElementById("clearMovementFilters");
    const count = document.getElementById("movementCount");

    if (!table || !search || !type || !clear || !count) return;

    const params = new URLSearchParams(window.location.search);
    const searchFromUrl = params.get("buscar");
    if (searchFromUrl) search.value = searchFromUrl;

    const rows = Array.from(table.querySelectorAll("tbody tr"));

    function applyFilters() {
        const text = search.value.trim().toLowerCase();
        const selectedType = type.value;
        let visible = 0;

        rows.forEach((row) => {
            const rowText = row.textContent.toLowerCase();
            const matchesText = !text || rowText.includes(text);
            const matchesType = !selectedType || row.dataset.type === selectedType;
            const shouldShow = matchesText && matchesType;

            row.classList.toggle("d-none", !shouldShow);
            if (shouldShow) visible += 1;
        });

        count.textContent = `${visible} movimiento${visible === 1 ? "" : "s"}`;
    }

    [search, type].forEach((control) => {
        control.addEventListener("input", applyFilters);
        control.addEventListener("change", applyFilters);
    });

    clear.addEventListener("click", () => {
        search.value = "";
        type.value = "";
        applyFilters();
        showToast("Filtros limpiados.");
    });

    applyFilters();
}

function setupAlertFilters() {
    const table = document.getElementById("alertsTable");
    const search = document.getElementById("alertSearch");
    const type = document.getElementById("alertTypeFilter");
    const clear = document.getElementById("clearAlertFilters");
    const count = document.getElementById("alertCount");

    if (!table || !search || !type || !clear || !count) return;

    const params = new URLSearchParams(window.location.search);
    const searchFromUrl = params.get("buscar");
    if (searchFromUrl) search.value = searchFromUrl;

    const rows = Array.from(table.querySelectorAll("tbody tr"));

    function applyFilters() {
        const text = search.value.trim().toLowerCase();
        const selectedType = type.value;
        let visible = 0;

        rows.forEach((row) => {
            const rowText = row.textContent.toLowerCase();
            const matchesText = !text || rowText.includes(text);
            const matchesType = !selectedType || row.dataset.status === selectedType;
            const shouldShow = matchesText && matchesType;

            row.classList.toggle("d-none", !shouldShow);
            if (shouldShow) visible += 1;
        });

        count.textContent = `${visible} alerta${visible === 1 ? "" : "s"}`;
    }

    [search, type].forEach((control) => {
        control.addEventListener("input", applyFilters);
        control.addEventListener("change", applyFilters);
    });

    clear.addEventListener("click", () => {
        search.value = "";
        type.value = "";
        applyFilters();
        showToast("Filtros limpiados.");
    });

    applyFilters();
}

// Carga en un select las opciones que dependen de la categoría (subcategorias o
// presentaciones) usando la misma API que el formulario de productos.
async function loadCategoryOptions(select, categoria, tipo, placeholderText, selectFirst) {
    if (!select || !categoria) return;

    try {
        const localOptions = window.productCategoryOptions?.[categoria]?.[tipo];
        let values = localOptions;

        if (!Array.isArray(values)) {
            const response = await fetch(`/api/categorias/${encodeURIComponent(categoria)}/${tipo}`);
            const data = await response.json();
            values = data[tipo] || [];
        }

        // Guarda el valor actual si existe (ej. al editar un producto)
        const currentValue = select.value;
        const isPlaceholder = currentValue === "" || currentValue.startsWith("Selecciona ");

        // Limpiar opciones previas
        select.innerHTML = "";

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = placeholderText;
        select.appendChild(placeholder);

        // Agregar nuevas opciones (algunas categorías pueden no tener subcategorías)
        values.forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });

        // Mantener el valor actual si sigue siendo válido; si no, usar el primero
        if (!isPlaceholder && values.includes(currentValue)) {
            select.value = currentValue;
        } else if (selectFirst && values.length > 0) {
            select.value = values[0];
        }
    } catch (error) {
        console.error(`Error al cargar ${tipo}:`, error);
    }
}

// Enlaza un select de categoría con sus selects dependientes.
function linkCategorySelects(categorySelect, subcategoriaSelect, presentacionSelect) {
    if (!categorySelect) return;

    const refresh = (categoria) => {
        loadCategoryOptions(subcategoriaSelect, categoria, "subcategorias", "Selecciona una subcategoría", false);
        loadCategoryOptions(presentacionSelect, categoria, "presentaciones", "Selecciona una presentación", true);
    };

    categorySelect.addEventListener("change", (event) => refresh(event.target.value));
    refresh(categorySelect.value);
}

function setupShoppingItemForm() {
    // Modal "Artículo nuevo" de la lista de compra: usa las mismas categorías,
    // subcategorías y presentaciones que el registro de productos.
    linkCategorySelects(
        document.getElementById("categoria-compra"),
        document.getElementById("subcategoria-compra"),
        document.getElementById("unidad-compra"),
    );
}

function setupProductForm() {
    const form = document.getElementById("productForm");
    const scanButton = document.getElementById("scanButton");
    const barcodeInput = document.getElementById("barcodeInput");

    linkCategorySelects(
        document.getElementById("categorySelect"),
        document.getElementById("subcategoriaSelect"),
        document.getElementById("presentacionSelect"),
    );

    if (form) {
        form.addEventListener("submit", (event) => {
            const requiredFields = Array.from(form.querySelectorAll("[required]"));
            const isValid = requiredFields.every((field) => field.value.trim());

            if (!isValid) {
                event.preventDefault();
                showToast("Completa los campos obligatorios.");
            }
        });
    }

    if (scanButton && barcodeInput) {
        scanButton.addEventListener("click", () => {
            barcodeInput.value = `770${Math.floor(1000000000 + Math.random() * 8999999999)}`;
            showToast("Código escaneado de prueba.");
        });
    }
}

function setupToastButtons() {
    document.querySelectorAll("[data-toast]").forEach((button) => {
        button.addEventListener("click", () => showToast(button.dataset.toast));
    });
}

function setupLogoutConfirmation() {
    const logout = document.querySelector("[data-confirm-logout]");

    if (!logout) return;

    logout.addEventListener("click", (event) => {
        if (!confirm("¿Deseas cerrar sesión?")) {
            event.preventDefault();
        }
    });
}

function setupDeleteConfirmation() {
    document.querySelectorAll("[data-confirm-delete]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!confirm("¿Deseas eliminar este producto?")) {
                event.preventDefault();
            }
        });
    });
}

function toggleAuthForm(mode) {
    const shell = document.querySelector(".auth-form-shell");
    const optionButtons = document.querySelectorAll(".auth-option");
    const formPanels = {
        login: document.getElementById("loginFormPanel"),
        register: document.getElementById("registerFormPanel")
    };

    if (!shell || !formPanels.login || !formPanels.register) return;

    shell.classList.remove("hidden");
    shell.style.display = "block";

    optionButtons.forEach((button) => {
        const isActive = button.dataset.auth === mode;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
        button.setAttribute("aria-selected", String(isActive));
    });

    Object.entries(formPanels).forEach(([key, panel]) => {
        const shouldShow = key === mode;
        panel.style.display = shouldShow ? "block" : "none";
        panel.classList.toggle("is-hidden", !shouldShow);
        if (shouldShow) {
            panel.querySelector("input")?.focus();
        }
    });
}

function setupAuthToggle() {
    const shell = document.querySelector(".auth-form-shell");
    const optionButtons = document.querySelectorAll(".auth-option");
    const formPanels = {
        login: document.getElementById("loginFormPanel"),
        register: document.getElementById("registerFormPanel")
    };

    if (!optionButtons.length || !formPanels.login || !formPanels.register) return;

    shell?.classList.add("hidden");
    shell && (shell.style.display = "none");

    Object.values(formPanels).forEach((panel) => {
        panel.style.display = "none";
        panel.classList.add("is-hidden");
    });

    const initialMode = document.querySelector(".auth-option.active")?.dataset.auth || "login";
    toggleAuthForm(initialMode);

    optionButtons.forEach((button) => {
        button.addEventListener("click", () => toggleAuthForm(button.dataset.auth));
    });
}

function setupGlobalSearch() {
    const globalSearch = document.getElementById("globalSearch");
    if (!globalSearch) return;

    const routes = [
        { keywords: ["dashboard", "inicio", "resumen"], url: "/dashboard" },
        { keywords: ["inventario", "producto", "productos", "buscar"], url: "/inventario" },
        { keywords: ["registrar", "nuevo", "agregar", "crear"], url: "/producto/nuevo" },
        { keywords: ["alerta", "alertas", "vencimiento", "vencidos"], url: "/alertas" },
        { keywords: ["compra", "compras", "lista de compra", "mercado"], url: "/lista-compra" },
    ];

    globalSearch.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;

        event.preventDefault();
        const query = globalSearch.value.trim().toLowerCase();
        if (!query) return;

        const match = routes.find((route) => route.keywords.some((keyword) => query.includes(keyword)));

        if (match) {
            window.location.href = match.url;
            return;
        }

        window.location.href = `/inventario?buscar=${encodeURIComponent(query)}`;
    });
}
