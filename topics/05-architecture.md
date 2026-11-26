# App architecture

The architecture round asks: can you structure an app so many developers can change it safely for years? Google's recommended architecture is **UI layer → (optional) Domain layer → Data layer**, with unidirectional data flow and a single source of truth.

### 5.1 Principles to name explicitly

- **Separation of concerns:** UI renders, ViewModel holds state logic, repositories own data.
- **Single source of truth (SSOT):** one owner per piece of data (usually the local DB); everything else observes it.
- **Unidirectional data flow (UDF):** state flows down, events flow up.
- **Drive UI from data models**, ideally persistent ones, so the app works offline and after process death.
- **SOLID**, especially Dependency Inversion: domain depends on a `Repository` interface, not on Retrofit.

### 5.2 MVVM

```kotlin
data class ArticlesUiState(
    val isLoading: Boolean = false,
    val articles: List<ArticleUi> = emptyList(),
    val errorMessage: String? = null
)

@HiltViewModel
class ArticlesViewModel @Inject constructor(
    private val getArticles: GetArticlesUseCase,
    private val refreshArticles: RefreshArticlesUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(ArticlesUiState(isLoading = true))
    val uiState: StateFlow<ArticlesUiState> = _uiState.asStateFlow()

    init {
        getArticles()
            .onEach { list -> _uiState.update { it.copy(isLoading = false, articles = list.map(Article::toUi)) } }
            .launchIn(viewModelScope)
        refresh()
    }

    fun refresh() = viewModelScope.launch {
        refreshArticles().onFailure { e -> _uiState.update { it.copy(errorMessage = e.message) } }
    }

    fun errorShown() = _uiState.update { it.copy(errorMessage = null) }
}
```

Key points: one immutable state object; `update {}` is atomic (safe from concurrent writes); expose read-only `StateFlow`.

### 5.3 MVI

All user actions are **Intents** (events) sent to a single entry point; a **reducer** produces the new state. Side effects are explicit.

```kotlin
sealed interface CartIntent {
    data class Add(val item: Item) : CartIntent
    data class Remove(val id: String) : CartIntent
    data object Checkout : CartIntent
}

fun onIntent(intent: CartIntent) {
    when (intent) {
        is CartIntent.Add -> _state.update { it.copy(items = it.items + intent.item) }
        is CartIntent.Remove -> _state.update { s -> s.copy(items = s.items.filterNot { it.id == intent.id }) }
        CartIntent.Checkout -> viewModelScope.launch { checkout(_state.value.items) }
    }
}
```

|  | MVVM | MVI |
| --- | --- | --- |
| State | Can be several flows | One state object |
| Inputs | Many public functions | One `onIntent()` / `process()` |
| Strength | Simple, low ceremony | Predictable, easy to log/replay, great for complex screens |
| Weakness | State can scatter across flows | Boilerplate; large reducer if not split |

Senior answer: "Modern MVVM with a single `UiState` and UDF is already close to MVI. I choose explicit MVI for complex, event-heavy screens such as checkout or a chat composer."

### 5.4 Clean Architecture and the domain layer

- **Domain layer** (optional): use cases and pure Kotlin models. No Android imports. Add it when logic is reused across ViewModels or is complex enough to test on its own.
- **Use case** = one business action, often with `operator fun invoke`.
- **Dependency rule:** inner layers know nothing about outer layers. Data implements interfaces defined in domain.
- Don't over-engineer: a use case that only forwards a repository call adds files without value. Say this in interviews; it signals experience.

```kotlin
class GetArticlesUseCase @Inject constructor(
    private val articles: ArticleRepository,
    private val prefs: UserPreferencesRepository
) {
    operator fun invoke(): Flow<List<Article>> =
        combine(articles.observeAll(), prefs.followedTopics) { list, topics ->
            list.filter { it.topic in topics }.sortedByDescending { it.publishedAt }
        }
}
```

### 5.5 Model mapping

Keep separate models per layer: `ArticleDto` (network, JSON annotations) → `ArticleEntity` (Room) → `Article` (domain) → `ArticleUi` (formatted strings, colours). Map with extension functions. This stops a backend change from rippling into the UI.

