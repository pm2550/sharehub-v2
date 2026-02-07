(function () {
  function setOpen(id, open) {
    var node = document.getElementById(id);
    if (!node) return;
    if (node.tagName && node.tagName.toLowerCase() === "dialog" && typeof node.showModal === "function") {
      if (open) {
        if (!node.open) node.showModal();
      } else if (node.open) {
        node.close();
      }
      return;
    }
    node.classList.toggle("on", open);
    node.setAttribute("aria-hidden", open ? "false" : "true");
  }

  document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setOpen(btn.getAttribute("data-modal-open"), true);
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setOpen(btn.getAttribute("data-modal-close"), false);
    });
  });

  document.querySelectorAll("dialog.quick-upload-dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (ev) {
      var rect = dialog.getBoundingClientRect();
      var inDialog =
        rect.top <= ev.clientY &&
        ev.clientY <= rect.top + rect.height &&
        rect.left <= ev.clientX &&
        ev.clientX <= rect.left + rect.width;
      if (!inDialog) dialog.close();
    });
  });

  document.querySelectorAll(".modal-backdrop").forEach(function (backdrop) {
    backdrop.addEventListener("click", function (ev) {
      if (ev.target === backdrop) setOpen(backdrop.id, false);
    });
  });
})();
