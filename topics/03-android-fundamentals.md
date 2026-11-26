# Android fundamentals

Seniors are expected to explain how the OS treats your app: processes, lifecycles, and what survives what.

### 3.1 The four components

| Component | Purpose | Example |
| --- | --- | --- |
| Activity | A screen / entry point with UI | `MainActivity` hosting a Compose `NavHost` |
| Service | Work without UI | Music playback as a foreground service |
| BroadcastReceiver | React to system or app events | Boot completed, locale changed |
| ContentProvider | Share structured data across apps | Contacts, `FileProvider` for sharing images |

All are declared in `AndroidManifest.xml`. Since Android 12, any component with an intent filter must set `android:exported` explicitly.

### 3.2 Activity lifecycle

`onCreate` → `onStart` (visible) → `onResume` (foreground, interactive) → `onPause` (losing focus; keep it fast) → `onStop` (not visible) → `onDestroy`.

Scenarios interviewers ask:

- **A opens B:** A.onPause → B.onCreate → B.onStart → B.onResume → A.onStop. (A stops only after B is visible.)
- **Back from B:** B.onPause → A.onRestart → A.onStart → A.onResume → B.onStop → B.onDestroy.
- **Rotation (default):** onPause → onStop → onSaveInstanceState → onDestroy → onCreate(bundle) → onStart → onRestoreInstanceState → onResume.
- **Dialog-themed activity on top / multi-window focus loss:** only onPause.
- **Home button:** onPause → onStop (onSaveInstanceState called).

### 3.3 Fragment lifecycle and the view lifecycle trap

Fragments have two lifecycles: the fragment's and its **view's** (`onCreateView` to `onDestroyView`). A fragment on the back stack keeps its instance but destroys its view.

```kotlin
private var _binding: FragmentHomeBinding? = null
private val binding get() = _binding!!

override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
    _binding = FragmentHomeBinding.bind(view)
    viewLifecycleOwner.lifecycleScope.launch {           // NOT lifecycleScope
        viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            viewModel.state.collect { binding.title.text = it.title }
        }
    }
}

override fun onDestroyView() { _binding = null; super.onDestroyView() }   // avoid leaking the view
```

### 3.4 Configuration changes vs process death

This is a favourite senior question. Know exactly what survives what.

| Mechanism | Survives rotation | Survives process death | Size / type |
| --- | --- | --- | --- |
| Local variables in Activity | No | No | Anything |
| `ViewModel` | Yes | **No** | Anything |
| `SavedStateHandle` / `onSaveInstanceState` / `rememberSaveable` | Yes | Yes | Small, Parcelable (< \~500 KB Binder limit; aim for a few KB) |
| Room / DataStore / files | Yes | Yes | Large, persistent |

**Process death:** when your app is in the background, the OS may kill the process to reclaim memory. When the user returns, Android recreates the task's activities and hands back the saved Bundles. Your singletons and ViewModels are gone. Test it with *Developer options → Don't keep activities* or `adb shell am kill <package>` while backgrounded.

```kotlin
@HiltViewModel
class CheckoutViewModel @Inject constructor(
    private val savedState: SavedStateHandle,
    private val repo: CartRepository
) : ViewModel() {
    // Survives process death: the cart id and the step the user was on
    val step: StateFlow<Int> = savedState.getStateFlow("step", 0)
    fun next() { savedState["step"] = step.value + 1 }
}
```

### 3.5 How ViewModel survives rotation

`ComponentActivity` keeps a `ViewModelStore` and passes it through `onRetainNonConfigurationInstance()` to the new instance. The store is cleared (calling `onCleared()`) only when the activity finishes for good (`isChangingConfigurations == false`). Never hold a reference to an Activity, Fragment, View or Context in a ViewModel; use `AndroidViewModel`/application context if needed.

### 3.6 Tasks, back stack and launch modes

- `standard` (new instance each time), `singleTop` (reuse if already on top → `onNewIntent`), `singleTask` (one instance per task, clears above it), `singleInstance` (alone in its own task), `singleInstancePerTask` (Android 12+).
- Intent flags: `FLAG_ACTIVITY_NEW_TASK`, `CLEAR_TOP`, `SINGLE_TOP`.
- Modern apps are usually **single-activity** with Navigation, so launch modes matter mostly for deep links and notifications.

### 3.7 Intents, PendingIntents and deep links

- Explicit intent: targets a class. Implicit intent: action + data, the system resolves it.
- `PendingIntent`: a token letting another app (e.g. the notification shade, AlarmManager) run an intent as your app. Since Android 12 you must set `FLAG_IMMUTABLE` or `FLAG_MUTABLE`.
- **App Links:** verified `https` deep links using `assetlinks.json` on your domain, so they open your app without a chooser.

### 3.8 Threading: Looper, Handler, main thread

- The main thread runs a `Looper` that processes a `MessageQueue`. All UI work and lifecycle callbacks run on it.
- Blocking it for about 5 s on input causes an **ANR**. Frames must render in \~16 ms (60 Hz) or \~8 ms (120 Hz) to avoid jank.
- `Handler(Looper.getMainLooper()).post {}` posts work to the main queue. Coroutines with `Dispatchers.Main` use this under the hood.

### 3.9 Context types

- **Application context:** lives as long as the process. Use for singletons, DataStore, Room.
- **Activity context:** themed, needed for inflating UI, dialogs, starting activities without `NEW_TASK`. Never store it in a long-lived object, or you leak the whole activity.

### 3.10 Permissions

