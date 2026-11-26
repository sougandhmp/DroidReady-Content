# Modern platform topics

Interviewers check that you keep up. Know what changed in recent Android versions and how it affected your apps.

### 14.1 Recent Android versions: what to mention

| Version (API) | Changes worth knowing |
| --- | --- |
| Android 17 (37), released June 2026 | For apps targeting 37, the opt-out for orientation and resizability restrictions on large screens (sw ≥ 600 dp) is removed (games exempt); expanded AppFunctions so apps expose capabilities to on-device AI; developer previews replaced by a continuous Canary channel; one major release in Q2 with a minor SDK release in Q4 |
| Android 16 (36), 2025 | Edge-to-edge opt-out removed for apps targeting 36; predictive back on by default; adaptive layout changes begin on large screens; progress-centric notifications; two SDK releases per year begin |
| Android 15 (35) | Edge-to-edge enforced by default when targeting 35; `dataSync` foreground service time limit; 16 KB page size support required for native code |
| Android 14 (34) | Foreground service types required; partial photo access; restrictions on implicit intents; credential manager |
| Android 13 (33) | `POST_NOTIFICATIONS` runtime permission; per-app language; Photo Picker; granular media permissions |

Play requires new apps and updates to target a recent API level (typically within about a year of each release), so these changes are not optional.

### 14.2 Edge-to-edge and insets

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            Scaffold { innerPadding ->            // Scaffold applies system bar insets
                Content(Modifier.padding(innerPadding))
            }
        }
    }
}
```

Use `WindowInsets.safeDrawing`, `Modifier.imePadding()` for the keyboard, and `ViewCompat.setOnApplyWindowInsetsListener` in Views.

### 14.3 Adaptive layouts (tablets, foldables, desktop mode, ChromeOS)

- Do not lock orientation or assume phone size; large-screen restrictions are no longer honoured for apps targeting the newest SDK.
- Use **window size classes** (compact / medium / expanded) to switch layouts, and Material 3 adaptive components (`NavigationSuiteScaffold`, `ListDetailPaneScaffold`).
- Handle configuration changes without losing state (resizing a window is a configuration change).
- Support keyboard, mouse and stylus input; foldable postures via `WindowInfoTracker`.

```kotlin
val sizeClass = currentWindowAdaptiveInfo().windowSizeClass
if (sizeClass.isWidthAtLeastBreakpoint(WindowSizeClass.WIDTH_DP_EXPANDED_LOWER_BOUND)) {
    ListDetailLayout()
} else {
    SinglePaneLayout()
}
```

### 14.4 Predictive back

Use `OnBackPressedDispatcher` / Compose `BackHandler` / `PredictiveBackHandler`; `onBackPressed()` override is deprecated. Declare `android:enableOnBackInvokedCallback` where needed and test the back-preview animation.

### 14.5 Kotlin Multiplatform (KMP)

- Share business logic (networking with Ktor, persistence with Room KMP or SQLDelight, ViewModels, domain) between Android and iOS; keep native UI or use **Compose Multiplatform** for shared UI.
- `expect`/`actual` for platform APIs.
- Senior talking points: incremental adoption (start with one shared module), iOS team buy-in, build-time impact, debugging on iOS, binary size.

### 14.6 On-device AI

Be ready to discuss Gemini Nano via ML Kit GenAI APIs / AICore, ML Kit for vision tasks, privacy benefits of on-device inference, and fallbacks when a device does not support it.

### 14.7 Accessibility

- `contentDescription` for meaningful images (null for decorative), `Modifier.semantics { }` / `mergeDescendants`, `Role`s for custom controls.
- Minimum 48 dp touch targets; contrast ratio 4.5:1 for text; support font scaling up to 200% (use `sp`, no fixed heights for text).
- Test with TalkBack, Switch Access, the Accessibility Scanner, and Compose accessibility checks in UI tests.

```kotlin
Row(Modifier.semantics(mergeDescendants = true) {}.clickable(onClickLabel = "Open profile") { open() }) {
    Image(avatar, contentDescription = null)
    Text(name)
}
```

### 14.8 Other modern APIs

Credential Manager (passkeys), Photo Picker, per-app language preferences, notification permission, Health Connect, Media3 (ExoPlayer), CameraX, Glance for widgets, Wear OS / Android TV / Android Auto basics.

### 14.9 Deeper dive: a Kotlin Multiplatform shared module

```text
shared/
  src/commonMain/kotlin/    -> models, repository, use cases, ViewModels (pure Kotlin)
  src/androidMain/kotlin/   -> Android 'actual' implementations
  src/iosMain/kotlin/       -> iOS 'actual' implementations
