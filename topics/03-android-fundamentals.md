# Android fundamentals

These questions check that you understand how Android treats your app: components, lifecycles, processes, threads and what survives what.

### 3.1 The four app components

**In one line:** Android apps are built from four kinds of entry points the system can start: Activities, Services, BroadcastReceivers and ContentProviders.

**Say this in the interview:** "An Activity is a screen the user interacts with. A Service does work without a UI, like playing music. A BroadcastReceiver reacts to system or app events, like the device finishing boot. A ContentProvider shares structured data with other apps, or files through `FileProvider`. All four are declared in the manifest, and since Android 12 any component with an intent filter must say whether it's `exported` to other apps."

**Example:** a music app uses an Activity for the player screen, a foreground Service for playback, a BroadcastReceiver for headphones being unplugged, and a ContentProvider (`FileProvider`) to share a playlist file.

**Common mistake:** Assuming a component runs on its own thread. Service and BroadcastReceiver callbacks normally run on the main thread.

**Follow-ups:**

- *Why must components be in the manifest?* The system, not your code, creates them; the manifest tells it what exists and who may start it.

### 3.2 Activity lifecycle

**In one line:** an Activity moves through `onCreate`, `onStart` (visible), `onResume` (interactive), `onPause`, `onStop` (not visible) and `onDestroy`.

**Say this in the interview:** "`onCreate` is for one-time setup, `onStart` and `onStop` bracket the time the screen is visible, and `onResume` and `onPause` bracket the time it's in the foreground and interactive. I keep `onPause` fast because the next screen waits for it. And I never rely on `onDestroy` to save data, because if the process is killed it isn't called."

**Example, the sequences interviewers ask about:**

| Scenario | Callbacks |
| --- | --- |
| A opens B | A.onPause, B.onCreate, B.onStart, B.onResume, A.onStop |
| Back from B to A | B.onPause, A.onRestart, A.onStart, A.onResume, B.onStop, B.onDestroy |
| Rotation | onPause, onStop, onSaveInstanceState, onDestroy, then onCreate(bundle), onStart, onRestoreInstanceState, onResume |
| Home button | onPause, onStop (state is saved) |
| Dialog-themed activity on top | onPause only |

**Common mistake:** Saving important data only in `onDestroy`.

**Follow-ups:**

- *Is `onDestroy` guaranteed?* No. If the process is killed it never runs, so save important data as soon as it changes.

### 3.3 Fragments and the view lifecycle

**In one line:** a Fragment is a reusable piece of UI inside an Activity, with two lifecycles: the fragment's own and its view's.

**Say this in the interview:** "The common bug with fragments is mixing up the two lifecycles. On the back stack, a fragment keeps its instance but destroys its view, so anything tied to the view, like a binding or a flow collector, must use `viewLifecycleOwner` and be cleared in `onDestroyView`. Fragments shouldn't talk to each other directly; they share a ViewModel scoped to a common owner, or return one-time results with the Fragment Result API. Most modern apps use a single activity that hosts all screens."

**Example:**

```kotlin
private var _binding: FragmentHomeBinding? = null
private val binding get() = _binding!!

override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
    _binding = FragmentHomeBinding.bind(view)
    viewLifecycleOwner.lifecycleScope.launch {                       // view's lifecycle, not the fragment's
        viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            viewModel.state.collect { binding.title.text = it.title }
        }
    }
    setFragmentResultListener("scan") { _, bundle -> viewModel.onScanned(bundle.getString("code")) }
}
override fun onDestroyView() { _binding = null; super.onDestroyView() }   // don't leak the view
```

**How it works:** shared ViewModels use the same owner: `by activityViewModels()`, `by viewModels({ requireParentFragment() })` or `by navGraphViewModels(R.id.checkout_graph)`. The Fragment Result API stores a result until the listener is at least `STARTED`, delivers it once and clears it.

**Common mistake:** Observing in a fragment with `this` as the lifecycle owner, so observers pile up each time the view is recreated.

**Follow-ups:**

