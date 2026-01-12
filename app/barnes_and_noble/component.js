// Minimal wrapper; shared logic lives in /components/parent_component.js
// Make sure parent_component.js is loaded before this file.
class BarnesAndNobleFileUploader extends window.BaseUploaderComponent {
  constructor() {
    super({
      toolPath: "barnes_and_noble",
      apiPath: "/barnes_and_noble/upload",
      downloadFilename: "Updated_Barnes_and_Noble.xlsx"
    });
  }
}

customElements.define('barnes-and-noble-file-uploader', BarnesAndNobleFileUploader);
