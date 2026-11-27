# Jetpack Compose

Compose is now the default UI toolkit. Interviewers want to hear that you understand recomposition, who owns state, how side effects work and how to keep screens fast.

### 4.1 The mental model

**In one line:** in Compose, the UI is a function of state: you describe what the screen should look like for the current state, and Compose updates it when the state changes.

**Say this in the interview:** "Instead of finding views and changing them, I write `@Composable` functions that take state and emit UI. When state that a composable read changes, Compose re-runs just that composable, which is called recomposition. Each frame has three phases: composition decides what to show, layout measures and places, and drawing renders. Composables can run often and in any order, so they must be fast and free of side effects."

**Example:**

```kotlin
@Composable
fun Greeting(name: String) {
    Text("Hello, $name")      // when 'name' changes, only this recomposes
}
```

**How it works:** the Compose compiler plugin rewrites composables to track which state they read through the snapshot system. Reading state in a later phase (layout or draw) means a change can skip the earlier phases, which is a key performance trick.

**Common mistake:** Doing side effects such as network calls directly in a composable body.

**Follow-ups:**

- *Name the three phases of a Compose frame.* Composition decides what to show, layout measures and places it, and drawing renders it.

### 4.2 State: remember, rememberSaveable and derivedStateOf

**In one line:** `remember` survives recomposition, `rememberSaveable` also survives rotation and process death, and `derivedStateOf` reduces recompositions from fast-changing inputs.

**Say this in the interview:** "Local variables reset on every recomposition. I use `remember` for transient UI state, `rememberSaveable` when it must survive configuration changes and process death, and `derivedStateOf` when a computed boolean or summary changes less often than the input state it reads."

**`remember`:** Stores an object in the composition slot table across recompositions, but resets on rotation, process death, or when the composable leaves the tree.

```kotlin
var expanded by remember { mutableStateOf(false) }
```

**`rememberSaveable`:** Saves state into the `Bundle` via `SavedStateRegistry`, surviving recomposition, configuration changes, and process death. Custom types need `@Parcelize` or a `Saver`.

```kotlin
var query by rememberSaveable { mutableStateOf("") }
```

**`derivedStateOf`:** Wraps a calculation over fast-changing `State` (such as scroll offset) and notifies readers only when the *output* value changes, preventing per-frame recompositions.

```kotlin
val listState = rememberLazyListState()
val showScrollToTop by remember { derivedStateOf { listState.firstVisibleItemIndex > 0 } }
```

**Common mistake:** Creating state with `mutableStateOf` without `remember`, so it resets on recomposition.

**Follow-ups:**

- *Where should screen state live: `remember` or a ViewModel?* Business and screen state in the ViewModel; pure UI element state (expanded, focus, scroll) in `remember` or a small state holder.

### 4.3 State hoisting and unidirectional data flow

**In one line:** state hoisting moves state up to the caller, so a composable receives its value as a parameter and reports changes through callbacks.

**Say this in the interview:** "I keep most composables stateless: values come down as parameters and events go up as lambdas. That makes them reusable, previewable and easy to test. A common pattern is a 'route' composable that talks to the ViewModel and a stateless 'screen' composable that only renders. For UI logic that doesn't belong in a ViewModel, like a search bar's expanded state, I write a small `@Stable` state-holder class with a `remember` function, the same way Compose provides `LazyListState`."

**Example:**

```kotlin
@Composable
fun SearchRoute(viewModel: SearchViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    SearchScreen(state = state, onQueryChange = viewModel::onQueryChanged)
}

@Composable
fun SearchScreen(state: SearchUiState, onQueryChange: (String) -> Unit) {
    // pure UI: easy to preview and test with fake state
}
```

**Common mistake:** Passing a ViewModel deep into the UI tree, which makes those composables hard to preview, test and reuse.

**Follow-ups:**

- *Where should you hoist state to?* To the lowest common parent of the composables that read or write it.

### 4.4 Side effects

**In one line:** side-effect APIs run non-UI work from composables in a controlled way, tied to the composable's lifecycle.