- *Why can `commit()` throw after `onSaveInstanceState`?* The transaction would be lost on recreation. Don't commit then; collect with `repeatOnLifecycle` so UI work stops before state is saved.

### 3.4 Configuration changes vs process death

**In one line:** a configuration change (like rotation) recreates the Activity but keeps the process; process death kills everything in memory and restores only what was saved in the Bundle.

**Say this in the interview:** "This is the difference that catches most bugs. On rotation, the Activity is recreated but the ViewModel survives. When the app is in the background, Android may kill the whole process to free memory; when the user comes back, it recreates the screen with only the saved Bundle, so ViewModels and singletons are new and empty. So I keep small user input in `SavedStateHandle` or `rememberSaveable`, real data in Room or DataStore, and pass IDs, not objects, between screens. I test it with 'Don't keep activities' or `adb shell am kill`."

**Example:**

| Where data lives | Survives rotation | Survives process death | Good for |
| --- | --- | --- | --- |
| Activity fields | No | No | Nothing important |
| ViewModel | Yes | No | Loaded data, screen state |
| `SavedStateHandle`, `rememberSaveable` | Yes | Yes | Small input: IDs, text, step number |
| Room, DataStore, files | Yes | Yes | Real data |

```kotlin
@HiltViewModel
class SignUpViewModel @Inject constructor(private val state: SavedStateHandle) : ViewModel() {
    val email = state.getStateFlow("email", "")
    fun onEmailChange(value: String) { state["email"] = value }   // restored after process death
}
```

**Common mistake:** Testing only rotation and believing that proves state survives process death.

**Follow-ups:**

- *Why is the saved Bundle size limited?* It crosses Binder to the system, and the transaction buffer is about 1 MB per process; too much causes `TransactionTooLargeException`. Save IDs, not lists.

### 3.5 How ViewModel survives rotation

**In one line:** the Activity keeps its `ViewModelStore` across configuration changes and clears it only when the Activity finishes for good.

**Say this in the interview:** "`ComponentActivity` hands its `ViewModelStore` to the new instance during a configuration change, so `by viewModels()` returns the same object. When the Activity really finishes, `onCleared()` is called and `viewModelScope` is cancelled. Because the ViewModel outlives the Activity, it must never hold a reference to an Activity, Fragment, View or Context, or it leaks them."

**Example:**

```kotlin
class CounterViewModel : ViewModel() {
    var launches = 0

    override fun onCleared() {
        Log.d("Counter", "cleared")
    }
}

class CounterActivity : ComponentActivity() {
    private val viewModel: CounterViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel.launches++
        Log.d("Counter", "activity ${hashCode()}, viewModel ${viewModel.hashCode()}, ${viewModel.launches}")
    }
}
```

Rotate the screen: the log shows a different Activity hash, the same ViewModel hash and a higher count. Call `finish()`, and `onCleared()` runs.

**Common mistake:** Passing an Activity or View into a ViewModel, which keeps it alive after the screen is recreated.

**Follow-ups:**

- *What if I need a Context in a ViewModel?* Use `AndroidViewModel`'s application context, or better, inject a repository that hides the Context.

### 3.6 Lifecycle-aware components

**In one line:** lifecycle-aware components start and stop themselves by observing a `Lifecycle`, instead of the screen remembering to do it.

**Say this in the interview:** "A `Lifecycle` has states like `STARTED` and events like `ON_STOP`. A `DefaultLifecycleObserver` can open the camera on start and close it on stop by itself. In Compose I use `LifecycleStartEffect` with `onStopOrDispose`. For app-wide state, `ProcessLifecycleOwner` tells me when the whole app goes to the background or comes back, which I use to connect and disconnect a socket."

**Example:**

```kotlin
ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner) = socket.connect()     // app came to foreground
    override fun onStop(owner: LifecycleOwner) = socket.disconnect()   // last activity stopped
})
```

**Common mistake:** Starting something in one callback and forgetting to stop it in the matching one.

**Follow-ups:**

