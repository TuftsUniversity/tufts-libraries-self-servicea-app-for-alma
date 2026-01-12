// Minimal wrapper; shared logic lives in /components/parent_component.js
// Make sure parent_component.js is loaded before this file.
class SQLGenerator extends window.BaseUploaderComponent {
  constructor() {
    super({
      toolPath: "sql",
      apiPath: "/sql/process_sql",
      downloadFilename: "gift_fund_biblophraphy.zip"
    });
  }
}

customElements.define('alma-analytics-sql-generator', SQLGenerator);