```

```kotlin
// commonMain
expect fun platformName(): String

class GreetingRepository(private val client: HttpClient) {          // Ktor client works on both platforms
    suspend fun greeting(): String = client.get("https://api.example.com/hello").bodyAsText() + " from " + platformName()
}

// androidMain
actual fun platformName(): String = "Android ${Build.VERSION.SDK_INT}"

// iosMain
actual fun platformName(): String = UIDevice.currentDevice.systemName()
```

Prefer interfaces plus dependency injection over many `expect`/`actual` declarations; keep `expect` for small platform facts. Room, DataStore, ViewModel and Lifecycle now have multiplatform versions, so a lot of an existing Android data layer can move into `commonMain` with few changes.

### 14.10 Deeper dive: handling insets in a real screen

```kotlin
@Composable
fun ChatScreen(messages: List<Message>, onSend: (String) -> Unit) {
    Scaffold(
        topBar = { TopAppBar(title = { Text("Chat") }) },          // draws under the status bar, pads its content
        contentWindowInsets = WindowInsets.safeDrawing
    ) { padding ->
        Column(Modifier.padding(padding).consumeWindowInsets(padding).imePadding()) {
            LazyColumn(Modifier.weight(1f), reverseLayout = true) { items(messages, key = { it.id }) { Bubble(it) } }
            MessageInput(onSend)                                    // stays above the keyboard
        }
    }
}
```

Checklist: backgrounds draw edge to edge, text and touch targets stay inside `safeDrawing`, the input field moves with the keyboard (`imePadding`), the gesture navigation area is not covered by buttons, and display cutouts are handled in landscape.

### 14.11 Deeper dive: predictive back with custom handling

```kotlin
@Composable
fun EditorScreen(hasUnsavedChanges: Boolean, onExit: () -> Unit) {
    var showDiscardDialog by remember { mutableStateOf(false) }

    BackHandler(enabled = hasUnsavedChanges) { showDiscardDialog = true }   // only intercept when needed

    if (showDiscardDialog) {
        AlertDialog(
            onDismissRequest = { showDiscardDialog = false },
            confirmButton = { TextButton(onClick = onExit) { Text("Discard") } },
            dismissButton = { TextButton(onClick = { showDiscardDialog = false }) { Text("Keep editing") } },
            text = { Text("Discard your changes?") }
        )
    }
}
```

The key idea: enable the handler only when you really need to intercept. When it is disabled, the system can play the predictive back animation that previews the previous screen.

### 14.12 Deeper dive: accessibility, before and after

```kotlin
// Before: TalkBack reads "image, 4.5, star, 120" as separate items; the heart has no label; target is 24 dp
Row {
    Image(painterResource(R.drawable.star), contentDescription = null)
    Text("4.5"); Text("(120)")
    Icon(Icons.Default.FavoriteBorder, contentDescription = null, modifier = Modifier.size(24.dp).clickable { like() })
}

// After: one meaningful announcement, a labelled toggle, a 48 dp target
Row(Modifier.semantics(mergeDescendants = true) { contentDescription = "Rated 4.5 stars from 120 reviews" }) {
    Image(painterResource(R.drawable.star), contentDescription = null)
    Text("4.5"); Text("(120)")
}
IconToggleButton(checked = liked, onCheckedChange = { like() }) {          // 48 dp by default
    Icon(if (liked) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
         contentDescription = if (liked) "Remove from favourites" else "Add to favourites")
}
```

### Interview questions

1. **What changes when your app targets Android 17 on a tablet?** The app can no longer opt out of orientation and resizability restrictions on large screens (apart from games), so layouts must adapt to any window size and survive resizing without losing state. {Medium}
2. **How do you make an app edge-to-edge safely?** Call `enableEdgeToEdge()`, let `Scaffold` or `WindowInsets.safeDrawing` pad content, use `imePadding()` for input, and test with gesture and 3-button navigation, cutouts and the keyboard. {Easy}
3. **What would you share in a KMP project first?** Networking, models, persistence and business logic, starting with one module. Keep UI native at first, measure the build and binary-size impact, and get the iOS team involved early. {Medium}
4. **How do you test accessibility?** TalkBack walk-throughs of key journeys, Accessibility Scanner, automated checks in Compose and Espresso tests, large font and display size, and contrast checks in design review. {Medium}