- *What does adding an observer to an already resumed lifecycle do?* The observer receives the earlier events, such as `onCreate`, `onStart` and `onResume`, so it catches up to the current state.

### 3.7 Intents, PendingIntents and App Links

**In one line:** an Intent describes an action to perform; an explicit Intent names the target class, an implicit one names an action and lets the system find an app.

**Say this in the interview:** "I use explicit intents inside my app and implicit ones like `ACTION_VIEW` to hand off to other apps. A PendingIntent is a token that lets another app, like the notification shade, run an intent as my app; since Android 12 it must be marked `FLAG_IMMUTABLE` or `FLAG_MUTABLE`. For links, a normal deep link may show a chooser, but a verified App Link opens my app directly: I add `autoVerify` to the intent filter and host `assetlinks.json` with the signing certificate fingerprint on my domain."

**Example:**

```kotlin
startActivity(Intent(this, CheckoutActivity::class.java))                       // explicit
startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=Opera+House")))   // implicit
```

**Common mistake:** Using a mutable PendingIntent with an implicit intent, which lets another app change where it goes.

**Follow-ups:**

- *Why does my App Link open a chooser?* Verification failed, most often because `assetlinks.json` lists the upload or debug key instead of Play's app signing key. Check with `adb shell pm get-app-links <package>`.

### 3.8 Tasks, back stack and launch modes

**In one line:** a task is a stack of activities the user navigates through; launch modes and intent flags change how new activities join it.

**Say this in the interview:** "`standard` creates a new instance every time; `singleTop` reuses the activity if it's already on top and calls `onNewIntent`; `singleTask` keeps one instance per task and clears what's above it; `singleInstance` puts it alone in its own task. In a modern single-activity app, these matter mainly for deep links and notifications, where `singleTop` avoids stacking duplicate screens."

**Example:** what happens to a back stack (the top is on the right):

| Stack before | Start | Launch mode of the started activity | Stack after |
| --- | --- | --- | --- |
| A, B | B | `standard` | A, B, B |
| A, B | B | `singleTop` | A, B (`onNewIntent`) |
| A, B, C | B | `singleTask`, same task affinity | A, B (`onNewIntent`, C is removed) |

```kotlin
fun orderIntent(context: Context, orderId: String): Intent =
    Intent(context, OrdersActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)   // reuse it if it is already on top
        .putExtra("orderId", orderId)

class OrdersActivity : ComponentActivity() {
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)                            // so getIntent() returns the new one
        intent.getStringExtra("orderId")?.let(::openOrder)
    }

    private fun openOrder(id: String) { /* show the order */ }
}
```

**Common mistake:** Choosing `singleTask` to stop duplicate screens without checking what it removes from the back stack.

**Follow-ups:**

- *What does `onNewIntent` do?* It delivers a new intent to an existing activity instance. Handle it, because `getIntent()` keeps returning the old one unless you call `setIntent()`.

### 3.9 The main thread, Looper and Handler

**In one line:** the main thread runs a `Looper` that processes a queue of messages: input events, lifecycle callbacks and frame drawing.

**Say this in the interview:** "Everything UI-related runs on the main thread, one message at a time. If I block it, input stops responding; about 5 seconds of that gives an ANR, and even 16 ms per frame causes visible jank at 60 Hz. A `Handler` posts work to a specific looper's queue, and `Dispatchers.Main` uses this under the hood. A `postDelayed` runnable that captures an Activity is a classic leak, so I prefer coroutines tied to a lifecycle."

**Example:**

```kotlin
fun showReportWithHandler(textView: TextView) {
    val mainHandler = Handler(Looper.getMainLooper())
    thread {
        val report = buildReport()                    // slow work off the main thread
        mainHandler.post { textView.text = report }   // touch the UI on the main thread
    }
}

// The same with a coroutine, which is cancelled when the lifecycle is destroyed
fun LifecycleOwner.showReport(textView: TextView) {
    lifecycleScope.launch {
        textView.text = withContext(Dispatchers.Default) { buildReport() }
    }
}
```

