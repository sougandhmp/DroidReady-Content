# Modern platform topics

Interviewers check that you keep up with the platform. Know what changed in recent Android versions, how each change affected your apps, and how you handled it.

### 14.1 Recent Android versions

**In one line:** each release tightens rules for apps that target it, and Play makes you target a recent API level, so these changes are not optional.

**Say this in the interview:** "When we raise the target SDK, I read the behaviour changes for that version and turn each one into a task. Recently that meant: notification permission on 13, foreground service types on 14, edge-to-edge by default on 15, predictive back and the end of the edge-to-edge opt-out on 16, and on 17 the end of the large-screen orientation and resizability opt-out. Play requires new apps and updates to target a recent API level, usually within about a year of each release."

**Example:**

| Version (API) | Changes worth knowing |
| --- | --- |
| Android 17 (37), 2026 | Apps targeting 37 can no longer opt out of orientation and resizability restrictions on large screens (games exempt); expanded AppFunctions so apps expose capabilities to on-device AI; a continuous Canary channel replaces developer previews; a major release in Q2 and a minor SDK release in Q4 |
| Android 16 (36), 2025 | Edge-to-edge opt-out removed; predictive back animations on by default; adaptive layout changes begin on large screens; progress-centric notifications; two SDK releases a year begin |
| Android 15 (35) | Edge-to-edge enforced by default; `dataSync` foreground service time limit; 16 KB page size support required for native code |
| Android 14 (34) | Foreground service types required; partial photo access; implicit intent restrictions; Credential Manager |
| Android 13 (33) | `POST_NOTIFICATIONS` runtime permission; per-app language; Photo Picker; granular media permissions |

**Follow-ups:**

- *How do you plan a target SDK upgrade?* Read the behaviour changes, list the impact per feature, fix and test behind the new target on a branch, run the full regression on the newest and oldest supported versions, then release with a staged rollout.

### 14.2 Edge-to-edge and insets

**In one line:** the app draws behind the status and navigation bars, and you use insets to keep text and buttons out of the system areas.

**Say this in the interview:** "On Android 15 and later, apps are edge-to-edge by default, and on 16 the opt-out is gone. I call `enableEdgeToEdge()`, let `Scaffold` pass inset padding to the content, and use `WindowInsets.safeDrawing` for anything custom. Backgrounds go edge to edge, but text and touch targets stay inside the safe area. For input screens I add `imePadding()` so the field stays above the keyboard. I test with gesture and 3-button navigation, display cutouts in landscape, and the keyboard open."

**Example:**

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

**How it works:** insets are sizes the system reports for the bars, the keyboard and cutouts. `consumeWindowInsets` tells children that the padding has already been applied, so they don't add it twice. In Views, use `ViewCompat.setOnApplyWindowInsetsListener`.

### 14.3 Adaptive layouts

**In one line:** design for any window size, phones, foldables, tablets, desktop windows and ChromeOS, using window size classes rather than device types.

**Say this in the interview:** "I never lock orientation or assume a phone screen; apps targeting the newest SDK can't opt out of resizing on large screens anyway. I pick the layout from the window size class, compact, medium or expanded, and use the Material 3 adaptive components: `NavigationSuiteScaffold` switches between bottom bar and rail, and `ListDetailPaneScaffold` shows list and detail side by side on wide screens. Resizing is a configuration change, so state must live in ViewModels or saved state. I also support keyboard, mouse and stylus, and foldable postures through `WindowInfoTracker`."

**Example:**

```kotlin
val sizeClass = currentWindowAdaptiveInfo().windowSizeClass
if (sizeClass.isWidthAtLeastBreakpoint(WindowSizeClass.WIDTH_DP_EXPANDED_LOWER_BOUND)) {
    ListDetailLayout()
} else {
    SinglePaneLayout()
}
```

**Follow-ups:**

- *Why size classes rather than "is this a tablet"?* A tablet in split-screen can be compact, and a foldable changes size when opened. The window size is what the layout actually has.

### 14.4 Predictive back

**In one line:** the system previews where back will go while the user swipes, so the app must declare back handling up front instead of deciding in `onBackPressed()`.

**Say this in the interview:** "Predictive back needs to know before the gesture finishes whether the app will intercept it. So I use `OnBackPressedDispatcher` callbacks, or `BackHandler` in Compose, and enable them only when I really need to intercept, for example when there are unsaved changes. When no handler is enabled, the system can play the animation that previews the previous screen. `onBackPressed()` is deprecated. For custom animations I use `PredictiveBackHandler`, which gives me the gesture progress."

**Example:**

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

### 14.5 Kotlin Multiplatform (KMP)

**In one line:** KMP shares Kotlin code, usually business logic and data, between Android, iOS and other platforms, while the UI can stay native or use Compose Multiplatform.

**Say this in the interview:** "I'd start small: one shared module with models, networking through Ktor, persistence through Room KMP or SQLDelight, and the domain logic. ViewModel, Lifecycle, Room and DataStore all have multiplatform versions now, so much of an existing Android data layer moves with few changes. UI stays native at first; Compose Multiplatform is an option later. For platform APIs I prefer interfaces with dependency injection, and keep `expect`/`actual` for small platform facts. The non-technical part matters most: iOS team buy-in, debugging on iOS, build time and binary size."

**Example:**

