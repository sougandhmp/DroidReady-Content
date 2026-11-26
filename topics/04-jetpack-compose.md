# Jetpack Compose

Compose is now the default UI toolkit. Seniors must explain recomposition, state ownership, side effects and performance, not just write composables.

### 4.1 Mental model

- UI = f(state). A `@Composable` function describes UI for the current state; when state changes, Compose **recomposes** only the functions that read that state.
- Three phases per frame: **Composition** (what to show) → **Layout** (measure and place) → **Drawing**. Reading state in a later phase skips the earlier ones (a key performance trick).
- Composables can run in any order, in parallel, and very often. They must be **side-effect free** and fast.

### 4.2 State and remember

```kotlin
@Composable
fun Counter() {
    var count by remember { mutableStateOf(0) }          // survives recomposition
    var text by rememberSaveable { mutableStateOf("") }   // also survives rotation + process death
    Button(onClick = { count++ }) { Text("Clicked $count") }
}
```

- `remember`: keeps a value across recompositions; lost when the composable leaves the composition or on config change.
- `rememberSaveable`: stores in the saved-instance Bundle.
- `derivedStateOf`: create state derived from other state that changes less often than its inputs.

```kotlin
val listState = rememberLazyListState()
val showScrollToTop by remember { derivedStateOf { listState.firstVisibleItemIndex > 0 } }
```

Without `derivedStateOf`, every scroll pixel would recompose the reader; with it, only the true/false flip does.

### 4.3 State hoisting and unidirectional data flow

Move state up to the caller; pass the **value down** and **events up**. Stateless composables are reusable, previewable and testable.

```kotlin
@Composable
fun SearchRoute(viewModel: SearchViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    SearchScreen(state = state, onQueryChange = viewModel::onQueryChanged, onItemClick = viewModel::open)
}

@Composable
fun SearchScreen(state: SearchUiState, onQueryChange: (String) -> Unit, onItemClick: (Id) -> Unit) {
    // pure UI, no ViewModel reference - easy to preview and test
}
```

The **Route / Screen split** above is a common pattern: the route wires the ViewModel; the screen is stateless.

### 4.4 Side-effect APIs

| API | Runs | Use for |
| --- | --- | --- |
| `LaunchedEffect(key)` | Coroutine on enter; restarts when key changes | Load data, show snackbar, animations |
| `rememberCoroutineScope()` | Scope tied to composition | Launch from callbacks (e.g. onClick scroll) |
| `DisposableEffect(key)` | On enter, with `onDispose` cleanup | Register/unregister listeners, observers |
| `SideEffect` | After every successful recomposition | Push Compose state to non-Compose code (analytics) |
| `rememberUpdatedState` | - | Capture the latest lambda in a long-running effect without restarting it |
| `produceState` | Coroutine producing State | Turn non-Compose async source into State |
| `snapshotFlow` | - | Turn Compose State into a Flow |

```kotlin
@Composable
fun LifecycleLogger(onEvent: (Lifecycle.Event) -> Unit) {
    val currentOnEvent by rememberUpdatedState(onEvent)
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, e -> currentOnEvent(e) }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
}
```

### 4.5 Stability and skipping

- Compose can **skip** a composable if all its parameters are equal to last time. That needs parameters to be **stable**: primitives, String, lambdas, `@Stable`/`@Immutable` classes, or classes whose properties are all `val` and stable.
- `List<T>` from Kotlin is an interface, so Compose treats it as unstable. Fix with `kotlinx.collections.immutable` (`ImmutableList`), annotate the wrapper with `@Immutable`, or add it to a stability configuration file.
- **Strong skipping mode** (on by default with Kotlin 2.0.20+ Compose compiler): composables with unstable parameters can still skip, using instance equality (`===`) for them, and lambdas are remembered automatically. Stability still matters, but less than before.
- Diagnose with **Compose compiler reports/metrics** and the **Layout Inspector recomposition counts**.

### 4.6 Performance techniques

1. Give `LazyColumn` items a stable `key` and a `contentType`.
2. Defer state reads: pass a lambda `() -> Float` instead of a `Float`, or use `Modifier.offset { IntOffset(...) }` (layout phase) and `Modifier.graphicsLayer { alpha = ... }` (draw phase) so scroll-driven animations skip composition.
3. Avoid heavy work in composition; `remember` expensive calculations with the right keys, or move them to the ViewModel.
4. Do not write to state you just read in the same composition (backwards write → infinite recomposition).
5. Test performance in **release** builds with R8 and a **baseline profile**; debug builds of Compose are much slower.

```kotlin
LazyColumn {
    items(items = messages, key = { it.id }, contentType = { it.type }) { msg ->
        MessageRow(msg)
    }
}
```

### 4.7 Modifiers, layouts and CompositionLocal

- Modifier order matters: `Modifier.padding(16.dp).background(Red)` differs from `.background(Red).padding(16.dp)`.
- Custom layouts with `Layout {}` or `SubcomposeLayout` (used by `BoxWithConstraints`; expensive).
- `CompositionLocal` passes values implicitly down the tree (theme, `LocalContext`). Use sparingly for truly ambient data, not to avoid passing parameters.

### 4.8 Navigation

- **Navigation Compose (Nav2):** `NavHost` + `NavController`, with type-safe routes using `@Serializable` classes since 2.8.
- **Navigation 3 (stable 1.0, Nov 2025):** you own the back stack as a Compose-state list of keys; `NavDisplay` renders it. Easier adaptive layouts (list-detail) and a single source of truth.

```kotlin
@Serializable data object Home : NavKey
@Serializable data class Detail(val id: String) : NavKey

val backStack = rememberNavBackStack(Home)
NavDisplay(
    backStack = backStack,
    onBack = { backStack.removeLastOrNull() },
    entryProvider = entryProvider {
        entry<Home> { HomeScreen(onOpen = { backStack.add(Detail(it)) }) }
        entry<Detail> { key -> DetailScreen(key.id) }
    }
)
```

### 4.9 Interop and migration

- `ComposeView` puts Compose inside Views; `AndroidView` puts Views (MapView, WebView, AdView) inside Compose.
- Migrate screen by screen, leaf-first; share the theme via a Material 3 theme bridge.

### Interview questions

1. **What triggers recomposition?** A change to a `State` object that was read during composition of that scope. Compose tracks reads through the snapshot system. {Easy}
2. **Why does my composable recompose even though data did not change?** An unstable parameter (e.g. `List`, a class from a non-Compose module, a `var` property), a new lambda instance capturing unstable values, or reading fast-changing state too high up. {Medium}
3. **`LaunchedEffect(Unit)` vs `LaunchedEffect(userId)`?** `Unit` runs once per entry into composition; `userId` restarts the effect (cancelling the old coroutine) whenever the id changes. {Medium}
4. **Where should UI state live: ViewModel or remember?** Screen-level business state in the ViewModel (survives config change, testable). Pure UI element state (expanded, scroll position, focus) in `remember`/state holders. {Easy}
5. **How do you test a composable?** `createComposeRule()`, find with semantics (`onNodeWithText`, `onNodeWithTag`), perform actions, assert. Because composables are stateless, pass fake state directly. {Easy}