**Common mistake:** Thinking `Handler.post` runs work in the background. It runs on the handler's looper, often the main thread.

**Follow-ups:**

- *What is a `Looper`?* It runs a thread's message loop, taking messages from a queue one at a time. A thread can have at most one.

### 3.10 Context

**In one line:** a `Context` is the app's handle to the system: resources, services, files and starting components.

**Say this in the interview:** "There are two main kinds. The application context lives as long as the process, so it's safe for singletons, Room or DataStore. An Activity context has the theme and is needed for UI, dialogs and inflation, but it dies with the screen, so storing it in anything long-lived leaks the whole Activity."

**Example:**

```kotlin
// Long-lived: keep only the application context
class FileStore(context: Context) {
    private val appContext = context.applicationContext

    fun cachedFile(name: String) = File(appContext.cacheDir, name)
}

// UI: use the Activity, which carries the theme and the window
fun confirmDelete(activity: Activity) {
    AlertDialog.Builder(activity).setMessage("Delete this item?").show()
}
```

**Common mistake:** Using the application context to inflate themed UI or show a dialog.

**Follow-ups:**

- *Can you keep a reference to the application context in a singleton?* Yes. It lives as long as the process, so it doesn't leak a screen.

### 3.11 Binder, IPC and Parcelable

**In one line:** Binder is Android's mechanism for calls between processes, and `Parcelable` is the fast format for sending data across it.

**Say this in the interview:** "Each app runs in its own process, so even `startActivity` is a Binder call to the system server. Data crossing Binder is written to a `Parcel`, which is why intent extras must be `Parcelable` or primitives; I generate it with `@Parcelize`. Binder calls are synchronous by default, so a slow system service called on the main thread can cause an ANR. For my own cross-app APIs I'd use a bound service with AIDL or a `Messenger`."

**Example:**

```kotlin
@Parcelize   // needs the kotlin-parcelize Gradle plugin
data class SearchFilter(val query: String, val maxPrice: Int) : Parcelable

fun openResults(context: Context, filter: SearchFilter) {
    context.startActivity(
        Intent(context, ResultsActivity::class.java).putExtra("filter", filter)
    )
}

class ResultsActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val filter = IntentCompat.getParcelableExtra(intent, "filter", SearchFilter::class.java)
    }
}
```

**Common mistake:** Passing large objects or bitmaps in intent extras. Pass an ID and load the data instead.

**Follow-ups:**

- *Parcelable vs Serializable?* Parcelable is explicit and fast; Serializable uses reflection, is slower and creates more garbage.

### 3.12 Services

**In one line:** a Service runs work without a UI; it can be started, bound, or run in the foreground with a notification.

**Say this in the interview:** "A started service runs until it stops itself, but since Android 8 background services are stopped soon after the app leaves the foreground, so for background work I use WorkManager instead. A foreground service shows a notification and is for ongoing work the user knows about, like music or navigation; since Android 14 it must declare a type. A bound service offers a call interface to clients while they're bound, through a `Binder` in the same app or AIDL across apps. Note that service callbacks run on the main thread."

**Example:**

```kotlin
class PlayerService : Service() {
    inner class LocalBinder : Binder() { fun service() = this@PlayerService }
    override fun onBind(intent: Intent): IBinder = LocalBinder()
}
```

**Common mistake:** Assuming a Service has its own background thread.

**Follow-ups:**

- *When do you bind to a service instead of starting it?* When a client needs to call it and use the results while connected. A bound-only service stops when its clients unbind.

### 3.13 BroadcastReceivers and ContentProviders

**In one line:** a BroadcastReceiver reacts to broadcast events, and a ContentProvider exposes data or files to other apps through `content://` URIs.

**Say this in the interview:** "Since Android 8, most implicit broadcasts can't be received by manifest-declared receivers, so I register receivers in code while they're needed, and since Android 14 I must say whether they're exported. `onReceive` runs on the main thread and must be quick; longer work goes to WorkManager. For sharing files I use `FileProvider`, which gives the other app a `content://` URI with temporary permission instead of a file path."

