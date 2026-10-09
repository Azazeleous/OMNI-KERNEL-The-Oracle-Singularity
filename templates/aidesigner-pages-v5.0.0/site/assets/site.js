"use strict";
const copyButton = document.querySelector("#copy-brief");
const brief = document.querySelector("#design-brief");
const status = document.querySelector("#copy-status");
if (copyButton && brief && status) {
  copyButton.addEventListener("click", async () => {
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(brief.textContent);
      status.textContent = "Brief copied. Adapt the bracketed fields to your offer.";
    } catch {
      status.textContent = "Select the brief above and copy it manually.";
    }
  });
}
