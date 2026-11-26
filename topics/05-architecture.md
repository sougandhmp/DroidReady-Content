# App architecture and data flow

The architecture round asks one question: can you structure an app so many developers can change it safely for years? Google's recommended architecture is a UI layer, an optional domain layer and a data layer, with data flowing in one direction.

### 5.1 The layers and the principles behind them

**In one line:** split the app into a UI layer that shows data, an optional domain layer with business rules, and a data layer that owns the data, connected by one-way data flow.

**Say this in the interview:** "I separate the app into layers with clear jobs. The UI layer, Compose screens plus ViewModels, only renders state and forwards user events. The domain layer, which is optional, holds reusable business rules as use cases. The data layer is repositories plus data sources like Room and Retrofit, and it owns the data. Three principles hold it together: separation of concerns, a single source of truth for each piece of data, usually the local database, and unidirectional data flow, where state goes down and events go up. Higher layers depend on interfaces, not implementations, so I can test with fakes."

**Example:**

| Layer | Contains | Knows about |
| --- | --- | --- |
| UI | Composables, ViewModels, UI state classes | Domain or data interfaces |
| Domain (optional) | Use cases, domain models | Repository interfaces only; pure Kotlin |
| Data | Repositories, Room DAOs, Retrofit APIs, DataStore | The outside world |

**Follow-ups:**

- *Why make the database the single source of truth instead of the network?* Every screen reads the same data, it works offline, cached data shows instantly, and network results update every observer at once.

### 5.2 Data flow, step by step

**In one line:** state flows down from the database to the screen, and events flow up from the screen to the database; nothing changes data on the side.

**Say this in the interview:** "State goes down, events go up. The UI only renders a `UiState` and calls ViewModel functions. The ViewModel turns events into use-case or repository calls and turns data into UI state. The repository writes network results into Room and exposes Room as a Flow, so every screen sees the same data, it works offline, and errors arrive as state, not as callbacks."

**Example, the read path** (the user opens the article list):

1. The screen collects `viewModel.uiState` with `collectAsStateWithLifecycle()`.
2. That starts the ViewModel's flow (`stateIn(WhileSubscribed(5_000))`), which collects the use case's flow.
3. The use case combines the articles with the user's followed topics.
4. The repository returns `dao.observeAll().map { it.toDomain() }`; Room emits cached rows at once.
5. In the background, the repository refreshes from the network and writes the result into Room.
6. Room emits again, and the new list flows back up to the screen.

**Example, the write path** (the user taps "bookmark"):

1. The composable calls `onBookmark(id, true)`; it changes nothing itself.
2. The ViewModel launches a coroutine and calls the use case.
3. The use case checks the rules (the user must be signed in) and calls the repository.
4. The repository writes to Room with `syncState = PENDING` and schedules a sync worker.
5. Room emits the updated row, and the icon turns filled through the read path.
6. Later, WorkManager sends the change to the server.

```kotlin
// Repository: the database is the single source of truth
override fun observeArticles(): Flow<List<Article>> = dao.observeAll().map { rows -> rows.map { it.toDomain() } }
override suspend fun refresh() = withContext(io) { dao.upsertAll(api.getArticles().map { it.toEntity() }) }

// ViewModel: one UI state for the screen
val uiState = getFollowedArticles()
    .map { ArticlesUiState(articles = it.map(Article::toUi)) }
    .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), ArticlesUiState(isLoading = true))
```

**How it works:** errors flow down as state too. An `IOException` in Retrofit becomes `DataError.NoNetwork` in the repository, a failure result in the use case, `errorMessage = R.string.offline` in the UI state, and a snackbar on screen; the UI then calls `onErrorShown()`. Each layer is main-safe: the UI and ViewModel run on the main thread, and the data layer switches to `IO` itself.

**Follow-ups:**

- *What breaks unidirectional data flow?* A ViewModel editing its own copy of a list while the screen also reads Room (two sources of truth); a composable calling the repository directly; a repository exposing `MutableStateFlow`; data-layer callbacks into the UI.
- *Why not pass the network response straight to the UI?* Other screens wouldn't see it, it would be lost offline and after process death, and the copies could disagree.

