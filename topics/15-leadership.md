# Leadership and behavioural

At senior level this round can veto an otherwise strong technical result. Prepare **6-8 stories** from your own work and reuse them across questions.

### 15.1 The STAR format

- **Situation:** one or two sentences of context.
- **Task:** what you were responsible for.
- **Action:** what *you* did (say "I", not "we"); the decisions and trade-offs. This should be \~60% of the answer.
- **Result:** measurable outcome, plus what you learned.

### 15.2 Example answer

**Q: Tell me about a time you improved app quality significantly.**

- **S:** Our shopping app had a 98.9% crash-free user rate and Play vitals flagged excessive ANRs, hurting store visibility.
- **T:** As the senior on the platform team, I owned bringing it to 99.8% within one quarter.
- **A:** I grouped Crashlytics issues by root cause and found that 60% of ANRs came from `SharedPreferences.commit()` and SDK initialisation on the main thread. I migrated settings to DataStore, moved 4 SDKs to lazy initialisation with App Startup, and added StrictMode and a Macrobenchmark startup test to CI. I ran a weekly 30-minute crash review with each feature team so fixes were owned locally.
- **R:** Crash-free users rose to 99.85%, ANR rate fell from 0.6% to 0.2%, and cold start improved by 35%. The weekly review became a standing practice.

### 15.3 Questions to prepare, and what they are probing

| Question | What they want to see |
| --- | --- |
| Tell me about a technical decision you made that others disagreed with | Data-driven persuasion, listening, disagree-and-commit |
| Describe a project that failed or a production incident you caused | Ownership, blameless post-mortem, what changed afterwards |
| How do you mentor junior developers? Give an example | Specific growth outcome, pairing, code-review style, delegation |
| Tell me about a time you pushed back on product/design | Balancing user value, deadlines and tech debt; offering alternatives |
| How do you handle tech debt? | Quantify cost, tie it to business impact, incremental refactoring, allocate capacity (e.g. 20%) |
| Describe the most complex thing you built | Depth, scope, trade-offs, your specific role |
| How do you do code reviews? | Kind and specific feedback, automate style, focus on correctness/design/tests, timely reviews |
| How did you improve team velocity or process? | Measurable change: build time, release cadence, fewer bugs |
| A time you had to learn something new quickly | Learning approach, outcome |
| Why are you leaving / why us? | Positive, specific, linked to the role |

### 15.4 Senior signals to weave into every story

- Scope beyond your own tickets: cross-team impact, standards, tooling.
- Numbers: users, %, ms, build minutes, crash rates, revenue.
- Influence without authority: RFCs, ADRs, prototypes, brown-bag sessions.
- Pragmatism: shipped value incrementally, knew when **not** to rewrite.
- Care for people: mentoring, psychological safety, onboarding documents.

### 15.5 Questions to ask the interviewer

- How are architecture decisions made and recorded here?
- What does the release process look like, and what are the current crash-free and ANR rates?
- How is the Android team structured relative to iOS, backend and product?
- What would success look like for this role after 6 months?
- What is the biggest technical challenge the Android team faces right now?