**Say this in the interview:** "Composables shouldn't do work like network calls directly, because they can run many times. `LaunchedEffect(key)` starts a coroutine when the composable enters, and restarts it when the key changes. `rememberCoroutineScope` gives me a scope for launching from click handlers. `DisposableEffect` is for registering and unregistering listeners. `rememberUpdatedState` lets a long-running effect use the latest lambda without restarting."

**Example:**

| API | Use for |
| --- | --- |
| `LaunchedEffect(key)` | Run suspend work on enter or when the key changes (show a snackbar, start an animation) |
| `rememberCoroutineScope()` | Launch from callbacks, like `onClick` scrolling a list |
| `DisposableEffect(key)` | Register/unregister listeners, with `onDispose` cleanup |
| `SideEffect` | Push Compose state to non-Compose code after each recomposition |
| `rememberUpdatedState` | Use the latest value inside a long-running effect |
| `produceState`, `snapshotFlow` | Convert between Flow/async sources and Compose state |

```kotlin
LaunchedEffect(state.userMessage) {
    state.userMessage?.let { snackbarHostState.showSnackbar(it); viewModel.messageShown() }
}
```

**Common mistake:** Using `LaunchedEffect(Unit)` when the effect depends on a value that can change.

**Follow-ups:**

- *`LaunchedEffect(Unit)` vs `LaunchedEffect(userId)`?* `Unit` runs once per entry into composition; `userId` cancels and restarts the effect whenever the ID changes.

### 4.5 Recomposition, stability and skipping

**In one line:** Compose skips a composable if its parameters haven't changed, but only if it can trust them: their types must be stable.

**Say this in the interview:** "When a parent recomposes, Compose can skip a child whose parameters are equal to last time. That needs stable types: primitives, strings, lambdas, and immutable classes with `val` properties of stable types. A plain `List` is an interface, so Compose can't know it's immutable. Since Kotlin 2.0.20 strong skipping is on by default, which lets composables with unstable parameters skip when the same instance is passed, so stability matters less than before. When a screen recomposes too often, I check the Layout Inspector's recomposition counts and the Compose compiler reports, then use immutable UI models or `ImmutableList`."

**Example:**

```kotlin
// Before: List and a class from a module without the Compose compiler are unstable
data class Post(val id: String, val tags: List<String>, val author: Author)

// After: a flat, immutable UI model
@Immutable
data class PostUi(val id: String, val title: String, val tags: ImmutableList<String>, val authorName: String)
```

**Common mistake:** Adding `@Stable` or `@Immutable` to a class that breaks that promise, which can leave the UI stale.

**Follow-ups:**

- *Why does my composable recompose when nothing changed?* An unstable parameter, a new list instance with the same content, or reading fast-changing state too high in the tree.

### 4.6 Performance techniques

**In one line:** keep composition cheap: stable keys in lists, read fast-changing state as late as possible, and measure in release builds.

**Say this in the interview:** "In lazy lists I always give items a stable `key` and a `contentType`. For scroll-driven animations I read state in the layout or draw phase, using lambda modifiers like `Modifier.offset { }` or `graphicsLayer { }`, so scrolling doesn't recompose. I never do heavy work during composition, and I never write to state I just read. And I measure in release builds with R8 and a baseline profile, because debug Compose is much slower."

**Example:**

```kotlin
LazyColumn {
    items(messages, key = { it.id }, contentType = { it.type }) { MessageRow(it) }
}

Box(Modifier.graphicsLayer { alpha = fadeProvider() })   // read in draw phase: no recomposition
```

**Common mistake:** Measuring Compose performance in a debug build.

**Follow-ups:**

- *Why give lazy list items a `key`?* It keeps each item's identity when the list changes, so remembered state stays with the right item and less work is repeated.

### 4.7 Layouts, modifiers and custom layouts

**In one line:** modifiers decorate a composable in order, and a custom `Layout` measures and places children yourself.

