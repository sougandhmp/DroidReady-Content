# Coroutines and Flow

Coroutines are the most-asked senior topic. Know structured concurrency, cancellation, exception propagation and the hot/cold Flow distinction cold.

### 2.1 Core concepts

- **Coroutine:** a suspendable computation. `suspend` functions can pause without blocking the thread; the compiler turns them into a state machine with a `Continuation` parameter (CPS transformation).
- **CoroutineScope:** owns coroutines; cancelling the scope cancels all children. Android gives you `viewModelScope` (cancelled in `onCleared`) and `lifecycleScope` (cancelled on `DESTROYED`).
- **CoroutineContext:** a set of elements: `Job`, `CoroutineDispatcher`, `CoroutineName`, `CoroutineExceptionHandler`.
- **Builders:** `launch` (fire and forget, returns `Job`), `async` (returns `Deferred<T>`, use `await()`), `runBlocking` (blocks a thread; tests and `main` only), `withContext` (switch context and return a result).

### 2.2 Dispatchers

| Dispatcher | Backed by | Use for |
| --- | --- | --- |
| `Dispatchers.Main` | Android main looper | UI updates, light work |
| `Dispatchers.Main.immediate` | Main, no re-dispatch if already on main | Default in `viewModelScope` / `lifecycleScope` |
| `Dispatchers.IO` | Shared pool, 64 threads (or more) | Blocking I/O: disk, network, Room without suspend |
| `Dispatchers.Default` | Pool sized to CPU cores | CPU work: JSON parsing, sorting, diffing |
| `Dispatchers.Unconfined` | Caller thread until first suspension | Rarely; tests |

**Rule:** suspend functions should be **main-safe**. The function that does blocking work switches dispatcher itself, so callers never need to.

```kotlin
class ArticleRepository(
    private val api: ArticleApi,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO  // injectable for tests
) {
    suspend fun fetch(id: String): Article = withContext(ioDispatcher) {
        api.getArticle(id)
    }
}
```

### 2.3 Structured concurrency and Job hierarchy

A child failure cancels the parent and all siblings (with a normal `Job`). With `SupervisorJob` / `supervisorScope`, a child failure does not affect siblings.

```kotlin
// Parallel calls; if one fails, the other is cancelled and the exception propagates
suspend fun loadProfile(): Profile = coroutineScope {
    val user = async { api.user() }
    val posts = async { api.posts() }
    Profile(user.await(), posts.await())
}

// Independent tasks; one failing does not cancel the others
supervisorScope {
    launch { syncContacts() }
    launch { syncPhotos() }
}
```

### 2.4 Cancellation

- Cancellation is **cooperative**. Suspending functions from kotlinx (`delay`, `withContext`, `yield`) check for it. A tight CPU loop must check `isActive` or call `ensureActive()`.
- Cancellation throws `CancellationException`. **Never swallow it.** A blanket `catch (e: Exception)` around a suspend call breaks cancellation; rethrow it.
- Cleanup in `finally`; if cleanup must suspend, use `withContext(NonCancellable)`.

```kotlin
try {
    repository.refresh()
} catch (e: CancellationException) {
    throw e
} catch (e: IOException) {
    _state.update { it.copy(error = e.message) }
}
```

### 2.5 Exception handling

- `launch`: exceptions propagate up to the parent; uncaught ones go to the `CoroutineExceptionHandler` (only works on root coroutines) or crash the app.
- `async`: the exception is stored and rethrown on `await()`. But in a non-supervisor scope it **also** cancels the parent immediately.
- `CoroutineExceptionHandler` is a last resort for logging; it does not let you recover.
- `runCatching` around suspend code also catches `CancellationException`; be careful.

### 2.6 Flow basics: cold streams

A `Flow` is cold: the code in `flow {}` runs again for each collector, only when collected.

