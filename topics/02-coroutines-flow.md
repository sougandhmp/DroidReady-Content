# Coroutines and Flow

Coroutines are the most-asked senior topic. Be ready to explain what suspension really is, structured concurrency, cancellation, exceptions, and the difference between cold and hot flows.

### 2.1 What a coroutine is

**In one line:** a coroutine is a piece of work that can pause (suspend) without blocking its thread, and resume later, possibly on another thread.

**Say this in the interview:** "A coroutine is like a very lightweight thread. When it reaches a suspending call, such as a network request, it saves where it was and frees the thread, so the thread can do other work. When the result arrives, it resumes from the same point. The compiler makes this possible by turning every suspend function into a state machine with a `Continuation` parameter. That's why thousands of coroutines are cheap, while thousands of threads would run out of memory."

**Example:**

```kotlin
suspend fun loadProfile(id: String): Profile {
    val user = api.getUser(id)           // suspends here; the main thread is free meanwhile
    val avatar = api.getAvatar(user)     // and here
    return Profile(user, avatar)         // reads like normal sequential code
}
```

**How it works:** the compiler adds a `Continuation` parameter and turns the function into a `when (label)` state machine that stores local variables in an object. At a suspension point the function returns the special value `COROUTINE_SUSPENDED`, releasing the thread; later the continuation is resumed and jumps to the saved label. A suspended coroutine is just a small object on the heap, not a 1 MB thread stack.

**Common mistake:** Assuming `suspend` moves work off the main thread. Blocking code inside a suspend function still blocks its thread.

**Follow-ups:**

- *Does `suspend` make code run in the background?* No. It only means the function can pause. Which thread it runs on depends on the dispatcher.
- *Coroutine vs thread?* Many coroutines share a few threads; switching between them is cheap and doesn't involve the OS.

### 2.2 Scopes, builders and structured concurrency

**In one line:** every coroutine runs inside a scope, and a parent coroutine waits for, and can cancel, all of its children.

**Say this in the interview:** "Structured concurrency means coroutines form a tree: a scope owns its coroutines, and cancelling the scope cancels everything in it. On Android I use `viewModelScope`, which is cancelled when the ViewModel is cleared, and `lifecycleScope` for UI. I start work with `launch` when I don't need a result and `async` when I need one, mostly for running calls in parallel inside `coroutineScope`. With a normal `Job`, one failing child cancels its siblings; with `SupervisorJob` or `supervisorScope`, children fail independently."

**Example:**

```kotlin
// Parallel calls; if one fails, the other is cancelled and the error is thrown here
suspend fun loadDashboard(): Dashboard = coroutineScope {
    val user = async { api.user() }
    val stats = async { api.stats() }
    Dashboard(user.await(), stats.await())
}

// Independent jobs: one failing doesn't stop the other
supervisorScope {
    launch { syncContacts() }
    launch { syncPhotos() }
}
```

| Builder | Returns | Use for |
| --- | --- | --- |
| `launch` | `Job` | Fire-and-forget work |
| `async` | `Deferred<T>` (call `await()`) | Parallel work that returns a result |
| `withContext(d)` | The block's result | Switching thread for a block |
| `coroutineScope { }` | The block's result | Grouping children; fails if any child fails |
| `runBlocking` | The block's result | Tests and `main` only; it blocks the thread |

**Common mistake:** Launching in `GlobalScope`, or any scope nobody cancels, so the work outlives the screen that started it.

**Follow-ups:**

- *Why avoid `GlobalScope`?* It isn't tied to any lifecycle, so the work can leak and can't be cancelled or tested. For app-wide work, inject an application-scoped `CoroutineScope(SupervisorJob() + Dispatchers.Default)`.

### 2.3 Dispatchers and main-safety

**In one line:** a dispatcher decides which thread or thread pool a coroutine runs on.

**Say this in the interview:** "`Dispatchers.Main` runs on the UI thread; `IO` is a large shared pool for blocking disk and network work; `Default` is sized to the CPU cores for heavy computation like parsing or sorting. My rule is that every suspend function should be main-safe: the function that does the blocking work switches with `withContext`, so callers never need to think about threads. I inject dispatchers so tests can replace them."

**Example:**

```kotlin
class ArticleRepository(
    private val api: ArticleApi,
    private val io: CoroutineDispatcher = Dispatchers.IO     // injectable for tests
) {
    suspend fun fetch(id: String): Article = withContext(io) { api.getArticle(id) }
}
```

