class FileDownloader extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });

        this.apiUrl = this.getAttribute("api-url") || "https://tufts-libraries-alma-self-service-stage-app.$
        this.templateUrl = "https://tufts-libraries-alma-self-service-stage-app.library.tufts.edu/p_and_e/c$

        this.loadTemplate();
    }

    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl, { method: 'GET' });
            if (!response.ok) throw new Error("Failed to load template");

            const html = await response.text();
            const templateWrapper = document.createElement("div");
            templateWrapper.innerHTML = html.trim(); // Convert HTML string into DOM elements
                                             [ Wrote 62 lines ]

-bash-4.2$ cat component.js 
class FileDownloader extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });

        this.apiUrl = this.getAttribute("api-url") || "https://tufts-libraries-alma-self-service-stage-app.library.tufts.edu/p_and_e/upload";
        this.templateUrl = "https://tufts-libraries-alma-self-service-stage-app.library.tufts.edu/p_and_e/component-template"; // External template URL

        this.loadTemplate();
    }

    async loadTemplate() {
        try {
            const response = await fetch(this.templateUrl, { method: 'GET' });
            if (!response.ok) throw new Error("Failed to load template");

            const html = await response.text();
            const templateWrapper = document.createElement("div");
            templateWrapper.innerHTML = html.trim(); // Convert HTML string into DOM elements

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
        const downloadBtn = this.shadowRoot.getElementById("downloadBtn");
        if (downloadBtn) {
            downloadBtn.addEventListener("click", () => this.downloadFile());
        } else {
            console.error("Download button not found in template.");
        }
    }

    async downloadFile() {
        try {
            const response = await fetch(this.apiUrl, { method: 'GET' });
            if (!response.ok) throw new Error("Failed to download file");

            const text = await response.text();
            const fileContent = this.shadowRoot.getElementById("fileContent");
            if (fileContent) {
                fileContent.textContent = text;
            } else {
                console.error("File content area not found in template.");
            }
        } catch (error) {
            console.error("Error fetching file:", error);
        }
    }
}

// Define the web component
customElements.define('file-downloader', FileDownloader);