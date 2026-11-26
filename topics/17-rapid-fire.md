# Rapid-fire Q&A and final checklist

Some interviews open with quick questions to check the basics. Answer in one sentence, then stop; the interviewer will ask for more if they want it. Cover the answer column and test yourself daily during the last week.

### 17.1 Rapid-fire questions

| Question | Say this | Level |
| --- | --- | --- |
| `val` vs `const val`? | `val` is read-only and set at runtime; `const val` is a compile-time constant that gets inlined, and only works for primitives and String | Easy |
| `lateinit` on an `Int`? | Not allowed, because primitives can't be null internally; use `Delegates.notNull()` or a nullable type | Easy |
| `==` vs `===`? | `==` compares content using `equals`; `===` checks it's the same object | Easy |
| `Any`, `Unit` and `Nothing`? | `Any` is the root type; `Unit` means "no useful result"; `Nothing` means "never returns", like `throw` | Easy |
| What is a `suspend` function under the hood? | The compiler adds a `Continuation` parameter and turns the body into a state machine that can pause and resume | Medium |
| `Job` vs `SupervisorJob`? | With `Job`, a child's failure cancels the parent and siblings; with `SupervisorJob`, children fail independently | Medium |
| `coroutineScope` vs `supervisorScope`? | The same difference, as suspending functions: one failure cancels all, or each child fails alone | Medium |
| `StateFlow` vs `SharedFlow`? | `StateFlow` always has a current value and skips equal values; `SharedFlow` has no initial value and configurable replay, good for events | Medium |
| Cold vs hot Flow? | A cold flow starts fresh for each collector; a hot flow runs whether or not anyone collects | Easy |
| When do you use `flatMapLatest`? | Search as you type: a new query cancels the previous search | Medium |
| `collectAsStateWithLifecycle` vs `collectAsState`? | The lifecycle version stops collecting when the app goes to the background | Easy |
| What is `derivedStateOf` for? | State computed from other state that changes less often than its inputs, so it avoids extra recompositions | Medium |
| What makes a type stable in Compose? | It's immutable, or it tells Compose when it changes; all public properties are `val` and stable themselves | Medium |
| Does a ViewModel survive process death? | No; use `SavedStateHandle` for small UI state and a database for real data | Easy |
| What limits the size of a saved-state Bundle? | The Binder transaction buffer, about 1 MB shared by the process, so keep saved state small | Medium |
| `Serializable` vs `Parcelable`? | `Serializable` uses reflection and is slow; `Parcelable` is explicit and fast, and `@Parcelize` writes it for you | Easy |
| LiveData `setValue` vs `postValue`? | `setValue` runs on the main thread immediately; `postValue` works from any thread but can drop intermediate values | Medium |
| SharedPreferences `commit()` vs `apply()`? | `commit()` writes synchronously and returns success; `apply()` writes in the background but can still block at lifecycle points, a common ANR cause | Medium |
| `Service` vs WorkManager? | A `Service` runs on the main thread and you manage its work and lifetime; WorkManager is for deferrable work that must be guaranteed; `IntentService` is deprecated | Easy |
| `Dispatchers.IO` vs `Default`? | `IO` is for blocking I/O and has many threads; `Default` is for CPU work and has one thread per core | Easy |
| What are the ANR thresholds? | About 5 seconds for input and about 10 seconds for a foreground broadcast receiver | Easy |
| What does R8 do? | It shrinks, obfuscates and optimises code; anything used by reflection needs keep rules | Easy |
| `@Binds` vs `@Provides`? | `@Binds` maps an interface to an implementation with no code; `@Provides` is a function you write to build the object | Medium |
| Hilt scope for an object shared only within one screen's ViewModel? | `@ViewModelScoped` | Medium |
| Why must `exported` be declared? | Since Android 12, components with intent filters must say whether other apps can start them, for security | Easy |
| `PendingIntent` mutability flag? | Required since Android 12; prefer `FLAG_IMMUTABLE` unless something must fill in the intent | Medium |
| Why did libraries use a `ContentProvider`? | To initialise automatically at app start, now replaced by App Startup; providers also share data through URIs | Medium |
| What does `Looper.prepare()` do? | It creates a message loop for the current thread, which is how `HandlerThread` works | Hard |
| What is Doze? | An idle mode that delays network, jobs and alarms to short maintenance windows to save battery | Easy |
| Why does the 16 KB page size matter? | Newer devices use 16 KB memory pages, so native libraries must be rebuilt and aligned for it | Medium |
| Companion object vs top-level function? | A companion is a real object inside the class, good for factories and private access; top-level functions are simpler for plain utilities | Easy |
| `let` vs `apply`? | `let` passes the object as `it` and returns the lambda result; `apply` uses `this` and returns the object, good for configuring | Easy |

### 17.2 Final checklist (the day before)

- [ ] Explain the Activity and Fragment lifecycles from memory, including rotation and navigating from A to B
- [ ] Explain configuration change vs process death and what survives each
- [ ] Write a ViewModel with `StateFlow` and `stateIn(WhileSubscribed(5000))`, and test it with `runTest` and Turbine
- [ ] Explain structured concurrency, cancellation and exception propagation with examples
- [ ] Explain recomposition, stability, side-effect APIs and two Compose performance fixes
- [ ] Draw the layered architecture and the data flow of an offline-first repository, and compare MVVM and MVI
- [ ] Set up Hilt modules, scopes and test replacements
- [ ] Design a chat or feed app end to end in 45 minutes using the framework in section 13
- [ ] Have three performance stories with numbers: a memory leak, an ANR, startup or jank
- [ ] Have 6-8 STAR stories covering conflict, failure, mentoring, impact, tech debt and ownership
- [ ] Know what changed in Android 13-17 and how it affected your apps
- [ ] Have solved about 30 medium algorithm problems in Kotlin, including an LRU cache
- [ ] Have 3-5 thoughtful questions for each interviewer

### 17.3 Recommended resources

- [Guide to app architecture](https://developer.android.com/topic/architecture) and the Now in Android sample app (GitHub: android/nowinandroid)
- [Kotlin coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Kotlin scope functions](https://kotlinlang.org/docs/scope-functions.html)
- [Compose performance best practices](https://developer.android.com/develop/ui/compose/performance)
- [App performance guide](https://developer.android.com/topic/performance/overview)
- [Navigation 3 is stable](https://developer.android.com/blog/posts/jetpack-navigation-3-is-stable) (Nov 2025)
- [Android 17 release post](https://android-developers.googleblog.com/2026/06/Android-17.html) (June 2026) and [Android 17 Beta 1 post](https://android-developers.googleblog.com/2026/02/the-first-beta-of-android-17.html)

Version-specific details in sections 4 and 14.1 were checked against these Android Developers pages on the as-of date; library version numbers in examples are illustrative.
