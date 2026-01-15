// Minimal wrapper; shared logic lives in /components/parent_component.js
// Make sure parent_component.js is loaded before this file.
class Bib2Holdings541Processor extends window.BaseUploaderComponent {
  constructor() {
    super({
      toolPath: "bib_2_holdings_541",
      apiPath: "/bib_2_holdings_541/upload",
      downloadFilename: ""
    });
  }
}

customElements.define('bib-2-holdings-541-processor', Bib2Holdings541Processor);