### 5.3 MVVM

**In one line:** in MVVM, a ViewModel exposes the screen's state as an observable stream and offers functions for user actions; the View observes and renders.

**Say this in the interview:** "My ViewModels expose one immutable `UiState` as a `StateFlow` and a few public functions for user actions. Inside, I update state with `_state.update { it.copy(...) }`, which is atomic. The screen collects the state and calls the functions. Keeping one state object avoids inconsistent combinations, like 'loading' and 'error' at the same time."

**Example:**

```kotlin
@HiltViewModel
class ArticlesViewModel @Inject constructor(
    private val getArticles: GetArticlesUseCase,
    private val refreshArticles: RefreshArticlesUseCase
) : ViewModel() {
    private val _uiState = MutableStateFlow(ArticlesUiState(isLoading = true))
    val uiState: StateFlow<ArticlesUiState> = _uiState.asStateFlow()

    init {
        getArticles().onEach { list -> _uiState.update { it.copy(isLoading = false, articles = list.map(Article::toUi)) } }
            .launchIn(viewModelScope)
    }

    fun refresh() = viewModelScope.launch {
        refreshArticles().onFailure { e -> _uiState.update { it.copy(errorMessage = e.toMessage()) } }
    }
}
```

### 5.4 MVI

**In one line:** in MVI, every user action is an intent sent to one entry point, and a pure reducer turns the current state plus the intent into the next state.

**Say this in the interview:** "MVI makes state changes explicit: all actions go through one `onIntent` or `dispatch` function, a pure reducer computes the new state, and side effects like network calls are handled separately. It's predictable, easy to log and replay, and the reducer is trivial to unit-test. The cost is boilerplate. Modern MVVM with a single `UiState` is already close to it, so I choose explicit MVI for complex, event-heavy screens like checkout or a chat composer."

**Example:**

```kotlin
sealed interface LoginAction {
    data class EmailChanged(val v: String) : LoginAction
    data object Submit : LoginAction
    data class Result(val error: String?) : LoginAction
}

fun reduce(s: LoginState, a: LoginAction): LoginState = when (a) {      // pure: no I/O
    is LoginAction.EmailChanged -> s.copy(email = a.v, error = null)
    LoginAction.Submit -> s.copy(loading = true)
    is LoginAction.Result -> s.copy(loading = false, error = a.error)
}
```

| | MVVM | MVI |
| --- | --- | --- |
| Inputs | Several public functions | One `dispatch(action)` |
| State | One or more flows | Exactly one state object |
| Strength | Simple, low ceremony | Predictable, easy to test and debug |
| Weakness | State can spread across flows | More boilerplate |

### 5.5 Clean Architecture, the domain layer and use cases

**In one line:** Clean Architecture keeps business rules in an inner layer that knows nothing about Android or the network; a use case is one business action.

**Say this in the interview:** "The dependency rule is that inner layers don't know about outer ones: the domain defines a `Repository` interface, and the data layer implements it. A use case holds one piece of business logic, like 'get articles for the topics the user follows', usually with `operator fun invoke`. I add a domain layer when logic is shared by several ViewModels or complex enough to test on its own. I don't add use cases that only forward a call to a repository; that's extra files without value."

**Example:**

```kotlin
class GetFollowedArticlesUseCase @Inject constructor(
    private val articles: ArticleRepository,
    private val prefs: UserPreferencesRepository
) {
    operator fun invoke(): Flow<List<Article>> =
        combine(articles.observeAll(), prefs.followedTopics) { list, topics ->
            list.filter { it.topic in topics }.sortedByDescending { it.publishedAt }
        }
}
```

### 5.6 Models and errors between layers

**In one line:** each layer has its own models, and errors are translated at each boundary, so a change in one layer doesn't ripple into the others.