**Example:**

```kotlin
val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", pdfFile)
startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
    type = "application/pdf"; putExtra(Intent.EXTRA_STREAM, uri); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
}, "Share invoice"))
```

**Common mistake:** Starting long asynchronous work in `onReceive`, where the process may be killed once it returns.

**Follow-ups:**

- *Why can a `ContentProvider` affect startup time?* Providers declared by the app are created at process start, before `Application.onCreate`.

### 3.14 Permissions

**In one line:** dangerous permissions are granted by the user at runtime, so you ask in context and handle refusal.

**Say this in the interview:** "There are normal permissions granted at install, runtime permissions the user grants, and special ones like exact alarms. I request runtime permissions at the moment they're needed, using the Activity Result API, explain the value if the user declined before, and keep the app usable without them. I also prefer APIs that need no permission, like the Photo Picker instead of storage access."

**Example:**

```kotlin
val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
    if (granted) startCamera() else showWhyCameraHelps()
}
Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) { Text("Scan receipt") }
```

**Common mistake:** Asking for every permission at first launch, before the user knows why.

**Follow-ups:**

- *What if the user keeps denying a permission?* The system may stop showing the dialog. Explain what is unavailable, offer a way to Settings and keep the rest of the app working.

### 3.15 Notifications

**In one line:** every notification belongs to a channel, and apps targeting Android 13+ need the `POST_NOTIFICATIONS` runtime permission.

**Say this in the interview:** "Since Android 8, notifications belong to channels, and the user controls each channel's importance and sound. Since Android 13, posting needs a runtime permission, so I ask in context, for example after the user turns on order alerts. I use the right style, like `MessagingStyle` for chats with direct reply, group related notifications, and use a stable ID so an update replaces the old notification."

**Example:**

```kotlin
val notification = NotificationCompat.Builder(context, "orders")
    .setSmallIcon(R.drawable.ic_box)
    .setContentTitle("Your order has shipped")
    .setContentIntent(openOrderIntent)
    .setAutoCancel(true)
    .build()
NotificationManagerCompat.from(context).notify(orderId.hashCode(), notification)
```

**Common mistake:** Posting without a channel, or without the runtime permission, and wondering why nothing appears.

**Follow-ups:**

- *Can an app change a channel's importance after creating it?* Not by creating it again. After that, the user controls its importance in system settings.

### 3.16 The View system: RecyclerView and custom views

**In one line:** RecyclerView shows long lists by recycling a small number of item views, and a custom view draws itself by overriding `onMeasure` and `onDraw`.

**Say this in the interview:** "Many apps still have Views. RecyclerView creates only the views that fit on screen and reuses them as you scroll; an Adapter binds data, a ViewHolder holds one item's views, and a LayoutManager positions them. I use `ListAdapter` with `DiffUtil`, which diffs lists in the background and updates only changed rows, instead of `notifyDataSetChanged`. For custom views I override `onMeasure` to choose a size and `onDraw` to draw, allocate `Paint` objects once, and call `invalidate()` to redraw or `requestLayout()` when the size changes."

**Example:**

```kotlin
object Diff : DiffUtil.ItemCallback<ArticleUi>() {
    override fun areItemsTheSame(old: ArticleUi, new: ArticleUi) = old.id == new.id   // same item?
    override fun areContentsTheSame(old: ArticleUi, new: ArticleUi) = old == new      // same data?
}
adapter.submitList(state.articles)
```

**Common mistake:** Calling `notifyDataSetChanged` for every change, or creating objects such as `Paint` inside `onDraw`.

**Follow-ups:**

- *`invalidate()` vs `requestLayout()`?* `invalidate()` asks for a redraw. `requestLayout()` asks for measuring and layout again when size or position may change.
- *Why use `ConstraintLayout` in Views, and what is `ConcatAdapter`?* `ConstraintLayout` keeps complex View layouts flat (avoiding nested `LinearLayout` weights) with `Guideline` and `Barrier` helpers; `ConcatAdapter` combines multiple `RecyclerView.Adapter`s sequentially (e.g. header + list + footer) without one giant adapter.

