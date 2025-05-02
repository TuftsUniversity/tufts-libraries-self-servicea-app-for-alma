class FileDownloader extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this.baseUrl = this.getAttribute('base-url');
        if (!this.baseUrl) {
            console.error("Missing 'base-url' attribute!");
            return;
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
                console.error("No <template> tag found in the loaded HTML.");
            }
        } catch (error) {
            console.error("Error loading template:", error);
        }
    }

    attachEventListeners() {
        const uploadForm = this.shadowRoot.getElementById("uploadForm");
        if (uploadForm) {
            uploadForm.addEventListener("submit", (event) => this.handleFormSubmit(event));
        } else {
            console.error("Upload form not found in template.");
        }
    }

    async handleFormSubmit(event) {
        event.preventDefault(); // prevent page reload

        const form = event.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(this.apiUrl, {
                method: "POST",
                body: formData
            });

            if (!response.ok) throw new Error("Upload failed");

            const resultDiv = this.shadowRoot.getElementById("uploadResult");
            resultDiv.textContent = "Upload successful!";
        } catch (error) {
            console.error("Error uploading file:", error);

            const resultDiv = this.shadowRoot.getElementById("uploadResult");
            resultDiv.textContent = "Upload failed. Please try again.";
        }
    }
}

customElements.define('file-downloader', FileDownloader);