**How it works:** `viewModelScope` and `lifecycleScope` use `Dispatchers.Main.immediate`, which runs straight away if already on the main thread. `IO` allows 64 threads (or more on many-core devices) because those threads mostly wait.

**Common mistake:** Running blocking I/O on `Dispatchers.Default`, which has only a few threads meant for CPU work.

**Follow-ups:**

- *Do I need `withContext(IO)` around Room or Retrofit suspend functions?* No; they are already main-safe. Use it for your own blocking code.

### 2.4 Cancellation

**In one line:** cancellation is cooperative: a coroutine stops only at points where it checks for cancellation, such as suspending calls.

**Say this in the interview:** "Cancelling a coroutine throws a `CancellationException` at its next suspension point. Library suspend functions like `delay` and `withContext` check for it, but a tight CPU loop must call `ensureActive()` itself. The big rule is never to swallow `CancellationException`: a blanket `catch (e: Exception)` around a suspend call breaks cancellation, so I either rethrow it or catch specific exceptions. Cleanup goes in `finally`, and if cleanup must suspend, I wrap it in `withContext(NonCancellable)`."

**Example:**

```kotlin
viewModelScope.launch {
    try {
        repository.refresh()
    } catch (e: CancellationException) {
        throw e                                   // let cancellation continue
    } catch (e: IOException) {
        _state.update { it.copy(error = R.string.offline) }
    }
}
```

**Common mistake:** Catching `Exception` around a suspend call and swallowing `CancellationException`.

**Follow-ups:**

- *Why is `runCatching` risky in coroutines?* It also catches `CancellationException`; rethrow it if you use it.

### 2.5 Exception handling

**In one line:** an uncaught exception in a child coroutine travels up to its parent, cancels its siblings, and crashes the app unless something handles it.

**Say this in the interview:** "With `launch`, an exception propagates up the job tree; if nothing catches it, it goes to the `CoroutineExceptionHandler` or crashes the app. With `async`, the exception is stored and rethrown at `await()`, but in a regular scope it also cancels the parent straight away. `viewModelScope` uses a `SupervisorJob`, so one failing `launch` doesn't cancel the others, but the exception still crashes the app if uncaught. So I catch errors inside the coroutine and turn them into UI state."

**Example:**

```kotlin
try {
    scope.launch { error("boom") }    // WRONG: launch returns at once; the error happens later
} catch (e: Exception) { }

scope.launch {
    try { work() } catch (e: IOException) { showError() }   // RIGHT: catch inside the coroutine
}
```

**Common mistake:** Wrapping `launch` in `try`/`catch` and expecting it to catch what happens inside the coroutine.

**Follow-ups:**

- *What is `CoroutineExceptionHandler` for?* A last-resort logger for root coroutines; it can't recover the failed work.

### 2.6 Flow: cold streams and operators

**In one line:** a `Flow` is a cold stream of values: its code runs again for each collector, and only when collected.

**Say this in the interview:** "A Flow is the coroutine version of a stream. It's cold, so nothing happens until someone calls `collect`, and each collector gets its own run. I build pipelines with operators like `map`, `filter`, `debounce`, `combine` and `flatMapLatest`, use `flowOn` to move upstream work to another dispatcher, and Room gives me Flows that re-emit whenever the table changes."

**Example:**

```kotlin
repository.observeArticles()                    // Flow<List<Article>> from Room
    .map { list -> list.filter { it.isPublished } }
    .distinctUntilChanged()
    .flowOn(Dispatchers.Default)                // the steps above run on Default
    .collect { render(it) }
```

**How it works:** `flowOn` changes the context of everything above it. Inside `flow { }` you must not emit from another context (for example inside `withContext`); use `flowOn` or `channelFlow`.

**Common mistake:** Collecting the same cold flow twice and expecting the work to run only once.

**Follow-ups:**

- *`combine` vs `zip`?* `combine` emits whenever any input changes, using the latest of each; `zip` pairs items in order, one from each.

### 2.7 Hot flows: StateFlow, SharedFlow and Channel

**In one line:** hot streams are active whether or not anyone collects: `StateFlow` always holds a current value, `SharedFlow` broadcasts events, and a `Channel` delivers each item to exactly one receiver.

