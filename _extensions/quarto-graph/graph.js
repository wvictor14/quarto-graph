/* Interactive link graph (Obsidian-style graph view).
 *
 * Reads graph.json (emitted by the resolver) and renders:
 *   - the full graph into #quarto-graph-full on the generated /graph/ page
 *   - a local 1-hop mini graph at the top of the right sidebar on every
 *     other page that appears in the graph
 *
 * Self-contained vanilla JS + canvas: no external requests, works under any
 * path prefix (base URL is derived from this script's own src).
 */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;
  // Quarto's HTML-dependency mechanism (see filter.lua) writes this script's
  // src as a page-depth-correct relative path, e.g. "graph.js" at the site
  // root, "../site_libs/.../graph.js" one directory down, and so on — the
  // exact internal path is a Quarto implementation detail (and even
  // contains this extension's own version string), so don't hardcode it.
  // Count the leading "../"s instead: that count IS the page's depth below
  // the site root, which is what we actually need.
  var rawSrc = script.getAttribute("src") || "";
  var depth = 0;
  while (rawSrc.indexOf("../") === 0) {
    depth++;
    rawSrc = rawSrc.slice(3);
  }
  var base = new URL(depth > 0 ? new Array(depth + 1).join("../") : ".", location.href).href;

  var TYPE_COLORS = {
    concept: "#3ba29f",
    person: "#9177b6",
    reference: "#d65527",
    project: "#6b0021",
    experiment: "#c9a227",
    moc: "#8fa6d9",
  };
  var DEFAULT_COLOR = "#9aa0a6";

  function isDark() {
    return document.body.classList.contains("quarto-dark");
  }
  function linkColor() {
    return isDark() ? "rgba(210, 160, 170, 0.25)" : "rgba(107, 0, 33, 0.18)";
  }
  function linkHiColor() {
    return isDark() ? "rgba(230, 190, 200, 0.7)" : "rgba(107, 0, 33, 0.6)";
  }
  function labelColor() {
    return isDark() ? "#d8dae0" : "#40434a";
  }
  function focusColor() {
    return isDark() ? "#e6a5b3" : "#6b0021";
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    fetch(base + "graph.json")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.nodes || !data.nodes.length) return;
        var full = document.getElementById("quarto-graph-full");
        if (full) {
          initGraph(full, data, {
            height: Math.max(420, Math.round(window.innerHeight * 0.65)),
            focus: findCurrent(data),
          });
        } else {
          mountLocalPanel(data, findCurrent(data));
        }
      })
      .catch(function () { /* graph is progressive enhancement only */ });
  });

  function findCurrent(data) {
    var here = location.pathname.replace(/index\.html$/, "");
    for (var i = 0; i < data.nodes.length; i++) {
      if (new URL(data.nodes[i].url, base).pathname === here) return i;
    }
    return -1;
  }

  // mkdocs-material uses .md-sidebar--secondary; Quarto's default website/
  // book right margin (toc: true) uses #quarto-margin-sidebar. Try both so
  // the same script drops into either theme unmodified.
  var SIDEBAR_SELECTORS = [
    ".md-sidebar--secondary .md-sidebar__scrollwrap",
    "#quarto-margin-sidebar",
  ];

  function mountLocalPanel(data, cur) {
    if (cur === -1) return;
    var wrap = null;
    for (var s = 0; s < SIDEBAR_SELECTORS.length; s++) {
      wrap = document.querySelector(SIDEBAR_SELECTORS[s]);
      if (wrap) break;
    }
    if (!wrap) return;

    var keep = {};
    keep[cur] = true;
    data.edges.forEach(function (e) {
      if (e[0] === cur) keep[e[1]] = true;
      if (e[1] === cur) keep[e[0]] = true;
    });
    var ids = Object.keys(keep).map(Number);
    if (ids.length < 2) return; // isolated page: nothing to show

    var remap = {};
    ids.forEach(function (v, k) { remap[v] = k; });
    var sub = {
      nodes: ids.map(function (v) { return data.nodes[v]; }),
      edges: data.edges
        .filter(function (e) { return remap[e[0]] != null && remap[e[1]] != null; })
        .map(function (e) { return [remap[e[0]], remap[e[1]]]; }),
    };

    var panel = document.createElement("div");
    panel.className = "quarto-graph-panel";
    var head = document.createElement("div");
    head.className = "quarto-graph-panel__head";
    var title = document.createElement("a");
    title.className = "quarto-graph-panel__title";
    title.textContent = "Graph";
    title.href = new URL(data.graphUrl || "graph.html", base).href;
    title.title = "Open the full graph";
    var expand = document.createElement("button");
    expand.className = "quarto-graph-panel__expand";
    expand.type = "button";
    expand.setAttribute("aria-label", "Expand local graph");
    expand.title = "Expand local graph";
    expand.innerHTML =
      '<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M6 2H2v4M10 2h4v4M6 14H2v-4M10 14h4v-4"/></svg>';
    expand.addEventListener("click", function () {
      openLocalPopup(sub, remap[cur], data.nodes[cur].title);
    });
    head.appendChild(title);
    head.appendChild(expand);
    panel.appendChild(head);
    var box = document.createElement("div");
    panel.appendChild(box);
    wrap.insertBefore(panel, wrap.firstChild);

    initGraph(box, sub, {
      height: 170,
      focus: remap[cur],
      mini: true,
    });
  }

  /* Enlarged local graph in a modal — same 1-hop subgraph as the panel,
   * with full pan/zoom and click-to-open. Closes on x, Escape, backdrop. */
  function openLocalPopup(sub, focus, title) {
    if (document.querySelector(".quarto-graph-modal")) return;
    var overlay = document.createElement("div");
    overlay.className = "quarto-graph-modal";
    var box = document.createElement("div");
    box.className = "quarto-graph-modal__box";
    var head = document.createElement("div");
    head.className = "quarto-graph-modal__head";
    var label = document.createElement("span");
    label.className = "quarto-graph-modal__title";
    label.textContent = "Local graph · " + title;
    var close = document.createElement("button");
    close.className = "quarto-graph-modal__close";
    close.setAttribute("aria-label", "Close graph");
    close.textContent = "×";
    head.appendChild(label);
    head.appendChild(close);
    var body = document.createElement("div");
    box.appendChild(head);
    box.appendChild(body);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    function destroy() {
      document.removeEventListener("keydown", onKey);
      overlay.remove(); // disconnects the canvas; its sim loop exits itself
    }
    function onKey(ev) {
      if (ev.key === "Escape") destroy();
    }
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("pointerdown", function (ev) {
      if (ev.target === overlay) destroy();
    });
    close.addEventListener("click", destroy);

    initGraph(body, sub, {
      height: Math.min(560, Math.round(window.innerHeight * 0.62)),
      focus: focus,
    });
    close.focus();
  }

  function initGraph(container, data, opts) {
    var N = data.nodes.length;
    var H = opts.height;
    var dpr = window.devicePixelRatio || 1;
    var canvas = document.createElement("canvas");
    canvas.className = "quarto-graph-canvas";
    canvas.style.height = H + "px";
    container.appendChild(canvas);
    var ctx = canvas.getContext("2d");
    var W = 0;

    function resize() {
      if (!canvas.isConnected) {
        window.removeEventListener("resize", resize);
        return;
      }
      W = container.clientWidth || 300;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      draw();
    }
    window.addEventListener("resize", resize);

    // --- simulation state ------------------------------------------------
    var nodes = data.nodes.map(function (n, i) {
      var a = (2 * Math.PI * i) / N;
      var r = 40 + 14 * Math.sqrt(N) * ((i % 7) / 7 + 0.4);
      return { x: Math.cos(a) * r, y: Math.sin(a) * r, vx: 0, vy: 0, deg: 0, d: n };
    });
    data.edges.forEach(function (e) {
      nodes[e[0]].deg++;
      nodes[e[1]].deg++;
    });
    var view = { x: 0, y: 0, k: opts.mini ? 0.5 : 0.9 };
    var alpha = 1;
    var hover = -1;
    var drag = null;   // {node, moved}
    var pan = null;    // {x, y, vx, vy}
    var spring = opts.mini ? 60 : 110;

    function tick() {
      var i, j, a, b, dx, dy, d2, d, f;
      for (i = 0; i < N; i++) {
        for (j = i + 1; j < N; j++) {
          a = nodes[i]; b = nodes[j];
          dx = b.x - a.x; dy = b.y - a.y;
          d2 = dx * dx + dy * dy + 0.01;
          d = Math.sqrt(d2);
          f = 3200 / d2;
          a.vx -= (dx / d) * f; a.vy -= (dy / d) * f;
          b.vx += (dx / d) * f; b.vy += (dy / d) * f;
        }
      }
      data.edges.forEach(function (e) {
        a = nodes[e[0]]; b = nodes[e[1]];
        dx = b.x - a.x; dy = b.y - a.y;
        d = Math.sqrt(dx * dx + dy * dy) + 0.01;
        f = (d - spring) * 0.02;
        a.vx += (dx / d) * f; a.vy += (dy / d) * f;
        b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
      });
      nodes.forEach(function (n) {
        n.vx -= n.x * 0.0022;  // gentle gravity to the center
        n.vy -= n.y * 0.0022;
        if (drag && n === drag.node) { n.vx = 0; n.vy = 0; return; }
        n.vx *= 0.85; n.vy *= 0.85;
        n.x += n.vx * alpha;
        n.y += n.vy * alpha;
      });
      alpha *= 0.99;
    }

    function radius(n) {
      return (3.2 + Math.min(9, n.deg * 0.9)) * (opts.mini ? 0.75 : 1);
    }
    function toScreen(n) {
      return { x: W / 2 + (n.x + view.x) * view.k, y: H / 2 + (n.y + view.y) * view.k };
    }
    function neighbors(idx) {
      var set = {};
      data.edges.forEach(function (e) {
        if (e[0] === idx) set[e[1]] = true;
        if (e[1] === idx) set[e[0]] = true;
      });
      return set;
    }

    function draw() {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      var hi = hover !== -1 ? neighbors(hover) : null;

      data.edges.forEach(function (e) {
        var s = toScreen(nodes[e[0]]);
        var t = toScreen(nodes[e[1]]);
        var lit = hover !== -1 && (e[0] === hover || e[1] === hover);
        ctx.strokeStyle = lit ? linkHiColor() : linkColor();
        ctx.lineWidth = lit ? 1.4 : 1;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.stroke();
      });

      var showLabels = N <= 40 || view.k > 1.3;
      nodes.forEach(function (n, i) {
        var p = toScreen(n);
        var r = radius(n);
        var dim = hover !== -1 && i !== hover && !(hi && hi[i]);
        ctx.globalAlpha = dim ? 0.25 : 1;
        ctx.fillStyle = TYPE_COLORS[n.d.type] || DEFAULT_COLOR;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
        ctx.fill();
        if (i === opts.focus) {
          ctx.strokeStyle = focusColor();
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r + 2.5, 0, 2 * Math.PI);
          ctx.stroke();
        }
        if ((showLabels && !dim) || i === hover) {
          ctx.font = (opts.mini ? "9px " : "11px ") + "'Overpass Mono', monospace";
          ctx.fillStyle = labelColor();
          ctx.textAlign = "center";
          ctx.fillText(n.d.title, p.x, p.y + r + (opts.mini ? 9 : 12));
        }
        ctx.globalAlpha = 1;
      });
    }

    // The simulation settles and STOPS (alpha decays below threshold); any
    // interaction reheats it via kick(). No perpetual O(N^2) rAF loop.
    var ALPHA_STOP = 0.02;
    var running = false;
    function loop() {
      tick();
      draw();
      if (!canvas.isConnected || (alpha < ALPHA_STOP && !drag && !pan)) {
        running = false;
        return;
      }
      requestAnimationFrame(loop);
    }
    function kick(heat) {
      alpha = Math.max(alpha, heat);
      if (!running && !reduced) {
        running = true;
        requestAnimationFrame(loop);
      }
    }
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      for (var s = 0; s < 400; s++) tick();
      resize();
    } else {
      resize();
      kick(1);
    }

    // --- interactions -----------------------------------------------------
    function pick(ev) {
      var rect = canvas.getBoundingClientRect();
      var mx = ev.clientX - rect.left;
      var my = ev.clientY - rect.top;
      for (var i = N - 1; i >= 0; i--) {
        var p = toScreen(nodes[i]);
        var dx = p.x - mx, dy = p.y - my;
        if (dx * dx + dy * dy <= Math.pow(radius(nodes[i]) + 4, 2)) return i;
      }
      return -1;
    }

    canvas.addEventListener("pointerdown", function (ev) {
      var i = pick(ev);
      if (i !== -1) {
        drag = { node: nodes[i], moved: false, idx: i };
        kick(0.5);
      } else {
        pan = { x: ev.clientX, y: ev.clientY };
      }
      try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* synthetic events */ }
    });
    canvas.addEventListener("pointermove", function (ev) {
      if (drag) {
        drag.moved = true;
        drag.node.x += ev.movementX / view.k;
        drag.node.y += ev.movementY / view.k;
        kick(0.3);
      } else if (pan) {
        view.x += (ev.clientX - pan.x) / view.k;
        view.y += (ev.clientY - pan.y) / view.k;
        pan = { x: ev.clientX, y: ev.clientY };
      } else {
        var i = pick(ev);
        if (i !== hover) {
          hover = i;
          canvas.style.cursor = i === -1 ? "default" : "pointer";
        }
      }
      if (!running) draw();
    });
    canvas.addEventListener("pointerup", function () {
      if (drag && !drag.moved && drag.idx !== opts.focus) {
        location.href = new URL(nodes[drag.idx].d.url, base).href;
      }
      drag = null;
      pan = null;
    });
    canvas.addEventListener("pointerleave", function () { hover = -1; if (!running) draw(); });
    canvas.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      var k = Math.min(4, Math.max(0.25, view.k * (ev.deltaY < 0 ? 1.12 : 0.89)));
      view.k = k;
      if (!running) draw();
    }, { passive: false });
  }
})();