- Normal (granted at install), dangerous / runtime (ask in context), special (e.g. `SCHEDULE_EXACT_ALARM`, overlay).
- Use the Activity Result API:

```kotlin
val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
    if (granted) startCamera() else showRationale()
}
Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) { Text("Scan") }
```

### 3.11 Deeper dive: process death, walked through

A user is filling a 3-step sign-up form, on step 2, and switches to the camera app. While the camera is open, Android kills your process to free memory. Here is what happens when they come back:

1. Android starts a new process and creates a new `Application` object (`Application.onCreate` runs again).
2. It recreates the activity on top of the back stack and passes the saved `Bundle` to `onCreate`.
3. Fragments and the navigation back stack are restored from that Bundle.
4. A **new** ViewModel is created; its `SavedStateHandle` is filled from the Bundle.
5. Anything that lived only in memory (singletons, ViewModel fields, static caches) is empty.

```kotlin
@HiltViewModel
class SignUpViewModel @Inject constructor(private val state: SavedStateHandle) : ViewModel() {
    // Survives: small, user-entered values
    val email = state.getStateFlow("email", "")
    val step = state.getStateFlow("step", 1)

    fun onEmailChange(value: String) { state["email"] = value }

    // Does NOT survive: rebuilt from the repository when needed
    private var countries: List<Country> = emptyList()
}
```

Common bugs this exposes: a `lateinit` singleton that crashes because `Application.onCreate` set it on a different path; a detail screen that reads a selected item from a shared in-memory object that is now empty. Fix by passing IDs as navigation arguments and reloading data from the repository.

### 3.12 Deeper dive: Binder and IPC

Each app runs in its own Linux process with its own user ID. Apps and system services (ActivityManager, PackageManager, WindowManager) talk through **Binder**, Android's IPC mechanism.

- Calling `startActivity` is really a Binder call to `ActivityTaskManagerService` in the `system_server` process.
- Data crossing Binder must be a `Parcel`, which is why intents carry `Parcelable` extras.
- The buffer for in-flight transactions is about 1 MB per process, shared by all calls, which is the origin of `TransactionTooLargeException`.
- A Binder call is synchronous by default, so a slow system service called on the main thread can cause an ANR.

To expose your own IPC service, you define an AIDL interface or use a `Messenger`. In interviews, also mention that `ContentProvider` and bound services are built on Binder.

### 3.13 Deeper dive: Looper, Handler and MessageQueue

```kotlin
class WorkerThread : HandlerThread("worker") {
    lateinit var handler: Handler
    override fun onLooperPrepared() { handler = Handler(looper) }
}

val worker = WorkerThread().apply { start() }
worker.handler.post { /* runs on the worker thread, in order */ }
Handler(Looper.getMainLooper()).postDelayed({ hideToast() }, 2_000)
```

How it works: a `Looper` loops forever, taking `Message`s from its `MessageQueue` (ordered by time) and running them. A `Handler` puts messages on one specific looper's queue. The main thread's looper also delivers input events, lifecycle callbacks and frame callbacks (Choreographer), so anything slow you post to it delays all of these.

Leak to mention: a `postDelayed` runnable that captures an Activity keeps it alive until it runs. Remove callbacks in `onDestroy`, or use coroutines tied to a lifecycle.

### 3.14 Deeper dive: BroadcastReceivers in practice

```kotlin
// Context-registered: lives only while registered; preferred for most cases
val receiver = object : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        onBattery(level)
    }
}
ContextCompat.registerReceiver(
    context, receiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED), ContextCompat.RECEIVER_NOT_EXPORTED
)
// later: context.unregisterReceiver(receiver)
```

- Since Android 8, most implicit broadcasts cannot be received by manifest-declared receivers (exceptions include `BOOT_COMPLETED` and `LOCALE_CHANGED`).
- Since Android 14, context-registered receivers must say if they are exported.
- `onReceive` runs on the main thread and must finish quickly. For longer work use `goAsync()` (a few seconds) or enqueue WorkManager.

### 3.15 Deeper dive: sharing a file with FileProvider

```xml
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/file_paths" />
</provider>
```

```kotlin
val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", pdfFile)
val share = Intent(Intent.ACTION_SEND).apply {
    type = "application/pdf"
    putExtra(Intent.EXTRA_STREAM, uri)
    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)   // temporary read access for the receiving app only
}
startActivity(Intent.createChooser(share, "Share invoice"))
```

The receiving app gets a `content://` URI and temporary permission, never a raw file path. Sharing `file://` URIs crashes with `FileUriExposedException` since Android 7.

### Interview questions

1. **Is `onDestroy` guaranteed to be called?** No. If the process is killed, it is not. Persist important data earlier (`onStop` or immediately on change). {Easy}
2. **Why is `onSaveInstanceState` Bundle size limited?** It goes across Binder to `system_server`; the transaction buffer is \~1 MB shared per process. Too much data throws `TransactionTooLargeException`. Save IDs, not objects. {Medium}
3. **What is the difference between `commit()` and `commitAllowingStateLoss()`?** After `onSaveInstanceState`, a fragment transaction would be lost on recreation, so `commit()` throws. `AllowingStateLoss` accepts the loss. Better: do not commit after the state is saved (collect with `repeatOnLifecycle`). {Hard}
4. **How does Android decide which process to kill?** By importance: foreground → visible → service → cached (background). Cached processes are killed first, least-recently-used first. {Medium}
5. **Parcelable vs Serializable?** Parcelable is Android's explicit, fast IPC format (generate with `@Parcelize`). Serializable uses reflection and is slower and creates garbage. {Easy}