**Say this in the interview:** "For UI state I use `StateFlow`: it always has a value, gives the latest one to new collectors and skips duplicates, which matches what a screen needs. `SharedFlow` is for broadcasting to many collectors with a configurable replay. A `Channel` is a queue where each item is received once. To turn a cold Flow into a StateFlow in a ViewModel, I use `stateIn` with `SharingStarted.WhileSubscribed(5_000)`, which keeps the upstream alive for 5 seconds so a rotation doesn't restart the work, but stops it when the app goes to the background."

**Example:**

```kotlin
val uiState: StateFlow<SearchUiState> = query
    .debounce(300)
    .filter { it.length >= 2 }
    .flatMapLatest { repo.search(it) }
    .map { SearchUiState.Results(it) }
    .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SearchUiState.Idle)
```

| | StateFlow | SharedFlow | Channel |
| --- | --- | --- | --- |
| Current value | Always | Only with replay | No |
| New collectors get | The latest value | `replay` items | Nothing old; each item goes to one receiver |
| Skips equal values | Yes | No | No |
| Use for | UI state | Broadcast events | Work queues, one consumer |

**Common mistake:** Using `StateFlow` for one-time events. It replays its latest value and drops equal ones.

**Follow-ups:**

- *StateFlow vs LiveData?* StateFlow needs an initial value, is pure Kotlin (testable, works in KMP) and has all Flow operators; it isn't lifecycle-aware by itself, so collect it with the lifecycle.

### 2.8 Collecting flows safely in the UI

**In one line:** collect flows only while the screen is visible, using `repeatOnLifecycle` in Views or `collectAsStateWithLifecycle` in Compose.

**Say this in the interview:** "If you collect a flow in `lifecycleScope.launch` directly, it keeps collecting in the background and can update a screen that isn't visible. `repeatOnLifecycle(STARTED)` starts collection when the screen starts and cancels it when it stops. In Compose, `collectAsStateWithLifecycle()` does the same."

**Example:**

```kotlin
// Views
viewLifecycleOwner.lifecycleScope.launch {
    viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { render(it) }
    }
}

// Compose
val state by viewModel.uiState.collectAsStateWithLifecycle()
```

**Common mistake:** Collecting in a bare `lifecycleScope.launch`, which keeps running while the screen is in the background.

**Follow-ups:**

- *Why was `launchWhenStarted` deprecated?* It only paused the coroutine, so upstream producers kept running in the background.

### 2.9 One-off events (navigation, snackbars)

**In one line:** one-off events are best modelled as state that the UI clears after handling, not as fire-and-forget messages.

**Say this in the interview:** "Events sent through a `SharedFlow` are lost if nobody is collecting, and even a `Channel` can lose one in a small window during configuration changes. Google's guidance, which I follow, is to put the event into the UI state, for example `userMessage: String?`, and have the UI call `messageShown()` after displaying it. It survives rotation and process death, and it's easy to test."

**Example:**

```kotlin
data class UiState(val items: List<Item> = emptyList(), val userMessage: Int? = null)
fun messageShown() = _state.update { it.copy(userMessage = null) }
```

**Common mistake:** Sending an important event through a `SharedFlow` with no replay, so it is lost when nobody is collecting.

**Follow-ups:**

- *How do you stop a message showing twice?* Clear it from the UI state once the UI has shown it, for example by calling `messageShown()`.

### 2.10 Flow errors, retry, flattening and backpressure

**In one line:** `catch` handles only upstream errors, `retryWhen` re-runs a failed flow, the `flatMap` variants decide how inner flows overlap, and `buffer`/`conflate` handle slow collectors.

**Say this in the interview:** "The `catch` operator only sees exceptions from operators above it, not from `collect`, so I put work in `onEach` before `catch` and use `launchIn`. For flaky streams I use `retryWhen` with backoff. For flattening, `flatMapLatest` cancels the previous inner flow, which is perfect for search; `flatMapConcat` runs them one by one; `flatMapMerge` runs them in parallel. If the collector is slow, `conflate` keeps only the latest value, and `collectLatest` cancels the old work when a new value arrives."

**Example:**

```kotlin
api.liveScores()
    .retryWhen { cause, attempt -> (cause is IOException && attempt < 3).also { if (it) delay(1000L * (attempt + 1)) } }
    .onCompletion { cause -> log("ended, cause=$cause") }   // runs on success, error or cancellation
    .catch { emit(Scores.Unavailable) }                      // upstream errors only
    .onEach { render(it) }
    .launchIn(viewModelScope)
```

