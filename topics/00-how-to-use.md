# How to use this guide

Every topic in this guide is written the way you will use it in an interview: a short definition you can remember, an answer you can say out loud, a small example, and the follow-up questions interviewers ask next.

### How each concept is laid out

- **In one line:** the definition. If you only remember one sentence, remember this.
- **Say this in the interview:** a 20-40 second spoken answer. Practise it aloud until it sounds like your own words.
- **Example:** the smallest code or scenario that proves you understand it. Mention it when you answer.
- **How it works:** what happens underneath. Use it when the interviewer asks "why?" or "how?".
- **Follow-ups:** the next questions you will probably get, with short answers.

### How to answer any technical question

Use the same four steps for almost every question:

1. **Define it** in one sentence.
2. **Explain why it exists:** the problem it solves.
3. **Give an example**, ideally from your own work.
4. **Mention a trade-off or pitfall:** when not to use it, or what goes wrong.

Example, for "What is a ViewModel?":

1. "A ViewModel holds and manages UI state for a screen."
2. "It exists because activities are destroyed on rotation, and we don't want to reload data every time."
3. "In my last app the feed ViewModel exposed a `StateFlow<FeedUiState>` and survived rotation, so scrolling and loaded data stayed put."
4. "It does not survive process death, so small user input goes into `SavedStateHandle` and real data into Room."

That answer takes about 30 seconds and covers everything a senior interviewer listens for.

### What a typical senior loop looks like

| Round | What they test | Where to prepare |
| --- | --- | --- |
| Recruiter or hiring-manager screen | Your scope, impact and motivation | Your 2-minute career story; 3 projects with numbers |
| Coding | Kotlin fluency, problem solving, tests | Section 16 |
| Android deep dive | Kotlin, coroutines, lifecycle, Compose, memory | Sections 1-4, 7-9, 18 |
| Architecture and code review | Layers, data flow, testability, trade-offs | Sections 5, 6, 10 |
| Mobile system design | Designing a feature or app end to end | Section 13 |
| Behavioural and leadership | Ownership, mentoring, conflict, impact | Section 15 |

### What makes an answer sound senior

- **Trade-offs, not absolutes.** "MVI suits screens with many interacting events; for a simple form, MVVM with one state class is enough."
- **Failure cases without being asked.** Process death, rotation, offline, slow networks, low-end devices, accessibility.
- **Numbers.** "Cold start went from 2.1 s to 1.2 s after a baseline profile and lazy SDK init."
- **Team impact.** Standards you set, modules that let teams ship in parallel, people you mentored.

### Study plan (3 weeks)

1. **Week 1, language and platform:** sections 1-4 and 18. Say each "Say this" answer aloud once a day.
2. **Week 2, architecture and data:** sections 5-12. Build a small offline-first app (Room, Retrofit, WorkManager, Hilt) with tests.
3. **Week 3, design and people:** sections 13-17. Do 3 mock system designs aloud, write 6 STAR stories, and run the rapid-fire table daily.
