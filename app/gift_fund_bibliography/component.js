// Minimal wrapper; shared logic lives in /components/parent_component.js
// Make sure parent_component.js is loaded before this file.
class GiftFundBibliography extends window.BaseUploaderComponent {
  constructor() {
    super({
      toolPath: "gift_fund_bibliography",
      apiPath: "/gift_fund_bibliography/process",
      downloadFilename: "gift_fund_biblophraphy.zip"
    });
  }
}

customElements.define('gift-fund-bibliography', GiftFundBibliography);
