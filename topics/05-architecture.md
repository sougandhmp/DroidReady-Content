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
