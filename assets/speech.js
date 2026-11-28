// "Read aloud" with the browser's own speech engine. Nothing is sent by this site.
var Speech = (function () {
  var synth = typeof window !== 'undefined' && window.speechSynthesis;
  var supported = !!synth && typeof window.SpeechSynthesisUtterance === 'function';
  // Code blocks are left out: read character by character they make no sense.
  var BLOCKS = 'h1,h2,h3,h4,p,li,tr,.eyebrow,.option';
  var SKIP = 'pre,.pill,.no-read';
  var LIMIT = 200;
  var session = 0, active = null, current = null;

  function textOf(el) {
    if (el.matches('.option')) return el.querySelector('b').textContent + '. ' + el.querySelector('span').textContent;
    if (el.matches('tr')) return Array.prototype.map.call(el.children, function (c) { return c.textContent.trim(); }).join(', ');
    var copy = el.cloneNode(true);
    copy.querySelectorAll(SKIP).forEach(function (n) { n.remove(); });
    return copy.textContent;
  }

  // Some browsers stop partway through a long utterance, so text goes in short pieces.
  function split(text) {
    var pieces = [];
    text.replace(/\s+/g, ' ').trim().split(/(?<=[.!?])\s+/).forEach(function (sentence) {
      while (sentence.length > LIMIT) {
        var cut = sentence.lastIndexOf(' ', LIMIT);
        if (cut < 1) cut = LIMIT;
        pieces.push(sentence.slice(0, cut));
        sentence = sentence.slice(cut).trim();
      }
      if (!sentence) return;
      // Short ones are joined: the "!!" or "as?" in code doesn't end a sentence.
      var last = pieces.length - 1;
      if (last >= 0 && pieces[last].length + sentence.length < LIMIT) pieces[last] += ' ' + sentence;
      else pieces.push(sentence);
    });
    return pieces;
  }

  function collect(roots) {
    var pieces = [];
    roots.forEach(function (root) {
      var found = root.matches(BLOCKS) ? [root] : Array.prototype.slice.call(root.querySelectorAll(BLOCKS));
      found.forEach(function (el) {
        if (el.closest(SKIP)) return;
        var parts = split(textOf(el));
        // A full stop gives headings and list items a pause of their own.
        if (parts.length && !/[.!?:]$/.test(parts[parts.length - 1])) parts[parts.length - 1] += '.';
        pieces = pieces.concat(parts);
      });
    });
    return pieces;
  }

  function show(button, reading) {
    button.setAttribute('aria-pressed', reading);
    button.textContent = reading ? '■ Stop reading' : idle(button.dataset.label);
  }

  function idle(label) { return (label === 'Play' ? '▶ ' : '🔊 ') + label; }

  // A section runs from its heading up to the next one.
  function section(heading) {
    var parts = [heading];
    for (var el = heading.nextElementSibling; el && !el.matches('h2,h3'); el = el.nextElementSibling) parts.push(el);
    return parts;
  }

  function addSectionButtons(root) {
    if (!supported) return;
    root.querySelectorAll('h3').forEach(function (heading) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn listen play';
      b.dataset.label = 'Play';
      b.dataset.section = heading.id;
      // Tells screen readers which section this button plays.
      b.setAttribute('aria-describedby', heading.id);
      show(b, false);
      heading.after(b);
    });
  }

  function stop() {
    // Cancelling fires events on the old utterance; the new session number ignores them.
    session++;
    if (supported) synth.cancel();
    if (active) show(active, false);
    active = current = null;
  }

  function start(button, pieces) {
    stop();
    if (!pieces.length) return;
    var mine = session, at = 0;
    active = button;
    show(button, true);
    (function next() {
      if (mine !== session) return;
      if (at === pieces.length) return stop();
      // Held in a variable so that it isn't discarded before it finishes.
      current = new SpeechSynthesisUtterance(pieces[at++]);
      current.lang = 'en-US';
      current.onend = next;
      current.onerror = function () { if (mine === session) stop(); };
      synth.speak(current);
    })();
  }

  // `selector` names what to read, in the order it appears on the page.
  function button(label, selector) {
    return supported ? '<button type="button" class="btn listen" data-label="' + label + '" data-read="' + selector + '" aria-pressed="false">🔊 ' + label + '</button>' : '';
  }

  // One listener covers buttons added after the page is drawn.
  function listen(view) {
    if (!supported) return;
    view.addEventListener('click', function (e) {
      var b = e.target.closest('.listen');
      if (!b) return;
      if (b === active) return stop();
      start(b, collect(b.dataset.section ? section(document.getElementById(b.dataset.section)) : view.querySelectorAll(b.dataset.read)));
    });
    window.addEventListener('pagehide', stop);
  }

  return { button: button, addSectionButtons: addSectionButtons, listen: listen, stop: stop };
})();
