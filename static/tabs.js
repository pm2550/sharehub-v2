(function () {
  var groups = document.querySelectorAll("[data-tab-group]");
  groups.forEach(function (group) {
    var buttons = Array.from(group.querySelectorAll("[data-tab]"));
    var panels = Array.from(group.querySelectorAll("[data-panel]"));
    if (!buttons.length || !panels.length) return;

    var defaultTab = group.getAttribute("data-default-tab") || buttons[0].getAttribute("data-tab");
    var fromHash = (window.location.hash || "").replace(/^#/, "");
    var panelNames = new Set(panels.map(function (p) { return p.getAttribute("data-panel"); }));
    var active = panelNames.has(fromHash) ? fromHash : defaultTab;

    function setActive(tabName, writeHash) {
      buttons.forEach(function (btn) {
        var on = btn.getAttribute("data-tab") === tabName;
        btn.classList.toggle("on", on);
      });
      panels.forEach(function (panel) {
        var on = panel.getAttribute("data-panel") === tabName;
        panel.classList.toggle("on", on);
      });
      if (writeHash) window.location.hash = tabName;
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        setActive(btn.getAttribute("data-tab"), true);
      });
    });

    setActive(active, false);
  });
})();
