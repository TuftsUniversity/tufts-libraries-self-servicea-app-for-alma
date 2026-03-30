class FilmSearchComponent extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });

        this.routeMap = {
            all: "/film_search/search_all",
            swank: "/film_search/run_search_swank",
            kanopy: "/film_search/kanopy_search",
            criterion: "/film_search/criterion_search",
            docuseek: "/film_search/run_docuseek_search",
            newday: "/film_search/run_newday_search",
            alexander: "/film_search/run_alexander_search",
        };
    }

    connectedCallback() {
        this.baseUrl = (this.getAttribute("base-url") || "").replace(/\/$/, "");
        this.token = this.getAttribute("data-token");

        if (!this.baseUrl) {
            console.error("Missing 'base-url' attribute.");
            this.renderError("Configuration error: missing base URL.");
            return;
        }

        this.templateUrl = `${this.baseUrl}/film_search/component-template`;
        this.loadTemplate();
    }

    renderError(message) {
        this.shadowRoot.innerHTML = `
            <style>
                .error {
                    color: red;
                    font-weight: bold;
                    padding: 0.75rem;
                }
            </style>
            <div class="error">${message}</div>
        `;
    }

    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl, { method: "GET" });
            if (!response.ok) {
                throw new Error(`Failed to load template: ${response.status}`);
            }

            const html = await response.text();
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();

            const template = wrapper.querySelector("template#film-search");
            if (!template) {
                throw new Error("No <template id=\"film-search\"> found.");
            }

            this.shadowRoot.innerHTML = "";
            this.shadowRoot.appendChild(template.content.cloneNode(true));

            await this.injectStyles();
            this.injectHourglass();
            this.attachEventListeners();
        } catch (error) {
            console.error("Error loading film search component:", error);
            this.renderError("Unable to load film search form.");
        }
    }

    async injectStyles() {
        try {
            const cssUrl = `${this.baseUrl}/static/styles.css`;
            const response = await fetch(cssUrl);

            if (!response.ok) {
                throw new Error(`Failed to load CSS: ${response.status}`);
            }

            const cssText = await response.text();
            const style = document.createElement("style");
            style.textContent = cssText;
            this.shadowRoot.appendChild(style);
        } catch (error) {
            console.error("Error injecting styles:", error);
        }
    }

    injectHourglass() {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = `
            <style>
                #hourglass {
                    display: none;
                    margin-top: 1rem;
                }
            </style>
            <div id="hourglass">
                <div class="spinner"></div>
            </div>
        `;
        this.shadowRoot.appendChild(wrapper);
    }

    showHourglass() {
        const hourglass = this.shadowRoot.getElementById("hourglass");
        if (hourglass) {
            hourglass.style.display = "block";
        }
    }

    hideHourglass() {
        const hourglass = this.shadowRoot.getElementById("hourglass");
        if (hourglass) {
            hourglass.style.display = "none";
        }
    }

    attachEventListeners() {
        const form = this.shadowRoot.getElementById("film-search-form");
        if (!form) {
            console.error("film-search-form not found.");
            return;
        }

        form.addEventListener("submit", (event) => this.handleSearchSubmit(event));
    }

    getEndpointForSelection() {
        const searchTarget = this.shadowRoot.getElementById("search_target");
        const selectedValue = searchTarget ? searchTarget.value : "all";
        const routePath = this.routeMap[selectedValue] || this.routeMap.all;
        return `${this.baseUrl}${routePath}`;
    }

    async handleSearchSubmit(event) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);
        const title = (formData.get("title") || "").toString().trim();

        if (!title) {
            alert("Please enter a film title.");
            return;
        }

        const endpoint = this.getEndpointForSelection();
        this.showHourglass();

        try {
            const headers = {};
            if (this.token) {
                headers["Authorization"] = `Bearer ${this.token}`;
            }

            const response = await fetch(endpoint, {
                method: "POST",
                headers,
                body: formData,
            });

            if (!response.ok) {
                let errorMessage = `Film search request failed: ${response.status}`;
                try {
                    const text = await response.text();
                    if (text) {
                        errorMessage = text;
                    }
                } catch (_err) {
                    // ignore secondary read failure
                }
                throw new Error(errorMessage);
            }

            const blob = await response.blob();

            const disposition = response.headers.get("Content-Disposition") || "";
            let filename = "film_results.xlsx";

            const filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
            if (filenameMatch && filenameMatch[1]) {
                filename = decodeURIComponent(filenameMatch[1].replace(/"/g, ""));
            }

            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = downloadUrl;
            link.download = filename;

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error("Error performing film search:", error);
            alert(`Error performing film search: ${error.message}`);
        } finally {
            this.hideHourglass();
        }
    }
}

customElements.define("film-search", FilmSearchComponent);