/**
 * Shared base class for Tufts Libraries Self-Service web components.
 * Centralizes:
 * - baseUrl + token handling
 * - templateUrl + apiUrl construction
 * - template fetch + <template> cloning into shadowRoot
 * - shared CSS injection (styles.css)
 * - hourglass spinner
 * - upload form wiring (id="uploadForm")
 * - token-authenticated POST -> blob download
 * - help icon click interception for links like href="/help#..."
 *
 * Usage:
 *   class MyComp extends BaseUploaderComponent {
 *     constructor() {
 *       super({
 *         toolPath: "sql",
 *         apiPath: "/sql/process_sql",
 *         downloadFilename: "output.zip"
 *       });
 *     }
 *   }
 */
class BaseUploaderComponent extends HTMLElement {
  constructor({ toolPath, apiPath, downloadFilename }) {
    super();
    this.attachShadow({ mode: "open" });

    this.toolPath = toolPath;
    this.apiPath = apiPath;
    this.downloadFilename = downloadFilename;

    this.baseUrl = null;
    this.token = null;

    this.apiUrl = null;
    this.templateUrl = null;
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
        <style>
          .error { color: red; font-weight: bold; }
        </style>
        <p class="error">Access denied: no token provided.</p>
      `;
      return;
    }

    this.apiUrl = `${this.baseUrl}${this.apiPath}`;
    this.templateUrl = `${this.baseUrl}/${this.toolPath}/component-template`;

    this.loadTemplate();
  }

  async loadTemplate() {
    try {
      const response = await fetch(this.templateUrl, { method: "GET" });
      if (!response.ok) throw new Error("Failed to load template");

      const html = await response.text();
      const templateWrapper = document.createElement("div");
      templateWrapper.innerHTML = html.trim();

      const template = templateWrapper.querySelector("template");
      if (template) {
        this.shadowRoot.appendChild(template.content.cloneNode(true));
        await this.injectStyles();
        this.injectHourglass();
        this.attachHelpLinkHandler();
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

attachHelpLinkHandler() {
  const base = (this.baseUrl || "").replace(/\/+$/, "");

  // 1) Rewrite help icon image src to absolute Flask URL
  this.shadowRoot.querySelectorAll("img.help-icon[src]").forEach(img => {
    const src = img.getAttribute("src") || "";

    // Only rewrite root-relative URLs
    if (src.startsWith("/")) {
      img.setAttribute("src", `${base}${src}`);
    }
  });

  // 2) Intercept clicks on help links
  this.shadowRoot.addEventListener(
    "click",
    (e) => {
      const a = e.target?.closest?.("a.help-icon");
      if (!a) return;

      const href = a.getAttribute("href") || "";
      if (!href.startsWith("/help")) return;

      e.preventDefault();
      e.stopPropagation();

      window.open(`${base}${href}`, "_blank", "noopener,noreferrer");
    },
    true
  );
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
      const response = await fetch(this.apiUrl, {
        method: "POST",
        headers: {
          ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        },
        body: formData,
      });


      
      if (!response.ok) throw new Error("Upload failed");

      if (this.downloadFilename != "") {
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = this.downloadFilename || "download.bin";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      }
    } catch (error) {
      console.error("Error during file upload or download:", error);
    } finally {
      this.hideHourglass();
    }
  }

}

// expose globally for non-module <script src="..."> usage
window.BaseUploaderComponent = BaseUploaderComponent;
