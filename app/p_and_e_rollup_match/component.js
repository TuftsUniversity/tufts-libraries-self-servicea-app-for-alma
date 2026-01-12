// Minimal wrapper; shared logic lives in /components/parent_component.js
// Make sure parent_component.js is loaded before this file.
class FileDownloader extends window.BaseUploaderComponent {
  constructor() {
    super({
      toolPath: "p_and_e",
      apiPath: "/p_and_e/upload",
      downloadFilename: "rollup_files.zip"
    });
  }
}

customElements.define('file-downloader', FileDownloader);
