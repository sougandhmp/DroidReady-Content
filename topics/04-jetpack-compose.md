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

### 4.10 Deeper dive: recomposition traced

```kotlin
@Composable
fun CartScreen(viewModel: CartViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column {
        CartHeader(count = state.items.size)          // (A)
        CartList(items = state.items)                 // (B)
        CheckoutButton(total = state.total, onClick = viewModel::checkout)   // (C)
    }
}
```

The user changes a coupon code, so only `state.total` changes. What recomposes?

- `CartScreen` recomposes, because it read `state`.
- (A) is skipped: `count` is an `Int` equal to last time.
- (B) is skipped only if `items` is stable and equal. With a plain `List<Item>` and strong skipping, it is skipped when it is the same list instance (`===`); if the ViewModel built a new list with the same contents, it recomposes.
- (C) recomposes because `total` changed. `viewModel::checkout` is a stable function reference.

The lesson: keep state granular and stable, and avoid creating new collections in the ViewModel when nothing changed.

### 4.11 Deeper dive: fixing stability, before and after

```kotlin
// Before: unstable. 'tags' is a List interface, 'author' comes from a module without the Compose compiler
data class Post(val id: String, val title: String, val tags: List<String>, val author: Author)

// After, option 1: immutable collections and an annotation
@Immutable
data class PostUi(val id: String, val title: String, val tags: ImmutableList<String>, val authorName: String)

// After, option 2: a stability configuration file for types you do not own
// compose_stability.conf
//   com.example.core.model.Author
//   kotlin.collections.List
```

Option 1 is preferred for UI models: map domain models into small, flat, immutable `...Ui` classes that hold exactly what the screen shows. Verify with the Compose compiler report: `restartable skippable fun PostCard(stable post: PostUi)`.

### 4.12 Deeper dive: plain state holder classes

Not all state belongs in a ViewModel. UI-element logic (expanded panels, a search bar's focus, which tab is selected) can live in a remembered state holder class:

```kotlin
@Stable
class SearchBarState(initialQuery: String) {
    var query by mutableStateOf(initialQuery)
        private set
    var expanded by mutableStateOf(false)
        private set

    fun onQueryChange(q: String) { query = q; expanded = q.isNotEmpty() }
    fun clear() { query = ""; expanded = false }

    companion object {
        val Saver = Saver<SearchBarState, String>(save = { it.query }, restore = { SearchBarState(it) })
    }
}

@Composable
fun rememberSearchBarState(initial: String = "") =
    rememberSaveable(saver = SearchBarState.Saver) { SearchBarState(initial) }
```

This is the same pattern Compose uses for `LazyListState`, `ScaffoldState` and `DrawerState`.

### 4.13 Deeper dive: a custom layout

A layout that places children in rows and wraps when a row is full (like tags):

```kotlin
@Composable
fun SimpleFlowRow(modifier: Modifier = Modifier, spacing: Dp = 8.dp, content: @Composable () -> Unit) {
    Layout(content = content, modifier = modifier) { measurables, constraints ->
        val gap = spacing.roundToPx()
        val placeables = measurables.map { it.measure(constraints.copy(minWidth = 0)) }  // measure each child once
        var x = 0; var y = 0; var rowHeight = 0
        val positions = placeables.map { p ->
            if (x + p.width > constraints.maxWidth) { x = 0; y += rowHeight + gap; rowHeight = 0 }
            IntOffset(x, y).also { x += p.width + gap; rowHeight = maxOf(rowHeight, p.height) }
        }
        layout(constraints.maxWidth, y + rowHeight) {
            placeables.forEachIndexed { i, p -> p.place(positions[i]) }
        }
    }
}
```

Key rule: each child may be measured only once per layout pass. This single-pass measurement is why Compose layouts are fast even when deeply nested. (In production, use the built-in `FlowRow`.)

### 4.14 Deeper dive: animations

| API | Use for | Example |
| --- | --- | --- |
| `animate*AsState` | One value to a target | `animateDpAsState(if (selected) 8.dp else 0.dp)` |
| `AnimatedVisibility` | Enter/exit of content | Expanding an error banner |
| `AnimatedContent` | Switching between contents | Counter text, loading to content |
| `updateTransition` | Several values driven by one state | Card selected: colour, size, elevation together |
| `rememberInfiniteTransition` | Looping | Shimmer placeholders |
| `Animatable` | Imperative, gesture-driven | Swipe to dismiss, fling |
| Shared element transitions | Element moves between screens | List thumbnail to detail image |

```kotlin
val elevation by animateDpAsState(targetValue = if (pressed) 2.dp else 8.dp, label = "elevation")
Card(elevation = CardDefaults.cardElevation(defaultElevation = elevation)) { /* ... */ }
```

Performance tip: animate in the draw phase when you can (`Modifier.graphicsLayer { alpha = animatedAlpha }`) so the animation does not trigger recomposition every frame.

### Interview questions

1. **What triggers recomposition?** A change to a `State` object that was read during composition of that scope. Compose tracks reads through the snapshot system. {Easy}
2. **Why does my composable recompose even though data did not change?** An unstable parameter (e.g. `List`, a class from a non-Compose module, a `var` property), a new lambda instance capturing unstable values, or reading fast-changing state too high up. {Medium}
3. **`LaunchedEffect(Unit)` vs `LaunchedEffect(userId)`?** `Unit` runs once per entry into composition; `userId` restarts the effect (cancelling the old coroutine) whenever the id changes. {Medium}
4. **Where should UI state live: ViewModel or remember?** Screen-level business state in the ViewModel (survives config change, testable). Pure UI element state (expanded, scroll position, focus) in `remember`/state holders. {Easy}
5. **How do you test a composable?** `createComposeRule()`, find with semantics (`onNodeWithText`, `onNodeWithTag`), perform actions, assert. Because composables are stateless, pass fake state directly. {Easy}
