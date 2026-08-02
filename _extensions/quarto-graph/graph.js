/* Interactive link graph (Obsidian-style graph view).
 *
 * Reads graph.json (emitted by the resolver) and renders:
 *   - one full-graph widget per {{< quarto-graph-full >}} shortcode call
 *     (".quarto-graph-full" elements), each independently sized/filtered
 *     via its own data-* attributes (see full-graph.lua)
 *   - a local N-hop mini graph at the top of the right sidebar on every
 *     page that appears in the graph (N from the page's resolved
 *     `quarto-graph: sidebar: depth:` config, default 1) unless the sidebar
 *     is explicitly disabled via `quarto-graph: sidebar: false`
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
    var fulls = document.querySelectorAll(".quarto-graph-full");
    // The Lua filter stamps this meta tag only on pages with the sidebar
    // panel turned off (see filter.lua). Checked before the fetch, not
    // after, so a disabled page skips downloading and parsing graph.json
    // entirely instead of throwing the work away once it's already here.
    if (!fulls.length && document.querySelector('meta[name="quarto-graph-sidebar"][content="false"]')) {
      return;
    }
    fetch(base + "graph.json")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.nodes || !data.nodes.length) return;
        for (var i = 0; i < fulls.length; i++) mountFullGraph(fulls[i], data);
        // The mini-panel is independent of any full-graph widget on the
        // page -- both render together unless the sidebar is explicitly
        // disabled (checked here, not just at the pre-fetch short-circuit
        // above, since that one only fires when there's no full widget
        // either).
        if (!document.querySelector('meta[name="quarto-graph-sidebar"][content="false"]')) {
          var depthMeta = document.querySelector('meta[name="quarto-graph-sidebar-depth"]');
          var depth = depthMeta ? Math.max(1, parseInt(depthMeta.content, 10) || 1) : 1;
          mountLocalPanel(data, findCurrent(data), depth);
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

  function findByRel(data, rel) {
    for (var i = 0; i < data.nodes.length; i++) {
      if (data.nodes[i].rel === rel) return i;
    }
    return -1;
  }

  // Generalizes the mini-panel's original 1-hop-only subgraph build to N
  // hops: BFS out from startIdx, keeping every node reached within `depth`
  // edges, remapped to a dense 0..k index space the way initGraph expects.
  // Adjacency list built once per call so each BFS level is O(frontier
  // degree) instead of rescanning every edge in data.edges.
  function bfsSubgraph(data, startIdx, depth) {
    var adj = {};
    data.edges.forEach(function (e) {
      (adj[e[0]] || (adj[e[0]] = [])).push(e[1]);
      (adj[e[1]] || (adj[e[1]] = [])).push(e[0]);
    });
    var keep = {};
    keep[startIdx] = true;
    var frontier = [startIdx];
    for (var d = 0; d < depth && frontier.length; d++) {
      var next = [];
      frontier.forEach(function (idx) {
        (adj[idx] || []).forEach(function (n) {
          if (!keep[n]) { keep[n] = true; next.push(n); }
        });
      });
      frontier = next;
    }
    var ids = Object.keys(keep).map(Number);
    var remap = {};
    ids.forEach(function (v, k) { remap[v] = k; });
    return {
      data: {
        nodes: ids.map(function (v) { return data.nodes[v]; }),
        edges: data.edges
          .filter(function (e) { return remap[e[0]] != null && remap[e[1]] != null; })
          .map(function (e) { return [remap[e[0]], remap[e[1]]]; }),
      },
      focus: remap[startIdx],
    };
  }

  // Shared by mountFullGraph's fullscreen toggle and mountLocalPanel's
  // expand button: same expand-arrows icon, same aria-label/title/click
  // shape, only the className and click handler differ per caller.
  function makeExpandButton(className, label, onClick) {
    var btn = document.createElement("button");
    btn.className = className;
    btn.type = "button";
    btn.setAttribute("aria-label", label);
    btn.title = label;
    btn.innerHTML =
      '<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M6 2H2v4M10 2h4v4M6 14H2v-4M10 14h4v-4"/></svg>';
    btn.addEventListener("click", onClick);
    return btn;
  }

  // Mounts a single {{< quarto-graph-full >}} instance per its own data-*
  // attributes (see full-graph.lua): data-width/data-height as raw CSS
  // lengths on the container, data-depth+data-root for an N-hop subgraph
  // centered on an explicit root (defaulting to the current page), and
  // data-expandable="true" for a fullscreen-toggle button.
  function mountFullGraph(el, data) {
    var ds = el.dataset;
    if (ds.width) el.style.width = ds.width;

    var height;
    if (ds.height) {
      el.style.height = ds.height;
      height = el.clientHeight || 420;
    } else {
      height = Math.max(420, Math.round(window.innerHeight * 0.65));
    }

    var graphData = data;
    var focus;
    var label = "Graph";
    if (ds.depth) {
      var depth = Math.max(1, parseInt(ds.depth, 10) || 1);
      var center = ds.root ? findByRel(data, ds.root) : findCurrent(data);
      if (center === -1) return; // resolved root/current page isn't a graph node: nothing to show
      var sub = bfsSubgraph(data, center, depth);
      graphData = sub.data;
      focus = sub.focus;
      label = "Local graph · " + data.nodes[center].title;
    } else {
      focus = findCurrent(data);
    }

    initGraph(el, graphData, { height: height, focus: focus });

    if (ds.expandable === "true") {
      el.appendChild(makeExpandButton("quarto-graph-full__expand", "Expand graph to fullscreen", function () {
        openGraphModal(graphData, focus, label, { big: true });
      }));
    }
  }

  // mkdocs-material uses .md-sidebar--secondary; Quarto's default website/
  // book right margin (toc: true) uses #quarto-margin-sidebar. Try both so
  // the same script drops into either theme unmodified.
  var SIDEBAR_SELECTORS = [
    ".md-sidebar--secondary .md-sidebar__scrollwrap",
    "#quarto-margin-sidebar",
  ];

  function mountLocalPanel(data, cur, depth) {
    if (cur === -1) return;
    var wrap = null;
    for (var s = 0; s < SIDEBAR_SELECTORS.length; s++) {
      wrap = document.querySelector(SIDEBAR_SELECTORS[s]);
      if (wrap) break;
    }
    if (!wrap) return;

    var sub = bfsSubgraph(data, cur, depth);
    if (sub.data.nodes.length < 2) return; // isolated page: nothing to show

    var panel = document.createElement("div");
    panel.className = "quarto-graph-panel";
    var head = document.createElement("div");
    head.className = "quarto-graph-panel__head";
    var title = document.createElement("a");
    title.className = "quarto-graph-panel__title";
    title.textContent = "Graph";
    title.href = new URL(data.graphUrl || "graph.html", base).href;
    title.title = "Open the full graph";
    var expand = makeExpandButton("quarto-graph-panel__expand", "Expand local graph", function () {
      openGraphModal(sub.data, sub.focus, "Local graph · " + data.nodes[cur].title);
    });
    head.appendChild(title);
    head.appendChild(expand);
    panel.appendChild(head);
    var box = document.createElement("div");
    panel.appendChild(box);
    wrap.insertBefore(panel, wrap.firstChild);

    initGraph(box, sub.data, {
      height: 170,
      focus: sub.focus,
      mini: true,
    });
  }

  /* Enlarged graph in a modal — full pan/zoom and click-to-open. Used by
   * the mini-panel's expand button (small box) and the full widget's
   * fullscreen toggle (opts.big, near-fullscreen box). Closes on x,
   * Escape, backdrop. */
  function openGraphModal(data, focus, label, opts) {
    opts = opts || {};
    if (document.querySelector(".quarto-graph-modal")) return;
    var overlay = document.createElement("div");
    overlay.className = "quarto-graph-modal";
    var box = document.createElement("div");
    box.className = "quarto-graph-modal__box" + (opts.big ? " quarto-graph-modal__box--full" : "");
    var head = document.createElement("div");
    head.className = "quarto-graph-modal__head";
    var labelEl = document.createElement("span");
    labelEl.className = "quarto-graph-modal__title";
    labelEl.textContent = label;
    var close = document.createElement("button");
    close.className = "quarto-graph-modal__close";
    close.setAttribute("aria-label", "Close graph");
    close.textContent = "×";
    head.appendChild(labelEl);
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

    initGraph(body, data, {
      height: opts.big ? Math.round(window.innerHeight * 0.86) : Math.min(560, Math.round(window.innerHeight * 0.62)),
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
