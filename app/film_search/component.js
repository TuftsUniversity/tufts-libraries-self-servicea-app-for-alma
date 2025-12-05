class FilmSearchComponent extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.baseUrl = this.getAttribute("base-url");
        this.token = this.getAttribute("data-token");

        if (!this.baseUrl) {
            console.error("Missing 'base-url' attribute!");
            return;
        }

        if (!this.token) {
            console.warn("No data-token attribute provided.");
            this.shadowRoot.innerHTML = `
                <style>.error { color: red; font-weight: bold; }</style>
                <p class="error">Access denied: no token provided.</p>
            `;
            return;
        }

        this.templateUrl = `${this.baseUrl}/film_search/component-template`;

        this.loadTemplate();
    }

    /* ----------------------------------------------------- */
    /* Load Template                                          */
    /* ----------------------------------------------------- */
    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl, { method: "GET" });
            if (!response.ok) throw new Error("Failed to load film-search template");

            const html = await response.text();

            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();

            const template = wrapper.querySelector("template#film-search-template");
            if (!template) {
                console.error("No <template id='film-search-template'> found in HTML.");
                return;
            }

            this.shadowRoot.appendChild(template.content.cloneNode(true));

            await this.injectStyles();
            this.injectHourglass();
            this.attachEventListeners();

        } catch (err) {
            console.error("Error loading film-search template:", err);
        }
    }

    /* ----------------------------------------------------- */
    /* Inject Shared Styles                                   */
    /* ----------------------------------------------------- */
    async injectStyles() {
        try {
            const cssUrl = `${this.baseUrl}/static/styles.css`;
            const cssResponse = await fetch(cssUrl);
            if (!cssResponse.ok) throw new Error("Failed to load CSS");

            const cssText = await cssResponse.text();
            const styleTag = document.createElement("style");
            styleTag.textContent = cssText;
            this.shadowRoot.appendChild(styleTag);

        } catch (err) {
            console.error("Error injecting styles:", err);
        }
    }

    /* ----------------------------------------------------- */
    /* Hourglass Spinner                                      */
    /* ----------------------------------------------------- */
    injectHourglass() {
        const hg = document.createElement("div");
        hg.innerHTML = `
            <div id="hourglass" style="display:none;">
                <div class="spinner"></div>
            </div>
        `;
        this.shadowRoot.appendChild(hg);
    }

    showHourglass() {
        const hg = this.shadowRoot.getElementById("hourglass");
        if (hg) hg.style.display = "block";
    }

    hideHourglass() {
        const hg = this.shadowRoot.getElementById("hourglass");
        if (hg) hg.style.display = "none";
    }

    /* ----------------------------------------------------- */
    /* Attach Event Listeners for BOTH forms                  */
    /* ----------------------------------------------------- */
    attachEventListeners() {
        // Swank Search Form
        const swankForm = this.shadowRoot.getElementById("swank-search-form");
        if (swankForm) {
            swankForm.addEventListener("submit", (e) =>
                this.handleSearchSubmit(e, `${this.baseUrl}/film_search/search`)
            );
        } else {
            console.error("Swank search form NOT found in template.");
        }

        // Criterion Search Form
        const criterionForm = this.shadowRoot.getElementById("criterion-search-form");
        if (criterionForm) {
            criterionForm.addEventListener("submit", (e) =>
                this.handleSearchSubmit(e, `${this.baseUrl}/film_search/criterion_search`)
            );
        } else {
            console.error("Criterion search form NOT found in template.");
        }
    }

    /* ----------------------------------------------------- */
    /* Generic Handler for Both Search Types                  */
    /* ----------------------------------------------------- */
    async handleSearchSubmit(event, apiEndpoint) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);

        this.showHourglass();

        try {
            const response = await fetch(apiEndpoint, {
                method: "POST",
                headers: {
                    ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
                },
                body: formData,
            });

            if (!response.ok) {
                console.error("Film search request failed:", response.status);
                throw new Error("Request failed");
            }

            const blob = await response.blob();

            const filename =
                response.headers.get("Content-Disposition")?.split("filename=")[1] ||
                "film_results.xlsx";

            const link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = filename.replace(/"/g, "");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (err) {
            console.error("Error performing film search:", err);
        } finally {
            this.hideHourglass();
        }
    }
}

/* Register the Web Component */
customElements.define("film-search", FilmSearchComponent);