```kotlin
// commonMain
expect fun platformName(): String

class GreetingRepository(private val client: HttpClient) {          // Ktor works on both platforms
    suspend fun greeting(): String = client.get("https://api.example.com/hello").bodyAsText() + " from " + platformName()
}

// androidMain
actual fun platformName(): String = "Android ${Build.VERSION.SDK_INT}"

// iosMain
actual fun platformName(): String = UIDevice.currentDevice.systemName()
```

**How it works:** source sets split the code: `commonMain` is pure Kotlin that compiles for every target, while `androidMain` and `iosMain` hold the `actual` implementations. Common code compiles to JVM bytecode for Android and to a native framework for iOS.

### 14.6 On-device AI

**In one line:** run models on the device for privacy, speed and offline use, with a fallback when the device can't.

**Say this in the interview:** "For generative features on supported devices I'd look at Gemini Nano through the ML Kit GenAI APIs, which run on AICore, and ML Kit for vision tasks like text recognition or barcode scanning. Data stays on the device, there's no network delay and it works offline. But not every device supports it, so I check availability and fall back to a server model or hide the feature. Android 17's AppFunctions also let apps expose their features to on-device assistants."

### 14.7 Accessibility

**In one line:** everyone should be able to use the app with TalkBack, large fonts, switch access and enough contrast.

**Say this in the interview:** "I give meaningful images a `contentDescription` and decorative ones `null`, merge related elements so TalkBack reads one sentence, give custom controls a `Role` and a click label, keep touch targets at least 48 dp, text contrast at least 4.5:1, and support font scaling to 200 percent by using `sp` and avoiding fixed heights. I test with TalkBack on key journeys, the Accessibility Scanner, and automated checks in UI tests."

**Example, before and after:**

```kotlin
// Before: TalkBack reads "4.5", "(120)" separately; the heart has no label; target is 24 dp
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

### 14.8 Resources and localization

**In one line:** let Android pick resources by configuration, use plurals and positional arguments for text, support right-to-left, and let users choose a language per app.

**Say this in the interview:** "All user-visible text lives in resources, so Android can pick `values-fr` for French or `values-night` for dark theme. I never build sentences by concatenation, because languages have different plural rules and word order, so I use `<plurals>` and positional arguments like `%1$s`. Numbers, currencies and dates go through locale-aware formatters. For right-to-left languages I use start and end instead of left and right, and auto-mirror directional icons. On Android 13+ users can pick a per-app language, and AppCompat's `setApplicationLocales` gives an in-app picker that also works on older versions."

**Example:**

```xml
<plurals name="items_in_cart">
    <item quantity="one">%d item in your cart</item>
    <item quantity="other">%d items in your cart</item>
</plurals>
```

```kotlin
val label = pluralStringResource(R.plurals.items_in_cart, count, count)               // Compose
val price = NumberFormat.getCurrencyInstance(Locale.getDefault()).format(amount)      // A$12.50, 12,50 €
AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags("fr"))       // in-app language picker
```

**How it works:** resource qualifiers (`values-fr`, `layout-sw600dp`, `drawable-xxhdpi`, `values-b+es+419`) are matched against the device configuration at runtime. `generateLocaleConfig = true` in Gradle builds the list of supported languages for the system settings. Changing the app locale recreates the Activity, and Compose's `stringResource` updates automatically.

### 14.9 Other modern APIs worth naming

**In one line:** know what each modern Jetpack or platform API is for, even if you haven't used it deeply.

**Example:**

| API | What it's for |
| --- | --- |
| Credential Manager | One API for passwords, passkeys and Sign in with Google |
| Photo Picker | Choosing photos without any storage permission |
| Health Connect | Shared, permissioned health and fitness data |
| Media3 (ExoPlayer) | Audio and video playback, sessions and background playback |
| CameraX | Camera with consistent behaviour across devices |
| Glance | Home-screen widgets written in a Compose style |
| Wear OS, TV, Auto | Same Kotlin stack with form-factor UI libraries |

### Interview questions

1. **What changes when your app targets Android 17 on a tablet?** The app can no longer opt out of orientation and resizability restrictions on large screens (games excepted), so layouts must adapt to any window size and survive resizing without losing state. {Medium}
2. **How do you make an app edge-to-edge safely?** Call `enableEdgeToEdge()`, let `Scaffold` or `WindowInsets.safeDrawing` pad content, use `imePadding()` for input, and test with gesture and 3-button navigation, cutouts and the keyboard. {Easy}
3. **Why does predictive back require changing how you handle back?** The system must know before the gesture ends whether the app will intercept it, so you register callbacks and enable them only when needed, instead of deciding in `onBackPressed()`. {Medium}
4. **Why use window size classes instead of checking for a tablet?** A tablet in split-screen can be compact and a foldable changes size; the window size is what the layout actually has. {Easy}
5. **What would you share first in a KMP project?** Networking, models, persistence and business logic in one module. Keep UI native at first, measure the build and binary-size impact, and involve the iOS team early. {Medium}
6. **How do you test accessibility?** TalkBack walk-throughs of key journeys, Accessibility Scanner, automated checks in UI tests, large font and display sizes, and contrast checks in design review. {Medium}
7. **Why is `"$count items"` a localization bug?** Many languages have several plural forms and different word order. Use `<plurals>` with `pluralStringResource` or `getQuantityString`, and positional arguments. {Easy}
8. **When would you use on-device AI instead of a server model?** When privacy, latency or offline use matters and the task fits a small model; check device support and keep a server fallback. {Medium}