**Say this in the interview:** "Modifier order matters: `padding` then `background` differs from `background` then `padding`. When the built-in layouts aren't enough, I write a `Layout` that measures each child once and places it. Compose's single-pass measurement is why deep nesting is cheap, unlike nested weights in old View layouts. `CompositionLocal` passes ambient values like the theme down the tree, and I use it sparingly."

**Example:**

```kotlin
Layout(content = content) { measurables, constraints ->
    val placeables = measurables.map { it.measure(constraints.copy(minWidth = 0)) }   // measure once each
    layout(constraints.maxWidth, placeables.sumOf { it.height }) {
        var y = 0
        placeables.forEach { it.place(0, y); y += it.height }
    }
}
```

**Common mistake:** Ignoring modifier order, then adding wrapper layouts to fix spacing or click areas.

**Follow-ups:**

- *`padding` then `clickable`, or the reverse?* With `padding` first, the padded space isn't clickable. With `clickable` first, it is.

### 4.8 Navigation

**In one line:** Navigation Compose maps routes to screens; Navigation 3, stable since November 2025, lets you own the back stack as a list of keys.

**Say this in the interview:** "With Navigation Compose I use type-safe routes, which are `@Serializable` classes, and pass IDs as arguments, not objects. Navigation 3 changes the model: the back stack is just a state list that I add to and remove from, and `NavDisplay` renders it. That makes adaptive layouts like list-detail easier and keeps a single source of truth for navigation state."

**Example:**

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

**Common mistake:** Passing whole objects as navigation arguments instead of IDs.

**Follow-ups:**

- *What happens to a screen's ViewModel when it leaves the back stack?* With Navigation Compose, a ViewModel scoped to that destination is cleared when its entry is removed.

### 4.9 Animations

**In one line:** Compose has high-level animation APIs for values, visibility and content changes, and low-level ones for gestures.

**Say this in the interview:** "For one value I use `animate*AsState`, for appearing and disappearing content `AnimatedVisibility`, for switching content `AnimatedContent`, and `updateTransition` when several values follow one state. For gestures like swipe-to-dismiss I use `Animatable`. When I can, I apply animated values in the draw phase with `graphicsLayer` so they don't recompose every frame."

**Example:**

```kotlin
val elevation by animateDpAsState(if (pressed) 2.dp else 8.dp, label = "elevation")
AnimatedVisibility(visible = state.error != null) { ErrorBanner(state.error) }
```

**Common mistake:** Reading a fast-changing animated value during composition when only layout or drawing needs it.

**Follow-ups:**

- *`animate*AsState` vs `Animatable`?* `animate*AsState` follows a target value for you. `Animatable` gives direct control from a coroutine, such as snapping during a gesture.

### 4.10 Interop and migration from Views

**In one line:** `ComposeView` puts Compose inside Views, and `AndroidView` puts a View inside Compose, so you can migrate one screen at a time.

**Say this in the interview:** "I'd never rewrite a whole app at once. I start with new screens in Compose, then migrate leaf components and whole screens one by one, sharing the theme between both systems. Views with no Compose equivalent, like a map or an ad view, stay inside `AndroidView`. I measure performance before and after each step."

**Example:**

```kotlin
// Compose inside a Fragment that is part of a View-based app
class ProfileFragment : Fragment() {
    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View =
        ComposeView(requireContext()).apply {
            setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed)
            setContent { Text("Profile") }
        }
}

// A View inside Compose
@Composable
fun Stars(rating: Float) {
    AndroidView(
        factory = { context -> RatingBar(context) },   // creates the View
        update = { view -> view.rating = rating },     // runs again when state it reads changes
    )
}
```

**Common mistake:** Planning a full rewrite instead of moving screen by screen.

**Follow-ups:**

- *How do you share a theme during migration?* Keep the same colors, type and shapes defined for both systems, and change them together until the Views are gone.

### 4.11 Material 3 theming and dynamic color

**In one line:** `MaterialTheme` supplies colors, typography and shapes down the tree via `CompositionLocal`, and Android 12+ supports wallpaper-driven dynamic color schemes.