**Say this in the interview:** "I keep separate models: a DTO for the network, an entity for Room, a domain model, and a UI model with formatted text. Mapping is a few extension functions. It means a backend rename doesn't touch my screens. I do the same with errors: an `HttpException` becomes a domain error like `Unauthorized`, and the UI maps that to a string resource and decides what to do, like going to the login screen."

**Example:**

```kotlin
sealed interface DataError { data object NoNetwork : DataError; data object Unauthorized : DataError; data class Server(val code: Int) : DataError }

fun Throwable.toDataError(): DataError = when (this) {
    is IOException -> DataError.NoNetwork
    is HttpException -> if (code() == 401) DataError.Unauthorized else DataError.Server(code())
    else -> DataError.Server(-1)
}
```

### 5.7 Modularization

**In one line:** splitting an app into Gradle modules by feature and by core layer speeds up builds, enforces boundaries and lets teams work in parallel.

**Say this in the interview:** "I organise modules like Google's Now in Android sample: an `:app` module that wires everything together, `:feature:*` modules for each feature, and `:core:*` modules for data, database, network, design system and testing. Feature modules never depend on each other; they navigate through routes or callbacks that the app module connects. Shared build setup lives in convention plugins, versions in a version catalog, and I prefer `implementation` over `api` so changes recompile fewer modules."

**Example:**

```text
:app                     wires features together, owns the navigation graph
:feature:home            UI + ViewModel for one feature
:feature:article
:core:data               repositories
:core:database           Room
:core:network            Retrofit
:core:model              pure Kotlin models
:core:designsystem       theme and shared components
:core:testing            fakes and test rules
build-logic/convention   Gradle convention plugins
```

```kotlin
// :feature:home exposes a navigation entry with a callback; :app connects it
fun NavGraphBuilder.homeScreen(onArticleClick: (String) -> Unit) {
    composable<HomeRoute> { HomeRoute(onArticleClick = onArticleClick) }
}
```

**Follow-ups:**

- *How do you introduce architecture changes in a large legacy app?* Write a short architecture decision record, pilot it on one feature, enforce boundaries with lint or dependency rules, migrate step by step, and measure build times and crash rates.

### Interview questions

1. **Describe the architecture you would use for a new Android app.** UI layer (Compose + ViewModels with one `UiState`), an optional domain layer of use cases, and a data layer of repositories over Room and Retrofit, with the database as the single source of truth, one-way data flow and Hilt for DI. {Medium}
2. **Walk me through what happens, layer by layer, when a user taps "like".** The UI sends the event to the ViewModel, which calls a use case; the use case checks the rules and calls the repository; the repository writes to the database and schedules a sync; the database emits and the new state flows back to the UI. {Medium}
3. **Why should the database, not the network, be the single source of truth?** Every screen sees the same data, the app works offline and after process death, cached data shows instantly, and one write updates every observer. {Medium}
4. **Why shouldn't the ViewModel pass the network response straight to the UI?** It creates a second source of truth: other screens won't see the change, it's lost offline and after process death, and the copies can disagree. {Medium}
5. **MVVM or MVI?** Both work. MVVM with a single `UiState` is simple and enough for most screens; MVI adds a single action entry point and a pure reducer, which pays off on complex, event-heavy screens. {Medium}
6. **What belongs in a ViewModel and what in a use case?** The ViewModel handles screen state, UI mapping and user events. A use case holds business rules that several screens reuse. Skip use cases that just forward a call. {Easy}
7. **How do you share state between two screens?** Through a shared repository (preferred), or a ViewModel scoped to a navigation graph or activity. Avoid global mutable singletons. {Easy}
8. **Why keep separate models per layer?** So a backend change in a DTO doesn't break the UI, the database schema can evolve on its own, and UI models can hold formatted, display-ready values. {Easy}
9. **How do feature modules navigate to each other without depending on each other?** Each feature exposes routes or navigation callbacks, and the app module wires them together; shared route types can live in a small API module. {Hard}
10. **How do you introduce a new architecture into a large legacy app?** Document the decision, pilot it on one feature, add rules that enforce module boundaries, migrate incrementally, and track build times and crash rates. {Hard}
