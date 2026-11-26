// Renders the Markdown subset listed in README.md. All text is HTML-escaped first.
var Markdown = (function () {
  function escape(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inline(text) {
    // Code spans are set aside so that their contents are never formatted.
    var codes = [];
    var s = String(text).replace(/\u0000/g, '').replace(/`([^`]+)`/g, function (_, c) {
      codes.push('<code>' + escape(c) + '</code>');
      return '\u0000' + (codes.length - 1) + '\u0000';
    });
    s = escape(s)
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, label, url) {
        return /^https?:\/\//i.test(url) ? '<a href="' + url + '" target="_blank" rel="noopener">' + label + '</a>' : label;
      })
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\s](?:[^*]*[^*\s])?)\*(?!\*)/g, '$1<em>$2</em>');
    return s.replace(/\u0000(\d+)\u0000/g, function (_, i) { return codes[i]; });
  }

  function cells(row) {
    return row.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(function (c) {
      return c.trim().replace(/\\\|/g, '|');
    });
  }

  // "{Easy}" at the end of an interview question is its difficulty, not text to show.
  function withLevel(item) {
    var m = /^(.*?)\s*\{(Easy|Medium|Hard)\}$/.exec(item);
    return m ? inline(m[1]) + ' <span class="pill ' + m[2] + '">' + m[2] + '</span>' : inline(item);
  }

  var HEADING = /^(#{1,6})\s+(.*)$/;
  var ITEM = /^\s*(?:([-*])|(\d+)\.)\s+(.*)$/;
  var FENCE = /^```/;

  function render(source) {
    var lines = source.split('\n');
    var out = [];
    var headings = [];
    var i = 0;
    function startsBlock(l) { return !l.trim() || HEADING.test(l) || ITEM.test(l) || FENCE.test(l) || /^\|/.test(l); }
    while (i < lines.length) {
      var line = lines[i];
      var m;
      if (!line.trim()) { i++; continue; }
      if (FENCE.test(line)) {
        var code = [];
        for (i++; i < lines.length && !FENCE.test(lines[i]); i++) code.push(lines[i]);
        i++;
        out.push('<pre tabindex="0"><code>' + escape(code.join('\n')) + '</code></pre>');
      } else if ((m = HEADING.exec(line))) {
        var level = m[1].length;
        var id = 's' + headings.length;
        headings.push({ id: id, level: level, text: m[2] });
        out.push('<h' + level + ' id="' + id + '">' + inline(m[2]) + '</h' + level + '>');
        i++;
      } else if (/^\|/.test(line)) {
        var rows = [];
        while (i < lines.length && /^\|/.test(lines[i])) rows.push(cells(lines[i++]));
        var body = rows.slice(2).map(function (r) {
          return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>';
        }).join('');
        out.push('<div class="table" tabindex="0"><table><thead><tr>' + rows[0].map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') + '</tr></thead><tbody>' + body + '</tbody></table></div>');
      } else if ((m = ITEM.exec(line))) {
        var ordered = !!m[2];
        var start = m[2];
        var items = [];
        while (i < lines.length && (m = ITEM.exec(lines[i])) && !!m[2] === ordered) {
          var item = m[3];
          for (i++; i < lines.length && /^\s+\S/.test(lines[i]) && !ITEM.test(lines[i]); i++) item += ' ' + lines[i].trim();
          var task = /^\[( |x|X)\]\s+(.*)$/.exec(item);
          items.push(task
            ? '<li class="task"><input type="checkbox" disabled' + (task[1] === ' ' ? '' : ' checked') + ' aria-label="Checklist item"> ' + inline(task[2]) + '</li>'
            : '<li>' + withLevel(item) + '</li>');
        }
        var tag = ordered ? 'ol' : 'ul';
        out.push('<' + tag + (ordered && start !== '1' ? ' start="' + start + '"' : '') + '>' + items.join('') + '</' + tag + '>');
      } else {
        var para = [line];
        for (i++; i < lines.length && !startsBlock(lines[i]); i++) para.push(lines[i]);
        out.push('<p>' + inline(para.join(' ')) + '</p>');
      }
    }
    return { html: out.join('\n'), headings: headings };
  }

  return { render: render, inline: inline, escape: escape };
})();

if (typeof module !== 'undefined') module.exports = Markdown;
