(function () {
  var view = document.getElementById('view');
  var esc = Markdown.escape;
  var inline = Markdown.inline;
  var topics = [], questions = [], quiz = [], byId = {}, qById = {};

  // Progress stays in this browser only.
  var STORE = 'droidready.v1';
  var state = { learned: {}, learning: {}, saved: {}, days: {}, quiz: { right: 0, total: 0 }, last: null };
  try { Object.assign(state, JSON.parse(localStorage.getItem(STORE)) || {}); } catch (e) {}
  function save() { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} }

  function dayKey(d) { return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); }
  function daysAgo(n) { var d = new Date(); d.setDate(d.getDate() - n); return d; }
  function studied() { var k = dayKey(new Date()); state.days[k] = (state.days[k] || 0) + 1; }
  function streak() {
    var n = state.days[dayKey(new Date())] ? 0 : 1, count = 0;
    while (state.days[dayKey(daysAgo(n++))]) count++;
    return count;
  }

  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return (h >>> 0).toString(36);
  }

  function getText(path) {
    return fetch(path, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(path + ' returned ' + r.status);
      return r.text();
    });
  }

  function load() {
    return getText('index.json').then(JSON.parse).then(function (index) {
      return Promise.all([
        Promise.all(index.topics.map(function (t) { return getText(t.path); })),
        getText(index.quiz.path).then(JSON.parse)
      ]).then(function (res) {
        topics = index.topics.slice().sort(function (a, b) { return a.number - b.number; });
        var source = {};
        index.topics.forEach(function (t, i) { source[t.id] = res[0][i]; });
        topics.forEach(function (t) {
          // The first line is the title, which the page header already shows.
          t.body = source[t.id].replace(/^# .*\n/, '');
          t.questions = Markdown.questions(source[t.id]).map(function (q) {
            q.id = t.id + '-' + hash(q.question);
            q.topic = t;
            qById[q.id] = q;
            questions.push(q);
            return q;
          });
          byId[t.id] = t;
        });
        quiz = res[1].questions;
      });
    });
  }

  function learnedCount(list) { return list.filter(function (q) { return state.learned[q.id]; }).length; }
  function bar(done, total) { return !total ? '' : '<div class="bar"><i style="width:' + Math.round(done / total * 100) + '%"></i></div>'; }
  function pill(level) { return level ? '<span class="pill ' + esc(level) + '">' + esc(level) + '</span>' : ''; }

  function questionList(list, showTopic) {
    return '<ul class="list">' + list.map(function (q) {
      return '<li><a class="item" href="#/question/' + q.id + '">' +
        (showTopic ? '<span class="from">' + esc(q.topic.title) + '</span>' : '') +
        '<span class="title">' + inline(q.question) + '</span>' +
        '<span class="tags">' + pill(q.level) + (state.learned[q.id] ? '<span class="pill Easy">✓ Learned</span>' : '') + '</span></a></li>';
    }).join('') + '</ul>';
  }

  // Each page returns { tab, title, html, wide, bind }.
  function home() {
    var last = byId[state.last] || topics[0];
    var done = learnedCount(last.questions);
    var days = streak();
    return {
      tab: 'home', title: 'Android interview prep', wide: true,
      html: '<div class="stack">' +
        '<div class="row between"><h1>Walk into your Android interview ready.</h1>' + (days ? '<span class="pill Hard">' + days + '-day streak</span>' : '') + '</div>' +
        '<div class="cards2"><a class="card hero" href="#/topic/' + last.id + '"><span class="eyebrow">' + (byId[state.last] ? 'Continue where you left off' : 'Start here') + '</span><span class="display" style="font-size:21px;font-weight:600">' + esc(last.title) + '</span>' +
        bar(done, last.questions.length) + '<span class="meta"><span>' + (last.questions.length ? done + ' of ' + last.questions.length + ' learned' : 'Study notes') + '</span><b>Open →</b></span></a>' +
        '<a class="card" href="#/practice/daily"><h2>Daily 5</h2><p class="muted">Five mixed quiz questions, new every day.</p></a></div>' +
        '<div class="row between"><h2>Topics</h2><span class="muted small">' + topics.length + ' topics · ' + questions.length + ' questions</span></div>' +
        '<div class="grid">' + topics.map(function (t) {
          var d = learnedCount(t.questions);
          return '<a class="card" href="#/topic/' + t.id + '"><b>' + esc(t.title) + '</b><span class="muted small">' + (t.questions.length ? d + ' / ' + t.questions.length + ' learned' : 'Study notes') + '</span>' + bar(d, t.questions.length) + '</a>';
        }).join('') + '</div>' +
        '<footer class="muted small">Your progress is saved in this browser only. <a href="https://github.com/sougandhmp/DroidReady-Content">Content on GitHub</a></footer></div>'
    };
  }

  function topic(id, tab) {
    var t = byId[id];
    if (!t) return missing();
    state.last = id;
    save();
    var asking = tab === 'questions' && t.questions.length;
    var at = topics.indexOf(t);
    var prev = topics[at - 1], next = topics[at + 1];
    var head = '<a href="#/">← All topics</a><h1>' + esc(t.title) + '</h1>' +
      (t.questions.length ? '<div class="row" style="flex-wrap:nowrap"><div style="flex:1">' + bar(learnedCount(t.questions), t.questions.length) + '</div><span class="muted small">' + learnedCount(t.questions) + ' / ' + t.questions.length + ' learned</span></div>' : '') +
      '<div class="row"><a class="chip" href="#/topic/' + id + '"' + (asking ? '' : ' aria-current="page"') + '>Notes</a>' +
      (t.questions.length ? '<a class="chip" href="#/topic/' + id + '/questions"' + (asking ? ' aria-current="page"' : '') + '>Questions (' + t.questions.length + ')</a>' : '') +
      (quiz.some(function (q) { return q.topic === id; }) ? '<a class="chip" href="#/practice/' + id + '">Practice quiz</a>' : '') + '</div>';
    var pager = '<div class="row between">' + (prev ? '<a class="btn" href="#/topic/' + prev.id + '">← Previous</a>' : '<span></span>') + (next ? '<a class="btn" href="#/topic/' + next.id + '">Next topic →</a>' : '') + '</div>';
    var page = { tab: 'home', title: t.title };
    if (asking) {
      page.html = '<div class="stack">' + head + '<div class="row" role="group" aria-label="Filter by difficulty">' +
        ['All', 'Easy', 'Medium', 'Hard'].map(function (l) { return '<button type="button" class="chip" data-level="' + l + '" aria-pressed="' + (l === 'All') + '">' + l + '</button>'; }).join('') +
        '</div><div id="results">' + questionList(t.questions) + '</div></div>';
      page.bind = function () {
        view.querySelectorAll('[data-level]').forEach(function (b) {
          b.onclick = function () {
            view.querySelectorAll('[data-level]').forEach(function (o) { o.setAttribute('aria-pressed', o === b); });
            var list = t.questions.filter(function (q) { return b.dataset.level === 'All' || q.level === b.dataset.level; });
            document.getElementById('results').innerHTML = list.length ? questionList(list) : '<p class="muted">No questions at this level.</p>';
          };
        });
      };
    } else {
      var doc = Markdown.render(t.body);
      var sections = doc.headings.filter(function (h) { return h.level === 3; });
      page.html = '<div class="stack">' + head +
        (sections.length > 1 ? '<details class="card"><summary><b>On this page</b></summary><div class="toc" style="margin-top:12px">' + sections.map(function (h) { return '<button type="button" class="chip" data-jump="' + h.id + '">' + inline(h.text) + '</button>'; }).join('') + '</div></details>' : '') +
        '<article class="prose">' + doc.html + '</article>' + pager + '</div>';
      page.bind = function () {
        view.querySelectorAll('[data-jump]').forEach(function (b) {
          b.onclick = function () { document.getElementById(b.dataset.jump).scrollIntoView({ block: 'start' }); };
        });
      };
    }
    return page;
  }

  function question(id) {
    var q = qById[id];
    if (!q) return missing();
    var list = q.topic.questions, at = list.indexOf(q), next = list[at + 1];
    var after = next ? '#/question/' + next.id : '#/topic/' + q.topic.id + '/questions';
    return {
      tab: 'home', title: q.topic.title,
      html: '<div class="stack"><div class="row between"><a href="#/topic/' + q.topic.id + '/questions">← Questions</a><span class="muted small">' + (at + 1) + ' of ' + list.length + '</span>' +
        '<button type="button" class="btn" id="bookmark" aria-pressed="' + !!state.saved[id] + '">Bookmark</button></div>' +
        '<div class="row"><span class="pill">' + esc(q.topic.title) + '</span>' + pill(q.level) + '</div><h1>' + inline(q.question) + '</h1>' +
        '<div class="card reveal" id="hidden"><p class="muted">Say your answer out loud first, like you would in the interview.</p><button type="button" class="btn solid" id="reveal">Show answer</button></div>' +
        '<div class="card" id="answer" hidden tabindex="-1"><span class="eyebrow">Answer</span><p>' + inline(q.answer) + '</p></div>' +
        '<div class="cards2"><button type="button" class="btn" id="learning">Still learning</button><button type="button" class="btn primary" id="known">✓ I know this</button></div></div>',
      bind: function () {
        document.getElementById('reveal').onclick = function () {
          document.getElementById('hidden').remove();
          var a = document.getElementById('answer');
          a.hidden = false;
          a.focus();
        };
        document.getElementById('bookmark').onclick = function () {
          if (state.saved[id]) delete state.saved[id]; else state.saved[id] = true;
          this.setAttribute('aria-pressed', !!state.saved[id]);
          save();
        };
        function mark(known) {
          delete state.learned[id];
          delete state.learning[id];
          state[known ? 'learned' : 'learning'][id] = true;
          studied();
          save();
          location.hash = after;
        }
        document.getElementById('known').onclick = function () { mark(true); };
        document.getElementById('learning').onclick = function () { mark(false); };
      }
    };
  }

  function practiceHome() {
    return {
      tab: 'practice', title: 'Practice',
      html: '<div class="stack"><h1>Practice</h1><a class="card hero" href="#/practice/daily"><span class="eyebrow">Daily 5</span><span class="display" style="font-size:21px">Five mixed questions</span></a><h2>By topic</h2><ul class="list">' +
        topics.map(function (t) {
          var n = quiz.filter(function (q) { return q.topic === t.id; }).length;
          return n ? '<li><a class="item" href="#/practice/' + t.id + '"><span class="title">' + esc(t.title) + '</span><span class="muted small">' + n + (n === 1 ? ' question' : ' questions') + '</span></a></li>' : '';
        }).join('') + '</ul></div>'
    };
  }

  function run(set) {
    var daily = set === 'daily';
    var today = dayKey(new Date());
    // Daily 5 is ordered by a hash of the date, so it stays the same all day.
    var pool = daily
      ? quiz.slice().sort(function (a, b) { return hash(today + a.id).localeCompare(hash(today + b.id)); }).slice(0, 5)
      : quiz.filter(function (q) { return q.topic === set; });
    if (!pool.length) return missing();
    var label = daily ? 'Daily 5' : byId[set].title;
    var at = 0, score = 0;
    function draw() {
      var q = pool[at];
      var box = document.getElementById('quiz');
      box.innerHTML = '<div class="row" style="flex-wrap:nowrap"><div class="steps" aria-hidden="true">' + pool.map(function (_, i) { return '<i class="' + (i < at ? 'done' : i === at ? 'now' : '') + '"></i>'; }).join('') + '</div><b class="small">' + (at + 1) + '/' + pool.length + '</b></div>' +
        '<span class="eyebrow">' + esc(label) + (daily && byId[q.topic] ? ' · ' + esc(byId[q.topic].title) : '') + '</span><h1 tabindex="-1" style="font-size:22px">' + inline(q.question) + '</h1>' +
        (q.code ? '<pre tabindex="0"><code>' + esc(q.code) + '</code></pre>' : '') +
        '<div class="options">' + q.options.map(function (o, i) { return '<button type="button" class="option" data-i="' + i + '"><b>' + 'ABCDEF'[i] + '</b><span>' + inline(o) + '</span></button>'; }).join('') + '</div>' +
        '<div id="feedback" aria-live="polite"></div>';
      box.querySelectorAll('.option').forEach(function (b) {
        b.onclick = function () {
          var pick = Number(b.dataset.i), right = pick === q.answer;
          box.querySelectorAll('.option').forEach(function (o) {
            var i = Number(o.dataset.i);
            o.disabled = true;
            if (i === q.answer) o.classList.add('right'); else if (i === pick) o.classList.add('wrong');
          });
          if (right) score++;
          state.quiz.total++;
          if (right) state.quiz.right++;
          studied();
          save();
          var last = at === pool.length - 1;
          document.getElementById('feedback').innerHTML = '<p class="feedback' + (right ? '' : ' no') + '"><b>' + (right ? 'Correct.' : 'Not quite. The answer is ' + 'ABCDEF'[q.answer] + '.') + '</b> ' + inline(q.explanation) + '</p><button type="button" class="btn primary" id="next" style="width:100%">' + (last ? 'See score' : 'Next question') + '</button>';
          document.getElementById('next').onclick = function () {
            if (last) {
              box.innerHTML = '<div class="card reveal"><span class="eyebrow">' + esc(label) + '</span><h1 tabindex="-1">' + score + ' of ' + pool.length + ' correct</h1><a class="btn primary" href="#/practice">Back to practice</a></div>';
            } else {
              at++;
              draw();
            }
            box.querySelector('h1').focus();
          };
        };
      });
    }
    return { tab: 'practice', title: label, html: '<a href="#/practice">← Practice</a><div class="stack" id="quiz" style="margin-top:18px"></div>', bind: draw };
  }

  var query = '';
  function search() {
    function results() {
      var words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
      var box = document.getElementById('results');
      if (!words.length) { box.innerHTML = '<p class="muted">Type to search questions and study notes.</p>'; return; }
      function matches(text) { text = text.toLowerCase(); return words.every(function (w) { return text.indexOf(w) !== -1; }); }
      var qs = questions.filter(function (q) { return matches(q.question + ' ' + q.answer + ' ' + q.topic.title); });
      var notes = topics.filter(function (t) { return matches(t.title + ' ' + t.body); });
      box.innerHTML = '<div class="stack"><p class="muted small">' + qs.length + ' questions and ' + notes.length + ' topics found</p>' +
        (notes.length ? '<div class="row">' + notes.map(function (t) { return '<a class="chip" href="#/topic/' + t.id + '">' + esc(t.title) + '</a>'; }).join('') + '</div>' : '') +
        questionList(qs, true) + '</div>';
    }
    return {
      tab: 'search', title: 'Search',
      html: '<div class="stack"><h1>Search</h1><input class="search" id="q" type="search" aria-label="Search questions and notes" placeholder="Try “flow”, “recomposition”, “Hilt”" value="' + esc(query) + '"><div class="row">' +
        ['flow', 'recomposition', 'lifecycle', 'Hilt', 'Room'].map(function (c) { return '<button type="button" class="chip" data-term="' + c + '">' + c + '</button>'; }).join('') + '</div><div id="results" aria-live="polite"></div></div>',
      bind: function () {
        var input = document.getElementById('q');
        input.oninput = function () { query = input.value; results(); };
        view.querySelectorAll('[data-term]').forEach(function (b) {
          b.onclick = function () { input.value = query = b.dataset.term; results(); };
        });
        results();
      }
    };
  }

  function saved(tab) {
    var learning = tab === 'learning';
    var bookmarks = questions.filter(function (q) { return state.saved[q.id]; });
    var unsure = questions.filter(function (q) { return state.learning[q.id]; });
    var list = learning ? unsure : bookmarks;
    var week = [6, 5, 4, 3, 2, 1, 0].map(function (n) { var d = daysAgo(n); return { day: 'SMTWTFS'[d.getDay()], n: state.days[dayKey(d)] || 0 }; });
    var max = Math.max.apply(null, week.map(function (d) { return d.n; }).concat(1));
    return {
      tab: 'saved', title: 'Your progress',
      html: '<div class="stack"><h1>Your progress</h1><div class="stats"><div class="card"><strong>' + learnedCount(questions) + '</strong><span class="muted small">Learned</span></div><div class="card"><strong>' + streak() + '</strong><span class="muted small">Day streak</span></div><div class="card"><strong>' + (state.quiz.total ? Math.round(state.quiz.right / state.quiz.total * 100) + '%' : '–') + '</strong><span class="muted small">Quiz score</span></div></div>' +
        '<div class="card"><b class="small">This week</b><div class="week" role="img" aria-label="Answers per day over the last seven days: ' + week.map(function (d) { return d.n; }).join(', ') + '">' +
        week.map(function (d) { return '<div><i style="height:' + Math.max(4, Math.round(d.n / max * 60)) + 'px"></i>' + d.day + '</div>'; }).join('') + '</div></div>' +
        '<div class="row"><a class="chip" href="#/saved"' + (learning ? '' : ' aria-current="page"') + '>Bookmarked (' + bookmarks.length + ')</a><a class="chip" href="#/saved/learning"' + (learning ? ' aria-current="page"' : '') + '>Still learning (' + unsure.length + ')</a></div>' +
        (list.length ? questionList(list, true) : '<p class="muted">' + (learning ? 'Questions you mark “Still learning” show up here.' : 'Bookmark a question to find it here.') + '</p>') + '</div>'
    };
  }

  function missing() { return { tab: 'home', title: 'Not found', html: '<h1>Page not found</h1><p><a href="#/">Back to topics</a></p>' }; }

  function route() {
    // "#view" is the skip link, not a page.
    if (location.hash === '#view') return;
    var p = location.hash.replace(/^#\/?/, '').split('/');
    var page = p[0] === '' ? home()
      : p[0] === 'topic' ? topic(p[1], p[2])
      : p[0] === 'question' ? question(p[1])
      : p[0] === 'practice' ? (p[1] ? run(p[1]) : practiceHome())
      : p[0] === 'search' ? search()
      : p[0] === 'saved' ? saved(p[1])
      : missing();
    view.className = page.wide ? '' : 'narrow';
    view.innerHTML = page.html;
    document.title = page.title + ' – DroidReady';
    document.querySelectorAll('[data-tab]').forEach(function (a) {
      if (a.dataset.tab === page.tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    if (page.bind) page.bind();
    window.scrollTo(0, 0);
  }

  load().then(function () {
    window.addEventListener('hashchange', function () { route(); view.focus({ preventScroll: true }); });
    route();
  }).catch(function (e) {
    view.innerHTML = '<h1>Content could not be loaded</h1><p class="muted">' + esc(e.message) + '. Reload the page to try again.</p>';
  });
})();