```kotlin
fun tickerFlow(periodMs: Long): Flow<Long> = flow {
    var i = 0L
    while (true) { emit(i++); delay(periodMs) }
}

repository.observeArticles()           // Flow<List<Article>> from Room
    .map { list -> list.filter { it.isPublished } }
    .distinctUntilChanged()
    .flowOn(Dispatchers.Default)        // upstream runs on Default
    .catch { emit(emptyList()) }        // catches upstream errors only
    .collect { render(it) }
```

Key operators: `map`, `filter`, `onEach`, `debounce`, `distinctUntilChanged`, `combine` (latest of each), `zip` (pairs in order), `flatMapLatest` (cancel previous inner flow, perfect for search), `flatMapConcat`, `flatMapMerge`, `retry`/`retryWhen`, `buffer`, `conflate`, `stateIn`, `shareIn`.

### 2.7 Hot flows: StateFlow and SharedFlow

|  | StateFlow | SharedFlow | Channel |
| --- | --- | --- | --- |
| Has current value | Yes, always | Optional (replay) | No |
| Replays to new collectors | Latest value | `replay` count | No - each item goes to one receiver |
| Equality conflation | Yes (skips equal values) | No | No |
| Best for | UI state | Broadcast events to many | One-off events to one consumer |

```kotlin
@HiltViewModel
class SearchViewModel @Inject constructor(private val repo: SearchRepository) : ViewModel() {

    private val query = MutableStateFlow("")

    val results: StateFlow<SearchUiState> = query
        .debounce(300)
        .filter { it.length >= 2 }
        .distinctUntilChanged()
        .flatMapLatest { q -> repo.search(q).map<List<Result>, SearchUiState> { SearchUiState.Success(it) } }
        .catch { emit(SearchUiState.Error(it)) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SearchUiState.Idle)

    fun onQueryChanged(q: String) { query.value = q }
}
```

`WhileSubscribed(5_000)` keeps the upstream alive for 5 s after the last collector leaves, so a rotation does not restart the work, but going to the background does stop it.

### 2.8 Collecting safely in the UI

```kotlin
// Views
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { render(it) }
    }
}

// Compose
val state by viewModel.uiState.collectAsStateWithLifecycle()
```

`launchWhenStarted` is deprecated: it only *paused* the coroutine, keeping upstream producers alive.

### 2.9 One-off events (navigation, snackbar)

Options and trade-offs - a common senior discussion:

- **`Channel(Channel.BUFFERED)` + `receiveAsFlow()`:** delivered once, buffered while there is no collector. Can still be lost in a narrow window if the collector is cancelled mid-delivery.
- **`SharedFlow(replay = 0)`:** lost if nobody is collecting.
- **Model events as state** (Google's current guidance): put `userMessage: String?` in `UiState`, and the UI calls `viewModel.messageShown()` after showing it. Survives process death and config change and is testable.

### 2.10 Testing coroutines

```kotlin
@Test
fun `search emits results`() = runTest {
    val vm = SearchViewModel(FakeSearchRepository())
    vm.results.test {                     // Turbine library
        assertEquals(SearchUiState.Idle, awaitItem())
        vm.onQueryChanged("kotlin")
        advanceTimeBy(301)
        assertTrue(awaitItem() is SearchUiState.Success)
    }
}
```

`runTest` uses virtual time (`delay` is skipped). Replace `Dispatchers.Main` with `Dispatchers.setMain(StandardTestDispatcher())` in a JUnit rule, and inject dispatchers so they can be replaced.

### 2.11 Deeper dive: the suspend state machine, step by step

Consider this function:

```kotlin
suspend fun loadUser(id: String): UserProfile {
    val user = api.getUser(id)          // suspension point 1
    val avatar = api.getAvatar(user)    // suspension point 2
    return UserProfile(user, avatar)
}
```

The compiler rewrites it roughly like this (simplified):

```kotlin
fun loadUser(id: String, cont: Continuation<UserProfile>): Any? {
    val sm = cont as? LoadUserSM ?: LoadUserSM(cont)   // holds 'label' and local variables
    when (sm.label) {
        0 -> {
            sm.label = 1
            val r = api.getUser(id, sm)
            if (r == COROUTINE_SUSPENDED) return COROUTINE_SUSPENDED   // thread is free now
            sm.user = r as User
        }
        1 -> sm.user = sm.result as User                               // resumed here later
    }
    // ...label 2 does the same for getAvatar...
}
```

What to say in the interview: one object per call holds the locals, the `label` says where to continue, and returning `COROUTINE_SUSPENDED` releases the thread. That is why thousands of coroutines are cheap compared to threads: a suspended coroutine is just a small object on the heap, not a 1 MB thread stack.

### 2.12 Deeper dive: exception scenarios traced

**Scenario 1: `launch` inside `viewModelScope`.** `viewModelScope` uses a `SupervisorJob`, so a failing child does not cancel siblings. But the exception is still uncaught and crashes the app, because nothing handles it.

```kotlin
viewModelScope.launch { error("boom") }      // crashes the app
viewModelScope.launch { loadFeed() }         // was not cancelled, but the app is already dead
```

Fix: catch inside the coroutine and turn the error into state.

**Scenario 2: `async` in a regular scope.**

```kotlin
coroutineScope {
    val a = async { error("A failed") }
    val b = async { delay(1000); "B" }
    // A fails -> the coroutineScope is cancelled -> b is cancelled -> the exception is rethrown here,
    // even if you never call a.await()
}
```

**Scenario 3: `try/catch` around `launch` does nothing.**

```kotlin
try {
    scope.launch { error("boom") }   // the launch returns immediately; the error happens later
} catch (e: Exception) { /* never reached */ }
```

The exception is thrown inside the coroutine, so the `try` must be inside the `launch` block.

**Scenario 4: `supervisorScope` with `async`.**

```kotlin
supervisorScope {
    val a = async { error("A failed") }
    val b = async { "B" }
    val resultA = runCatching { a.await() }   // failure surfaces only on await
    val resultB = b.await()                   // still succeeds
}
```

### 2.13 Deeper dive: shared mutable state

Coroutines on `Dispatchers.Default` or `IO` run on several threads, so shared state needs protection.

```kotlin
var counter = 0
coroutineScope {
    repeat(1000) { launch(Dispatchers.Default) { counter++ } }
}
println(counter)   // often less than 1000: lost updates
```

Fixes, from simplest:

- `AtomicInteger` / `AtomicReference` for single values.
- `MutableStateFlow.update { }` is atomic (compare-and-set loop).
- `Mutex` for a critical section that suspends. Unlike `synchronized`, it suspends instead of blocking a thread.
- Confine the state to one thread (e.g. `Dispatchers.Default.limitedParallelism(1)`).

```kotlin
class TokenCache(private val api: AuthApi) {
    private val mutex = Mutex()
    private var token: Token? = null

    suspend fun get(): Token = mutex.withLock {
        token?.takeIf { !it.isExpired() } ?: api.refresh().also { token = it }
    }
}
```

Ten callers at once get one refresh call; the other nine wait on the lock and then read the cached token.

### 2.14 Deeper dive: channels, producers and fan-out

A `Channel` is a coroutine-safe queue: `send` suspends when full, `receive` suspends when empty. Each item goes to exactly one receiver.

```kotlin
val jobs = Channel<UploadJob>(capacity = 50)

// producer
launch { photos.forEach { jobs.send(UploadJob(it)) }; jobs.close() }

// 3 workers share the queue (fan-out)
repeat(3) { workerId ->
    launch { for (job in jobs) upload(job, workerId) }   // loop ends when the channel is closed and empty
}
```

Capacity choices: `RENDEZVOUS` (0, sender waits for a receiver), `BUFFERED` (64 by default), `CONFLATED` (keeps only the latest), `UNLIMITED` (risk of running out of memory).

### 2.15 Deeper dive: callbackFlow for a real API

Turning location updates into a Flow that stops listening when the collector goes away:

```kotlin
fun FusedLocationProviderClient.locationFlow(request: LocationRequest): Flow<Location> = callbackFlow {
    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { trySend(it) }   // non-suspending send from a callback
        }
    }
    requestLocationUpdates(request, callback, Looper.getMainLooper())
        .addOnFailureListener { close(it) }            // end the flow with an error
    awaitClose { removeLocationUpdates(callback) }     // runs when the collector is cancelled
}
```

Forgetting `awaitClose` throws an `IllegalStateException`; it is how the library makes sure you clean up.

### 2.16 Deeper dive: backpressure in Flow

If the collector is slower than the producer, the producer suspends by default (each `emit` waits for the collector). Options:

| Operator | Behaviour | Example use |
| --- | --- | --- |
| (none) | Producer waits for the collector | Default, safe |
| `buffer(n)` | Producer runs ahead up to n items in a separate coroutine | Parse while previous item renders |
| `conflate()` | Collector gets only the latest; skips intermediate values | Sensor readings, progress |
| `collectLatest { }` | Cancels the slow collector block when a new value arrives | Re-render on each search result |
| `sample(ms)` / `debounce(ms)` | Time-based dropping | UI updates from fast streams |

```kotlin
downloadProgress()          // emits every few ms
    .conflate()
    .collect { progressBar.progress = it }   // UI only draws the newest value
```

### 2.17 Flow error handling, completion and flattening

**`catch` only sees upstream errors.** It catches exceptions thrown by operators above it, and can emit a fallback value. An exception thrown inside `collect` is downstream and is not caught.

```kotlin
repository.observeFeed()                       // upstream
    .map { it.toUi() }                         // upstream of catch
    .catch { e -> emit(FeedUi.Error(e.toMessage())) }   // handles errors from the two lines above
    .collect { render(it) }                    // an exception here is NOT caught by catch
```

To handle collector errors too, move the work into `onEach` before `catch`, then call `collect()` with no arguments:

```kotlin
flow.onEach { render(it) }.catch { showError(it) }.launchIn(scope)
```

**Exception transparency.** A `flow { }` builder must not catch an exception from `emit` and keep going, and must not emit from another coroutine context (for example inside `withContext`). Use `flowOn` to change the upstream dispatcher, or `channelFlow` when you need to emit from several coroutines.

**Completion and retry.**

```kotlin
api.liveScores()
    .retryWhen { cause, attempt ->
        val retry = cause is IOException && attempt < 3
        if (retry) delay(1_000L * (attempt + 1))   // 1 s, 2 s, 3 s backoff
        retry
    }
    .onStart { emit(Scores.Loading) }
    .onCompletion { cause -> if (cause == null) log("stream ended") }   // runs on success, error or cancellation
    .catch { emit(Scores.Unavailable) }
    .collect { show(it) }
```

`onCompletion` receives `null` on success and the exception otherwise; it does not swallow the exception. A tight loop that never suspends should call `ensureActive()` or use `.cancellable()` so cancellation is noticed.

**Flattening operators compared.** Each turns every upstream value into an inner flow:

| Operator | Inner flows run | When a new value arrives | Typical use |
| --- | --- | --- | --- |
| `flatMapConcat` | One at a time, in order | Waits for the current inner flow to finish | Ordered uploads |
| `flatMapMerge(concurrency)` | Several at once (default limit 16) | Starts another inner flow | Parallel downloads |
| `flatMapLatest` | Only the newest | Cancels the previous inner flow | Search-as-you-type, user ID changes |

**`collect` vs `collectLatest`.** With `collect`, a slow block delays the next value. With `collectLatest`, a new value cancels the block that is still running for the old one, so only the newest value's work completes. Use it when only the latest result matters, such as re-rendering a preview.

### 2.18 Coroutines vs RxJava

Many established apps still contain RxJava, and interviewers ask how the two compare and how you would migrate.

| RxJava | Coroutines / Flow |
| --- | --- |
| `Single<T>` | `suspend fun(): T` |
| `Completable` | `suspend fun()` |
| `Maybe<T>` | `suspend fun(): T?` |
| `Observable<T>` / `Flowable<T>` | `Flow<T>` (cold) |
| `BehaviorSubject` | `MutableStateFlow` |
| `PublishSubject` | `MutableSharedFlow` |
| `subscribeOn(Schedulers.io())` | `flowOn(Dispatchers.IO)` or `withContext(Dispatchers.IO)` |
| `observeOn(AndroidSchedulers.mainThread())` | Collect in a main-thread scope (`viewModelScope`) |
| `CompositeDisposable.clear()` | Scope cancellation (`viewModelScope` is cancelled for you) |
| `switchMap` | `flatMapLatest` |
| `debounce`, `distinctUntilChanged`, `combineLatest` | `debounce`, `distinctUntilChanged`, `combine` |

Why teams move to coroutines: sequential-looking code instead of chains, structured concurrency (no forgotten `dispose()`), first-class support in Jetpack libraries (Room, Paging, DataStore, WorkManager, Lifecycle), and smaller method count. RxJava still has a larger operator set and mature backpressure handling with `Flowable`.

**Migrating incrementally** with the `kotlinx-coroutines-rx3` adapters, one layer at a time:

```kotlin
// Old Rx repository, new coroutine ViewModel
val user: User = legacyRepo.getUser(id).await()                 // Single -> suspend
val feed: Flow<List<Post>> = legacyRepo.observeFeed().asFlow()  // Observable -> Flow

// New coroutine code called from old Rx code
fun loadUserRx(id: String): Single<User> = rxSingle { newRepo.getUser(id) }
```

A common order: convert the data layer to `suspend`/`Flow` first, use adapters at the boundaries, then migrate ViewModels screen by screen, and finally remove the adapters and the RxJava dependency.

### Interview questions

1. **What happens when a suspend function suspends?** It saves local state into its continuation object, returns `COROUTINE_SUSPENDED`, and frees the thread. When resumed, the state machine continues from the saved label. {Hard}
2. **`launch` vs `async`?** `launch` returns a `Job` for side effects; `async` returns a `Deferred` result. Use `async` only for parallel decomposition inside `coroutineScope`. {Easy}
3. **Why does `GlobalScope` exist and why avoid it?** It is not bound to any lifecycle, so work leaks and cannot be cancelled or tested. For app-wide work, inject an application-scoped `CoroutineScope` with a `SupervisorJob`. {Easy}
4. **StateFlow vs LiveData?** StateFlow needs an initial value, is pure Kotlin (testable, usable in KMP), supports operators, and is not lifecycle-aware by itself (use `repeatOnLifecycle`). LiveData is lifecycle-aware but Android-only and has a weak operator set. {Medium}
5. **`flowOn` vs `withContext` inside `flow {}`?** You must not call `emit` from a different context inside `flow {}` (it violates context preservation and throws). Use `flowOn` to change the upstream context, or `channelFlow` if you need to emit from multiple coroutines. {Hard}
6. **How do you convert a callback API to Flow?** `callbackFlow { val listener = ...; register(listener); awaitClose { unregister(listener) } }`. For a single callback, `suspendCancellableCoroutine`. {Medium}
7. **Why didn't my `catch` operator catch an exception thrown in `collect`?** `catch` only handles upstream exceptions. Move the work into `onEach` before `catch` and use `launchIn`, or wrap `collect` in `try/catch`. {Medium}
8. **What replaces `switchMap` and `BehaviorSubject` when moving from RxJava?** `flatMapLatest` and `MutableStateFlow`. Use the `kotlinx-coroutines-rx3` adapters (`await`, `asFlow`, `rxSingle`) to migrate one layer at a time. {Medium}