| Operator | Behaviour | Use for |
| --- | --- | --- |
| `flatMapLatest` | Cancels the previous inner flow | Search as you type |
| `flatMapConcat` | One inner flow at a time, in order | Ordered uploads |
| `flatMapMerge` | Several at once (default 16) | Parallel downloads |
| `buffer()` | Producer runs ahead of the collector | Overlap production and rendering |
| `conflate()` | Slow collector gets only the latest | Progress, sensors |

**Common mistake:** Expecting `catch` to handle an exception thrown inside `collect`.

**Follow-ups:**

- *`collect` vs `collectLatest`?* `collect` finishes handling one value before taking the next. `collectLatest` cancels the current handling when a new value arrives.

### 2.11 Shared mutable state

**In one line:** coroutines on `Default` or `IO` run on several threads, so shared mutable state needs atomics, a `Mutex`, or confinement to one thread.

**Say this in the interview:** "If 1,000 coroutines on `Dispatchers.Default` each do `counter++`, you get fewer than 1,000, because the increment isn't atomic. For a single value I use `AtomicInteger` or `MutableStateFlow.update`, which is atomic. For a block that suspends, I use a coroutine `Mutex`, which suspends instead of blocking the thread. A common example is a token cache: ten callers at once should trigger only one refresh."

**Example:**

```kotlin
class TokenCache(private val api: AuthApi) {
    private val mutex = Mutex()
    private var token: Token? = null
    suspend fun get(): Token = mutex.withLock {
        token?.takeIf { !it.isExpired() } ?: api.refresh().also { token = it }
    }
}
```

**Common mistake:** Relying on `@Volatile` to make `counter++` safe.

**Follow-ups:**

- *Why not use `synchronized` around a suspend call?* You can't suspend inside a `synchronized` block. Use a coroutine `Mutex` with `withLock`.

### 2.12 Turning callbacks into coroutines

**In one line:** `suspendCancellableCoroutine` wraps a one-shot callback as a suspend function, and `callbackFlow` wraps a repeating callback as a Flow.

**Say this in the interview:** "Many Android APIs are still callback-based. For a single result I use `suspendCancellableCoroutine` and remove the listener if the coroutine is cancelled. For repeated updates, like location, I use `callbackFlow`: register the listener, send values with `trySend`, and unregister in `awaitClose`, which runs when the collector stops."

**Example:**

```kotlin
fun FusedLocationProviderClient.locations(request: LocationRequest): Flow<Location> = callbackFlow {
    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) { result.lastLocation?.let { trySend(it) } }
    }
    requestLocationUpdates(request, callback, Looper.getMainLooper())
    awaitClose { removeLocationUpdates(callback) }   // required: cleanup when collection stops
}
```

**Common mistake:** Forgetting to unregister the callback when the coroutine is cancelled or the collector stops.

**Follow-ups:**

- *What if the callback can fire more than once?* A continuation can be resumed only once, so use `callbackFlow` for repeated values.

### 2.13 Coroutines vs RxJava

**In one line:** both handle async streams; coroutines use sequential-looking code and structured concurrency, while RxJava uses operator chains and manual disposal.

**Say this in the interview:** "Coroutines replaced RxJava in most Android code because the code reads top to bottom, cancellation is automatic through scopes instead of `CompositeDisposable`, and Jetpack libraries support them directly. The mapping is simple: `Single` becomes a suspend function, `Observable` becomes `Flow`, `BehaviorSubject` becomes `MutableStateFlow`, and `switchMap` becomes `flatMapLatest`. To migrate, I convert the data layer first and use the `kotlinx-coroutines-rx3` adapters at the boundaries."

**Example:**

```kotlin
val user: User = legacyRepo.getUser(id).await()                  // Single -> suspend
val feed: Flow<List<Post>> = legacyRepo.observeFeed().asFlow()   // Observable -> Flow
fun loadUserRx(id: String): Single<User> = rxSingle { newRepo.getUser(id) }   // suspend -> Single
```

**Common mistake:** Translating Rx chains operator by operator when plain suspend code would be simpler.

**Follow-ups:**

- *What is the closest thing to `CompositeDisposable`?* A `CoroutineScope`. Cancelling it cancels all the coroutines started in it.

### 2.14 Testing coroutines

**In one line:** use `runTest` with virtual time, replace `Dispatchers.Main` with a test dispatcher, and test flows with Turbine.

