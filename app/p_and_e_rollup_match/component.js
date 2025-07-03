class FileDownloader extends HTMLElement {
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
        }

        this.apiUrl = `${this.baseUrl}/p_and_e/upload`;
        this.templateUrl = `${this.baseUrl}/p_and_e/component-template`;

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
                this.attachEventListeners();
            } else {
                console.error("No <template> tag found in loaded HTML.");
            }
        } catch (error) {
            console.error("Error loading template:", error);
        }
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
            link.download = "rollup_files.zip";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            console.error("Error during file upload or download:", error);
        }
    }
}

customElements.define('file-downloader', FileDownloader);
