class GiftFundBibliography extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this.baseUrl = this.getAttribute('base-url');
        this.token = this.getAttribute('data-token');

        if (!this.baseUrl) {
            console.error("Missing 'base-url' attribute!");
            return;
        }

        if (!this.token) {
            console.warn("No data-token attribute provided.");
            this.shadowRoot.innerHTML = `
            <style>
                .error { color: red; font-weight: bold; }
            </style>
            <p class="error">Access denied: no token provided.</p>
        `;
        return;
        }

        this.apiUrl = `${this.baseUrl}/gift_fund_bibliography/process`;
        this.templateUrl = `${this.baseUrl}/gift_fund_bibliography/component-template`;

        
        this.loadTemplate();
    }

    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl, { method: 'GET' });
            if (!response.ok) throw new Error("Failed to load template");

            const html = await response.text();
            const templateWrapper = document.createElement("div");
            templateWrapper.innerHTML = html.trim();

            const template = templateWrapper.querySelector("template");
            if (template) {
                this.shadowRoot.appendChild(template.content.cloneNode(true));
                await this.injectStyles();
                this.injectHourglass();
                this.attachEventListeners();
            } else {
                console.error("No <template> tag found in loaded HTML.");
            }
        } catch (error) {
            console.error("Error loading template:", error);
        }
    }

    async injectStyles() {
        try {
            const cssUrl = `${this.baseUrl}/static/styles.css`;
            const cssResponse = await fetch(cssUrl);
            if (!cssResponse.ok) throw new Error("Failed to load CSS");

            const cssText = await cssResponse.text();
            const styleTag = document.createElement("style");
            styleTag.textContent = cssText;
            this.shadowRoot.appendChild(styleTag);
        } catch (error) {
            console.error("Error injecting styles into shadow DOM:", error);
        }
    }

    injectHourglass() {
        const hourglassWrapper = document.createElement("div");
        hourglassWrapper.innerHTML = `
            <div id="hourglass" style="display: none;">
                <div class="spinner"></div>
            </div>
        `;
        this.shadowRoot.appendChild(hourglassWrapper);
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
        const uploadForm = this.shadowRoot.getElementById("uploadForm");
        if (uploadForm) {
            uploadForm.action = this.apiUrl;
            uploadForm.addEventListener("submit", (event) => this.handleFormSubmit(event));
        } else {
            console.error("Upload form not found in template.");
        }
    }

    async handleFormSubmit(event) {
        event.preventDefault();
        this.showHourglass();

        const form = event.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                headers: {
                    ...(this.token ? { 'Authorization': `Bearer ${this.token}` } : {})
                },
                body: formData
            });

            if (!response.ok) throw new Error("Upload failed");

            const blob = await response.blob();
            const link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = "gift_fund_biblophraphy.zip";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            console.error("Error during file upload or download:", error);
        } finally {
            this.hideHourglass();
        }
    }
}

customElements.define('gift-fund-bibliography', GiftFundBibliography);