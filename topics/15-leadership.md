# Leadership and behavioural

At senior level this round can veto an otherwise strong technical result. Prepare 6-8 stories from your own work and reuse them across questions. The numbers in the examples below are illustrative; use your own.

### 15.1 The STAR format

**In one line:** answer behavioural questions as Situation, Task, Action, Result, spending most of the time on what you did.

**Say this in the interview:** keep the Situation and Task to two or three sentences, then spend about 60 percent of the answer on your actions: the decisions, the trade-offs and why. Say "I", not "we", for your part. End with a measurable result and what you learned.

**Example:**

| Part | What to say | Length |
| --- | --- | --- |
| Situation | The context in one or two sentences | 10% |
| Task | What you were responsible for | 10% |
| Action | What you did, the options you weighed, how you brought others along | 60% |
| Result | Numbers, plus what you learned or would do differently | 20% |

**Common mistake:** Spending most of the answer on background, or saying "we" so your own part is unclear.

**Follow-ups:**

- *What if the interviewer interrupts?* That's good: they're steering toward what they want to assess. Answer their question directly, then continue only if it still helps.

### 15.2 A full example answer

**In one line:** a strong answer shows scope beyond your own tickets, a clear root cause, concrete actions and measured results.

**Example, "Tell me about a time you improved app quality significantly":**

- **Situation:** "Our shopping app was at 98.9 percent crash-free users, and Play vitals flagged excessive ANRs, which hurts store visibility."
- **Task:** "As the senior on the platform team, I owned getting us to 99.8 percent within a quarter."
- **Action:** "I grouped Crashlytics issues by root cause and found most ANRs came from `SharedPreferences.commit()` and SDK initialisation on the main thread. I moved settings to DataStore, made four SDKs initialise lazily, and added StrictMode and a startup benchmark to CI so it couldn't regress. I also started a weekly 30-minute crash review with each feature team, so fixes were owned by the team that wrote the code."
- **Result:** "Crash-free users rose to 99.85 percent, ANRs fell from 0.6 to 0.2 percent, and cold start improved by about a third. The weekly review became a standing practice."

**Common mistake:** Memorizing someone else's story. Follow-up questions quickly reach details you don't have.

**Follow-ups:**

- *How long should a story be?* About two minutes is a useful target. Then let the interviewer ask for more detail.

### 15.3 Common questions and what they're testing

**In one line:** each behavioural question checks a specific senior quality, so pick the story that shows it.

**Example:**

| Question | What they want to see |
| --- | --- |
| A technical decision others disagreed with | Persuading with data, listening, disagree and commit |
| A project that failed or an incident you caused | Ownership, blameless post-mortem, what changed afterwards |
| How you mentor junior developers | A specific growth outcome, pairing, review style, delegation |
| A time you pushed back on product or design | Balancing user value, deadlines and tech debt; offering alternatives |
| How you handle tech debt | Measuring its cost, linking it to business impact, incremental refactoring, reserved capacity |
| The most complex thing you built | Depth, scope, trade-offs, your specific role |
| How you do code reviews | Kind and specific feedback, automated style checks, focus on correctness, design and tests, quick turnaround |
| How you improved team speed or process | A measured change: build time, release cadence, fewer bugs |
| Learning something new quickly | How you learn, and the outcome |
| Why are you leaving, why us | Positive, specific, linked to the role |

**Common mistake:** Using one story for every question, even when it doesn't show the quality being tested.

**Follow-ups:**

- *How many stories should you prepare?* A handful that cover different qualities, such as leadership, conflict, failure and technical depth.

### 15.4 Answering the tough ones

**In one line:** for disagreements, failures and tech debt, show maturity: facts over opinions, ownership over blame, and incremental progress over big rewrites.

**Say this in the interview:**

- **Disagreement:** "I wrote a short RFC comparing both options with data, asked for objections, and built a small prototype. The team chose the other option; I committed fully, and we agreed on a checkpoint to revisit it."
- **Failure:** "I own it: here's what happened, how we fixed it for users, what the post-mortem found, and what we changed in the process so it can't recur."
- **Tech debt:** "I measure its cost, in bugs, slower delivery or build time, tie it to a business goal, and fix it incrementally alongside features, with a fixed share of capacity, rather than asking for a rewrite."

**Common mistake:** Blaming others, or offering a disguised strength as your failure.

**Follow-ups:**

- *When would you argue for a rewrite?* Rarely: only when incremental change costs more than the rewrite and you can migrate in slices behind flags, keeping the old path running.

### 15.5 Senior signals to include in every story

**In one line:** interviewers listen for scope, numbers, influence, pragmatism and care for people.

**Example:**

- **Scope:** impact beyond your tickets: other teams, standards, tooling.
- **Numbers:** users, percentages, milliseconds, build minutes, crash rates, revenue.
- **Influence without authority:** RFCs, architecture decision records, prototypes, internal talks.
- **Pragmatism:** delivered value in increments, and knew when not to rewrite.
- **Care for people:** mentoring, psychological safety, onboarding documents.

**Common mistake:** Claiming impact with no number or concrete result behind it.

**Follow-ups:**

- *What if you have no exact numbers?* Give an honest estimate and say that it is one, or describe a result that can be observed. Don't invent figures.

### 15.6 Questions to ask the interviewer

**In one line:** good questions show you think like an owner and help you judge the team.

**Say this in the interview:** "I have a few questions about how the team works. How are architecture decisions made and recorded? What does the release process look like? And what would success look like in this role after six months?"

**Example:**

- How are architecture decisions made and recorded here?
- What does the release process look like, and what are your current crash-free and ANR rates?
- How is the Android team organised relative to iOS, backend and product?
- What would success look like in this role after six months?
- What's the biggest technical challenge the Android team faces right now?

**Common mistake:** Saying you have no questions.

**Follow-ups:**

- *What is a good question about how the team works?* Ask how a recent technical decision was made. The example tells you more than a general description.

### Interview questions

1. **Tell me about a technical decision others disagreed with.** Show how you gathered data, listened, wrote it up or prototyped, and either persuaded the team or committed to their choice with a checkpoint. {Medium}
2. **Describe a production incident you caused.** Own it, explain the fix for users, the blameless post-mortem, and the process change that prevents a repeat. {Medium}
3. **How do you mentor junior developers?** Give one specific person and outcome: pairing, gradually larger tasks, review feedback that teaches, and their growth as the result. {Medium}
4. **How do you handle tech debt?** Measure its cost, link it to business impact, fix it incrementally with reserved capacity, and avoid big-bang rewrites. {Medium}
5. **How do you do code reviews?** Review quickly, automate style, focus on correctness, design and tests, explain the why, and separate must-fix comments from suggestions. {Easy}
6. **Tell me about a time you pushed back on product.** Explain the risk in user and business terms, offer an alternative such as a smaller first version, and agree on a decision together. {Medium}
7. **What makes a developer senior rather than mid-level?** Scope beyond their own tasks, sound trade-off decisions, raising the team's level through mentoring and standards, and owning outcomes in production. {Easy}