**Say this in the interview:** "I centralize colors, typography and shapes in one `AppTheme` composable that wraps `MaterialTheme`. On Android 12 (API 31) and higher, `dynamicDarkColorScheme(context)` and `dynamicLightColorScheme(context)` pull the user's wallpaper palette; on older versions or when brand colors matter, I fall back to static schemes. Components read `MaterialTheme.colorScheme.primary` or `typography.bodyLarge` instead of hardcoded hex colors, so dark mode, high contrast and theming work everywhere."

**Example:**

```kotlin
@Composable
fun AppTheme(darkTheme: Boolean = isSystemInDarkTheme(), dynamicColor: Boolean = true, content: @Composable () -> Unit) {
    val scheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val ctx = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = scheme, typography = AppTypography, content = content)
}
```

**Common mistake:** Hardcoding `Color(0xFF...)` or `16.sp` directly in screens instead of reading `MaterialTheme.colorScheme` and `MaterialTheme.typography`.

**Follow-ups:**

- *How does `MaterialTheme` pass values without threading parameters everywhere?* Through `CompositionLocal`s (`LocalColorScheme`, `LocalTypography`, `LocalShapes`).

### Interview questions

1. **What triggers recomposition?** A change to a `State` object that a composable read during composition. Compose tracks those reads and re-runs only the composables that read the changed state. {Easy}
2. **`remember` vs `rememberSaveable`?** `remember` keeps a value across recompositions only. `rememberSaveable` also saves it in the Bundle, so it survives rotation and process death. {Easy}
3. **When do you use `derivedStateOf`?** When a value is computed from state that changes more often than the result, such as 'show the scroll-to-top button' from the scroll position, so the UI recomposes only when the result changes. {Medium}
4. **What is state hoisting, and why do it?** Moving state up to the caller so a composable takes values as parameters and reports events through lambdas. Stateless composables are reusable, previewable and easy to test. {Easy}
5. **`LaunchedEffect`, `rememberCoroutineScope` or `DisposableEffect`?** `LaunchedEffect` runs suspend work tied to a key; `rememberCoroutineScope` launches from callbacks like `onClick`; `DisposableEffect` registers listeners and cleans up in `onDispose`. {Medium}
6. **Why does my composable recompose even though the data didn't change?** An unstable parameter type, a new list instance with the same contents, or reading fast-changing state too high up. Use immutable UI models, stable keys and lambda modifiers. {Medium}
7. **What does strong skipping mode change?** It's on by default since Kotlin 2.0.20. Composables with unstable parameters can still skip when the same instances are passed, and lambdas are remembered automatically, so stability problems matter less. {Hard}
8. **How do you make a `LazyColumn` perform well?** Stable `key`s and `contentType`s, cheap item composables with precomputed UI models, no heavy work in composition, and testing in release builds with a baseline profile. {Medium}
9. **Why does Modifier order matter?** Each modifier wraps the next, so `padding().background()` pads outside the background, while `background().padding()` pads inside it. {Easy}
10. **How would you migrate a large View-based app to Compose?** Screen by screen: new screens in Compose, then leaf components and existing screens, using `ComposeView` and `AndroidView` for interop and a shared theme, measuring performance as you go. {Medium}
11. **How do you test a composable?** With `createComposeRule()`: set content with fake state, find nodes by text, content description or test tag, perform actions and assert. Stateless composables make this easy. {Easy}
12. **What is different about Navigation 3?** You own the back stack as a state list of keys, and `NavDisplay` renders it, which simplifies adaptive layouts and keeps navigation state in one place. {Medium}
13. **How does Material 3 theming and dynamic color work in Jetpack Compose?** `MaterialTheme` provides `colorScheme`, `typography` and `shapes` down the tree via `CompositionLocal`; on Android 12+ (API 31+), `dynamicLightColorScheme` and `dynamicDarkColorScheme` derive the palette from the user's wallpaper, falling back to static schemes on older devices. {Easy}
