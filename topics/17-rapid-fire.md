# Rapid-fire Q&A and final checklist

Cover the answer column and test yourself daily during the last week.

### 17.1 Rapid-fire questions

| Question | Short answer | Level |
| --- | --- | --- |
| `val` vs `const val`? | `val` is read-only at runtime; `const val` is a compile-time constant, inlined, primitives/String only | Easy |
| `lateinit` on a primitive? | Not allowed; use `Delegates.notNull()` or a nullable | Easy |
| `==` vs `===`? | Structural vs referential equality | Easy |
| `Any`, `Unit`, `Nothing`? | Root type; single-value "no result" type; type with no values (functions that never return, e.g. `throw`) | Easy |
| `suspend` function under the hood? | Extra `Continuation` parameter, compiled into a state machine | Medium |
| `Job` vs `SupervisorJob`? | Child failure cancels parent and siblings vs is isolated | Medium |
| `coroutineScope` vs `supervisorScope`? | Same distinction, as suspending builders | Medium |
| `StateFlow` vs `SharedFlow`? | Always has a value + conflates equal values vs configurable replay, no initial value | Medium |
| Cold vs hot Flow? | Starts per collector vs active independent of collectors | Easy |
| `flatMapLatest` use case? | Search-as-you-type: cancel the previous query | Medium |
| `collectAsStateWithLifecycle` vs `collectAsState`? | Former stops collecting below STARTED | Easy |
| `remember` vs `rememberSaveable`? | Survives recomposition vs also config change and process death | Easy |
| `derivedStateOf`? | Derived state that changes less often than its input (avoid over-recomposition) | Medium |
| What makes a Compose type stable? | Immutable, or notifies Compose of changes; all public properties `val` and stable | Medium |
| ViewModel survives process death? | No - use `SavedStateHandle` or persistence | Easy |
| Where is the Bundle limit enforced? | Binder transaction buffer (\~1 MB per process) | Medium |
| `Serializable` vs `Parcelable`? | Reflection, slow vs explicit, fast (`@Parcelize`) | Easy |
| LiveData `setValue` vs `postValue`? | Main thread, immediate vs any thread, posted (intermediate values can be lost) | Medium |
| `commit()` vs `apply()` in SharedPreferences? | Synchronous, returns Boolean vs async write (but can block at lifecycle points) | Medium |
| `Service` vs `IntentService` vs WorkManager? | Runs on main thread, you manage threads; `IntentService` deprecated; WorkManager for guaranteed deferrable work | Easy |
| `Dispatchers.IO` vs `Default`? | Blocking I/O (many threads) vs CPU-bound (cores) | Easy |
| ANR thresholds? | \~5 s input; \~10 s foreground broadcast | Easy |
| What is a baseline profile? | AOT-compile hints for critical paths shipped with the app | Medium |
| What does R8 do? | Shrink, obfuscate, optimise; needs keep rules for reflection | Easy |
| `@Binds` vs `@Provides`? | Interface → implementation mapping (abstract) vs factory code you write | Medium |
| Hilt scope for an object shared by a screen's ViewModel and nothing else? | `@ViewModelScoped` | Medium |
| Why `exported` must be declared? | Security: since Android 12, components with intent filters must state if other apps can start them | Easy |
| `PendingIntent` mutability flag? | Required since Android 12; prefer `FLAG_IMMUTABLE` | Medium |
| What is a `ContentProvider` used for in libraries? | Auto-initialisation (now replaced by App Startup) and sharing data via URIs | Medium |
| What is `Looper.prepare()`? | Creates a message loop for the current thread (used by `HandlerThread`) | Hard |
| What is Doze? | Idle mode deferring network, jobs and alarms to maintenance windows | Easy |
| 16 KB page size? | Newer devices use 16 KB memory pages; native libraries must be aligned/rebuilt | Medium |

### 17.2 Final checklist (the day before)

- [ ] Can explain the Activity and Fragment lifecycles, including rotation and A→B navigation, from memory
- [ ] Can explain config change vs process death and what survives each
- [ ] Can write a ViewModel with `StateFlow`, `stateIn(WhileSubscribed(5000))` and a test with `runTest` + Turbine
- [ ] Can explain structured concurrency, cancellation and exception propagation with examples
- [ ] Can explain recomposition, stability, side-effect APIs and two Compose performance fixes
- [ ] Can draw the layered architecture and an offline-first repository, and defend MVVM vs MVI
- [ ] Can set up Hilt modules, scopes and test replacements
- [ ] Can design a chat / feed app end to end in 45 minutes using the framework in section 13
- [ ] Have 3 performance war stories with numbers (memory leak, ANR, startup or jank)
- [ ] Have 6-8 STAR stories covering conflict, failure, mentoring, impact, tech debt and ownership
- [ ] Know what changed in Android 14-17 and how it affected your apps
- [ ] Have solved \~30 medium DSA problems in Kotlin, including LRU cache
- [ ] Have 3-5 thoughtful questions for each interviewer

### 17.3 Recommended resources

- [Guide to app architecture](https://developer.android.com/topic/architecture) and the *Now in Android* sample app (GitHub: android/nowinandroid)
- [Kotlin coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Compose performance best practices](https://developer.android.com/develop/ui/compose/performance)
- [App performance guide](https://developer.android.com/topic/performance/overview)
- [Navigation 3 is stable](https://developer.android.com/blog/posts/jetpack-navigation-3-is-stable) (Nov 2025)
- [Android 17 release post](https://android-developers.googleblog.com/2026/06/Android-17.html) (June 2026) and [Android 17 Beta 1 post](https://android-developers.googleblog.com/2026/02/the-first-beta-of-android-17.html)

Version-specific details in sections 4.8 and 14.1 were checked against these Android Developers pages on the as-of date; library version numbers in examples are illustrative.