**Say this in the interview:** "`runTest` skips delays with virtual time, so a test with `delay(5_000)` runs instantly. I replace the main dispatcher with `Dispatchers.setMain` in a JUnit rule and inject other dispatchers so they share the same scheduler. `StandardTestDispatcher` queues work until I advance it, which lets me check intermediate states like 'loading'; `UnconfinedTestDispatcher` runs eagerly. For flows I use Turbine's `test { awaitItem() }`."

**Example:**

```kotlin
@Test fun `shows results after debounce`() = runTest {
    val vm = SearchViewModel(FakeSearchRepository())
    vm.uiState.test {
        assertEquals(SearchUiState.Idle, awaitItem())
        vm.onQueryChanged("kotlin")
        advanceTimeBy(301)
        assertTrue(awaitItem() is SearchUiState.Results)
    }
}
```

**Common mistake:** Hardcoding `Dispatchers.IO`, so tests can't control when that work runs.

**Follow-ups:**

- *How do you test code that has a long `delay`?* Run it in `runTest`, which uses virtual time. Make sure the delayed code runs on a test dispatcher.

### Interview questions

1. **What actually happens when a suspend function suspends?** It saves its local variables and position in a continuation object, returns `COROUTINE_SUSPENDED` and frees the thread. When the result is ready, the continuation resumes at the saved point, possibly on another thread. {Medium}
2. **When do you use `launch` and when `async`?** `launch` for work without a result; it returns a `Job`. `async` when you need a result; it returns a `Deferred` you `await`. Use `async` mainly for parallel calls inside `coroutineScope`. {Easy}
3. **Why shouldn't you use `GlobalScope`?** It isn't tied to any lifecycle, so work can leak, can't be cancelled and is hard to test. Use `viewModelScope`, `lifecycleScope`, or an injected application scope with a `SupervisorJob`. {Easy}
4. **What is the difference between `Job` and `SupervisorJob`?** With `Job`, a failing child cancels its parent and siblings. With `SupervisorJob`, children fail independently. `viewModelScope` uses a `SupervisorJob`. {Medium}
5. **Why is catching `Exception` around a suspend call dangerous?** It also catches `CancellationException`, which stops cancellation from working. Rethrow it, or catch only the specific exceptions you expect. {Medium}
6. **StateFlow, SharedFlow or Channel: which do you use for what?** StateFlow for UI state, because it always holds the latest value. SharedFlow to broadcast events to several collectors. Channel when each item must be handled exactly once by one receiver. {Medium}
7. **What does `WhileSubscribed(5_000)` do in `stateIn`?** It keeps the upstream flow running for 5 seconds after the last collector leaves, so a rotation doesn't restart the work, while going to the background stops it. {Medium}
8. **How do you collect a flow safely in an Activity or Fragment?** Inside `repeatOnLifecycle(STARTED)` on the (view) lifecycle owner, or `collectAsStateWithLifecycle()` in Compose, so collection stops when the screen isn't visible. {Easy}
9. **How do you handle one-off events like navigation or a snackbar?** Put them into the UI state and have the UI report when it has handled them. This survives rotation and process death, unlike a SharedFlow event that can be lost. {Medium}
10. **Why didn't my `catch` operator catch an exception thrown in `collect`?** `catch` only handles upstream exceptions. Move the work into `onEach` before `catch` and use `launchIn`, or wrap `collect` in `try/catch`. {Medium}
11. **`flatMapLatest`, `flatMapConcat` or `flatMapMerge`?** `flatMapLatest` cancels the previous inner flow (search). `flatMapConcat` runs them one at a time in order. `flatMapMerge` runs several in parallel. {Medium}
12. **How do you turn a callback API into a Flow?** Use `callbackFlow`: register the listener, send values with `trySend`, and unregister in `awaitClose`. For a single callback, use `suspendCancellableCoroutine`. {Medium}
13. **How would you migrate an RxJava codebase to coroutines?** Convert the data layer to suspend functions and Flow first, use the rx3 adapters (`await`, `asFlow`, `rxSingle`) at boundaries, migrate ViewModels screen by screen, then remove RxJava. {Hard}
14. **How do you test code that uses `delay` and `Dispatchers.Main`?** Use `runTest`, which skips delays with virtual time, replace Main with `Dispatchers.setMain(StandardTestDispatcher())`, inject other dispatchers, and test flows with Turbine. {Medium}
