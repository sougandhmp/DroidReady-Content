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

### Interview questions

1. **What happens when a suspend function suspends?** It saves local state into its continuation object, returns `COROUTINE_SUSPENDED`, and frees the thread. When resumed, the state machine continues from the saved label. {Hard}
2. **`launch` vs `async`?** `launch` returns a `Job` for side effects; `async` returns a `Deferred` result. Use `async` only for parallel decomposition inside `coroutineScope`. {Easy}
3. **Why does `GlobalScope` exist and why avoid it?** It is not bound to any lifecycle, so work leaks and cannot be cancelled or tested. For app-wide work, inject an application-scoped `CoroutineScope` with a `SupervisorJob`. {Easy}
4. **StateFlow vs LiveData?** StateFlow needs an initial value, is pure Kotlin (testable, usable in KMP), supports operators, and is not lifecycle-aware by itself (use `repeatOnLifecycle`). LiveData is lifecycle-aware but Android-only and has a weak operator set. {Medium}
5. **`flowOn` vs `withContext` inside `flow {}`?** You must not call `emit` from a different context inside `flow {}` (it violates context preservation and throws). Use `flowOn` to change the upstream context, or `channelFlow` if you need to emit from multiple coroutines. {Hard}
6. **How do you convert a callback API to Flow?** `callbackFlow { val listener = ...; register(listener); awaitClose { unregister(listener) } }`. For a single callback, `suspendCancellableCoroutine`. {Medium}