### 5.6 Modularization

Why: faster incremental builds, enforced boundaries, team ownership, reuse, dynamic delivery.

Typical structure (as in Google's *Now in Android* sample):

```text
:app                       -> wires everything, navigation graph
:feature:home              -> UI + ViewModel for one feature
:feature:settings
:core:data                 -> repositories
:core:database             -> Room
:core:network              -> Retrofit
:core:model                -> pure Kotlin models
:core:designsystem         -> theme, components
:core:testing              -> fakes, test rules
build-logic/convention     -> Gradle convention plugins
```

Rules: feature modules **never depend on other feature modules**; they communicate through navigation routes or `:core` interfaces. Use `api` vs `implementation` correctly (prefer `implementation` to limit recompilation). Share build configuration with **convention plugins**, and versions with a **version catalog** (`libs.versions.toml`).

### 5.7 Deeper dive: one feature through every layer

Feature: "Bookmark an article", which must work offline and show immediately.

**Data layer: DAO and repository.**

```kotlin
@Query("UPDATE articles SET isBookmarked = :on, syncState = 'PENDING' WHERE id = :id")
suspend fun setBookmarked(id: String, on: Boolean)

class OfflineFirstArticleRepository @Inject constructor(
    private val dao: ArticleDao,
    private val syncScheduler: SyncScheduler
) : ArticleRepository {
    override suspend fun setBookmarked(id: String, on: Boolean) {
        dao.setBookmarked(id, on)        // 1. local write: Room's Flow re-emits, UI updates at once
        syncScheduler.requestSync()      // 2. WorkManager pushes PENDING rows when online
    }
}
```

**Domain layer: a use case with a business rule.**

```kotlin
class ToggleBookmarkUseCase @Inject constructor(
    private val articles: ArticleRepository,
    private val account: AccountRepository
) {
    suspend operator fun invoke(id: String, on: Boolean): Result<Unit> {
        if (on && !account.isSignedIn()) return Result.failure(SignInRequired())
        articles.setBookmarked(id, on)
        return Result.success(Unit)
    }
}
```

**UI layer: ViewModel and screen.**

```kotlin
fun onBookmarkClick(id: String, on: Boolean) = viewModelScope.launch {
    toggleBookmark(id, on).onFailure { e ->
        if (e is SignInRequired) _uiState.update { it.copy(showSignInPrompt = true) }
    }
}
```

```kotlin
IconToggleButton(checked = article.isBookmarked, onCheckedChange = { onBookmarkClick(article.id, it) }) {
    Icon(if (article.isBookmarked) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder, contentDescription = "Bookmark")
}
```

Notice there is no manual "update the list in memory" step. The UI observes the database, so the single write in the repository updates every screen that shows the article.

### 5.8 Deeper dive: MVI with a pure reducer and effects

Splitting state changes (pure) from side effects (I/O) makes the logic trivially testable:

```kotlin
data class LoginState(val email: String = "", val password: String = "", val loading: Boolean = false, val error: String? = null)

sealed interface LoginAction {
    data class EmailChanged(val v: String) : LoginAction
    data class PasswordChanged(val v: String) : LoginAction
    data object Submit : LoginAction
    data class Result(val success: Boolean, val error: String? = null) : LoginAction
}

// Pure: same input, same output; no coroutines, no Android
fun reduce(s: LoginState, a: LoginAction): LoginState = when (a) {
    is LoginAction.EmailChanged -> s.copy(email = a.v, error = null)
    is LoginAction.PasswordChanged -> s.copy(password = a.v, error = null)
    LoginAction.Submit -> s.copy(loading = true)
    is LoginAction.Result -> s.copy(loading = false, error = a.error)
}

class LoginViewModel @Inject constructor(private val auth: AuthRepository) : ViewModel() {
    private val _state = MutableStateFlow(LoginState())
    val state = _state.asStateFlow()

    fun dispatch(action: LoginAction) {
        _state.update { reduce(it, action) }
        if (action == LoginAction.Submit) viewModelScope.launch {          // effect
            val r = auth.login(_state.value.email, _state.value.password)
            dispatch(LoginAction.Result(r.isSuccess, r.exceptionOrNull()?.message))
        }
    }
}
```

Test the reducer with plain asserts: `assertEquals(true, reduce(LoginState(), LoginAction.Submit).loading)`.

### 5.9 Deeper dive: modelling errors across layers

Avoid leaking `HttpException` or `SQLiteException` to the UI. Translate at each boundary:

```kotlin
sealed interface DataError {
    data object NoNetwork : DataError
    data object Unauthorized : DataError
    data class Server(val code: Int) : DataError
    data object Unknown : DataError
}

fun Throwable.toDataError(): DataError = when (this) {
    is IOException -> DataError.NoNetwork
    is HttpException -> if (code() == 401) DataError.Unauthorized else DataError.Server(code())
    else -> DataError.Unknown
}

// UI layer maps to user-facing text
fun DataError.message(): Int = when (this) {
    DataError.NoNetwork -> R.string.error_offline
    DataError.Unauthorized -> R.string.error_session_expired
    is DataError.Server -> R.string.error_server
    DataError.Unknown -> R.string.error_generic
}
```

The UI shows a localised string resource and decides behaviour (e.g. go to login on `Unauthorized`). This keeps the domain layer free of Android and of transport details.

### 5.10 Deeper dive: navigating between feature modules

Feature modules must not depend on each other, so `:feature:home` cannot reference `ArticleScreen` in `:feature:article`. Common solutions:

- **Routes in a shared API module.** `:feature:article:api` holds `@Serializable data class ArticleRoute(val id: String)`. Home depends only on the API module; the `:app` module wires routes to screens.
- **Navigation callbacks.** Each feature exposes a function like `fun NavGraphBuilder.homeScreen(onArticleClick: (String) -> Unit)`. The app module connects `onArticleClick` to the article route.

```kotlin
// :feature:home
fun NavGraphBuilder.homeScreen(onArticleClick: (String) -> Unit) {
    composable<HomeRoute> { HomeRoute(onArticleClick = onArticleClick) }
}

// :app
NavHost(navController, startDestination = HomeRoute) {
    homeScreen(onArticleClick = { id -> navController.navigate(ArticleRoute(id)) })
    articleScreen(onBack = navController::popBackStack)
}
```

This keeps features independently buildable and testable, and the app module is the only place that knows the whole graph.

### Interview questions

1. **Why should the repository be the single source of truth instead of the network?** The UI always reads the DB; the network only writes into it. This gives offline support, consistency between screens, and instant display of cached data. {Medium}
2. **How do you share state between two screens?** Through a shared repository (preferred), a ViewModel scoped to a navigation graph, or an activity-scoped ViewModel. Avoid global mutable singletons. {Easy}
3. **What goes in the ViewModel vs a use case?** ViewModel: screen state, mapping to UI models, handling UI events. Use case: business rules reusable across screens. {Easy}
4. **How do you introduce architecture changes in a large legacy app?** Write an ADR (architecture decision record), pilot on one feature, add lint/Konsist rules to enforce boundaries, migrate incrementally, measure build times and crash rates. {Hard}

Layered Android architecture. Events flow down, state flows up.

```text
+--------------------------------+
| UI layer (Compose or Views)    |
| renders UiState, sends events  |
+--------------------------------+
   events |          ^ UiState
          v          |
+--------------------------------+
| ViewModel                      |
| UiState in a StateFlow         |
+--------------------------------+
    calls |          ^ Flow
          v          |
+--------------------------------+
| Domain: use cases (optional)   |
| reusable rules, pure Kotlin    |
+--------------------------------+
    calls |          ^ Flow
          v          |
+--------------------------------+
| Repository                     |
| single source of truth         |
+--------------------------------+
  observe & |        | fetch
      write v        v
+--------------+  +--------------+
| Local source |<-| Remote       |
| Room,        |  | Retrofit,    |
| DataStore    |  | OkHttp       |
+--------------+  +--------------+
```

Network results are saved locally; the UI only ever reads local data.

Read it top to bottom for events and bottom to top for state. The dashed domain layer is optional; the repository always reads from the local store.
