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
                console.error("No <template> tag found in loaded HTML.");
            }
        } catch (error) {
            console.error("Error loading template:", error);
        }
    }

    attachEventListeners() {
        const uploadForm = this.shadowRoot.getElementById("uploadForm");
        if (uploadForm) {
            // Correct the form action dynamically
            uploadForm.action = `${this.baseUrl}/p_and_e/upload`;
    
            uploadForm.addEventListener("submit", (event) => this.handleFormSubmit(event));
        } else {
            console.error("Upload form not found in template.");
        }
    }

    async handleFormSubmit(event) {
        event.preventDefault(); // Stop the form from navigating away

        const form = event.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: formData
            });

            if (!response.ok) throw new Error("Network response was not ok");

            const blob = await response.blob();
            const link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = "rollup_files.zip";  // Default filename
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (error) {
            console.error("Error downloading file:", error);
        }
    }
}

customElements.define('file-downloader', FileDownloader);