### Interview questions

1. **Is `onDestroy` always called?** No. If the process is killed it isn't, so save important data as soon as it changes, not in `onDestroy`. {Easy}
2. **What survives a rotation, and what survives process death?** Rotation keeps the ViewModel but recreates the Activity. Process death keeps only the saved Bundle (`SavedStateHandle`, `rememberSaveable`) and persistent storage; ViewModels and singletons are gone. {Medium}
3. **Why is the `onSaveInstanceState` Bundle size limited?** It crosses Binder to the system, whose transaction buffer is about 1 MB per process; too much data throws `TransactionTooLargeException`. Save IDs, not objects. {Medium}
4. **Why must fragments use `viewLifecycleOwner` for UI work?** A fragment on the back stack keeps its instance but destroys its view. Collecting with the fragment's own lifecycle keeps updating a destroyed view and leaks it. {Medium}
5. **How do two fragments share data?** Through a ViewModel scoped to a common owner (activity, parent fragment or navigation graph) for ongoing state, or the Fragment Result API for a one-time result. Never by referencing each other. {Easy}
6. **How does a ViewModel survive rotation?** The Activity passes its `ViewModelStore` to the new instance during a configuration change, and clears it only when the Activity finishes for good. {Medium}
7. **How do you detect that the whole app went to the background?** Observe `ProcessLifecycleOwner`: `ON_STOP` fires when the last activity stops and `ON_START` when the app returns. {Medium}
8. **What is a PendingIntent, and why must you set mutability?** A token that lets another app run an intent as your app, such as a notification action. Since Android 12 you must choose `FLAG_IMMUTABLE` or `FLAG_MUTABLE`; prefer immutable for security. {Medium}
9. **Your App Link opens a chooser instead of your app. Why?** Verification failed, usually because `assetlinks.json` lists the wrong certificate fingerprint (debug or upload key instead of Play's signing key), or the file is redirected or not on HTTPS. {Medium}
10. **What causes an ANR?** Blocking the main thread: about 5 seconds without responding to input, or a broadcast receiver or service that takes too long. Typical causes are disk or network on the main thread, lock contention and slow Binder calls. {Medium}
11. **Application context or Activity context?** Application context for anything long-lived (singletons, Room). Activity context for UI work like dialogs and inflation, and never stored beyond the screen's life. {Easy}
12. **Parcelable or Serializable?** Parcelable, generated with `@Parcelize`: it's explicit and fast. Serializable uses reflection and is slower. {Easy}
13. **Started service, bound service or foreground service?** Started runs until stopped (rare now; use WorkManager). Bound offers an interface to connected clients. Foreground shows a notification for ongoing, user-visible work like music. {Easy}
14. **Why did my notification not show on Android 13?** The app lacks the `POST_NOTIFICATIONS` permission, or its channel is missing or turned off by the user. {Easy}
15. **`ListAdapter` with `DiffUtil` or `notifyDataSetChanged()`?** `ListAdapter` diffs the lists in the background and updates only changed items, with animations. `notifyDataSetChanged()` rebinds everything and loses animations. {Easy}
16. **What's the difference between `invalidate()` and `requestLayout()` in a custom view?** `invalidate()` only redraws (`onDraw`). `requestLayout()` re-measures and re-lays out, for when the size or position changes. {Medium}
17. **When would you use `ConstraintLayout` over nested `LinearLayout`s, and what are `Barrier`s?** `ConstraintLayout` flattens complex View hierarchies to avoid double-measurement from nested weights; a `Barrier` dynamically aligns to the widest or tallest of a group of referenced views (useful for localized labels). {Easy}
18. **What is the difference between Back and Up navigation, and when do you use `TaskStackBuilder`?** Back returns in chronological history across apps; Up navigates within your app's hierarchy. When launching a deep screen from a notification, use `TaskStackBuilder` to build a synthetic back stack so Up/Back returns to the parent screen instead of exiting. {Medium}
