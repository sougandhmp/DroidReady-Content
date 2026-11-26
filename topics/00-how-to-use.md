# How to use this guide

A senior Android interview tests whether you can **own a feature or app end to end**: write correct Kotlin, choose an architecture and defend it, find performance problems, design a system, and lead other engineers. Knowing API names is not enough. For every topic, be ready to say *why*, *when not to*, and *what you did in production*.

Each section below has three parts: **Learn** (the concept), **Example** (code or a scenario), and **Interview questions** (what you will be asked, with the answer an interviewer wants to hear).

### What a typical senior loop looks like

| Round | What they test | How to prepare |
| --- | --- | --- |
| Recruiter / hiring manager screen | Scope of past work, motivation, seniority signals | 2-minute career story; 3 projects with numbers |
| Coding (live or take-home) | Kotlin fluency, DSA basics, clean code, tests | Section 16; practise in Kotlin, not Java |
| Android deep dive | Lifecycle, coroutines, Compose, memory, threading | Sections 1-4, 7-9 |
| Architecture / code review | Layering, testability, trade-offs | Sections 5-6, 10 |
| Mobile system design | Design an app or feature end to end | Section 13 |
| Behavioural / leadership | Mentoring, conflict, ownership, impact | Section 15 |

### What separates senior from mid-level answers

- **Trade-offs, not absolutes.** Not "MVI is better" but "MVI suits screens with many interacting events; for a simple form, MVVM with one state class is less ceremony."
- **Failure modes.** Mention process death, configuration changes, offline, slow networks, low-memory devices, and accessibility without being asked.
- **Measurement.** "We cut cold start from 2.1 s to 1.2 s using a baseline profile and lazy init" beats "I optimised startup."
- **Team impact.** Code review standards, modularisation that let 5 teams ship in parallel, mentoring juniors.

### Suggested 3-week study plan

1. **Week 1 - language and platform:** Sections 1-4. Write small sample apps for coroutines and Compose state.
2. **Week 2 - architecture and data:** Sections 5-10. Build a mini offline-first app (Room + Retrofit + WorkManager + Hilt) with tests.
3. **Week 3 - design and people:** Sections 11-17. Do 3 mock system designs aloud, write 6 STAR stories, and run the rapid-fire Q&A daily.
