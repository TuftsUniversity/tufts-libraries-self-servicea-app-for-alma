class FilmSearcher extends HTMLElement {
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
            console.warn("No data-token provided.");
            this.shadowRoot.innerHTML = `
                <style>
                    .error { color: red; font-weight: bold; }
                </style>
                <p class="error">Access denied: no token provided.</p>
            `;
            return;
        }

        this.apiUrl = `${this.baseUrl}/film_search/search`;
        this.templateUrl = `${this.baseUrl}/film_search/component-template`;

        this.loadTemplate();
    }

    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl);
            if (!response.ok) throw new Error("Failed to load film-search template");

            const html = await response.text();
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();

            const template = wrapper.querySelector("template");
            if (!template) {
                console.error("film-search template missing <template> tag");
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

    async injectStyles() {
        try {
            const cssUrl = `${this.baseUrl}/static/styles.css`;
            const response = await fetch(cssUrl);
            if (!response.ok) throw new Error("Failed to load CSS");

            const css = await response.text();
            const styleTag = document.createElement("style");
            styleTag.textContent = css;
            this.shadowRoot.appendChild(styleTag);
        } catch (err) {
            console.error("Error injecting CSS:", err);
        }
    }

    injectHourglass() {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = `
            <div id="hourglass" style="display: none;">
                <div class="spinner"></div>
            </div>
        `;
        this.shadowRoot.appendChild(wrapper);
    }

    showHourglass() {
        const hg = this.shadowRoot.getElementById("hourglass");
        if (hg) hg.style.display = "block";
    }

    hideHourglass() {
        const hg = this.shadowRoot.getElementById("hourglass");
        if (hg) hg.style.display = "none";
    }

    attachEventListeners() {
        const form = this.shadowRoot.getElementById("filmSearchForm");

        if (!form) {
            console.error("filmSearchForm not found inside template");
            return;
        }

        form.action = this.apiUrl;
        form.addEventListener("submit", (event) => this.handleFormSubmit(event));
    }

    async handleFormSubmit(event) {
        event.preventDefault();
        this.showHourglass();

        const form = event.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(this.apiUrl, {
                method: "POST",
                headers: {
                    ...(this.token ? { "Authorization": `Bearer ${this.token}` } : {})
                },
                body: formData
            });

            if (!response.ok) throw new Error("Film search failed");

            const blob = await response.blob();

            // Try to extract filename from response header (Flask sets download_name)
            let filename = "swank_results.xlsx";
            const disposition = response.headers.get("Content-Disposition");
            if (disposition && disposition.includes("filename=")) {
                filename = disposition.split("filename=")[1].replace(/"/g, '');
            }

            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            console.error("Error during film-search request:", error);
        } finally {
            this.hideHourglass();
        }
    }
}

customElements.define("film-searcher", FilmSearcher);
