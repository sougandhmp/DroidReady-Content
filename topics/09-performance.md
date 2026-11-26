# Performance

Senior candidates are expected to have *debugged* real performance problems. Always frame answers as: **measure → find the cause → fix → verify with numbers → guard against regressions**.

### 9.1 Key metrics (Android vitals)

| Metric | Bad-behaviour threshold on Play | Tools |
| --- | --- | --- |
| User-perceived crash rate | 1.09% overall (8% per device model) | Crashlytics, Play Console |
| User-perceived ANR rate | 0.47% overall (8% per device model) | Play Console, ANR traces |
| Cold start time | Aim < 1 s on mid-range; vitals flag ≥ 5 s | Macrobenchmark, `reportFullyDrawn()` |
| Slow / frozen frames | > 16 ms / > 700 ms | JankStats, Perfetto |
| Excessive wakeups / wakelocks | Battery | Battery Historian, Power Profiler |

Play can reduce visibility of apps that exceed the crash/ANR thresholds, so these numbers have business impact.

### 9.2 Memory leaks

A leak is an object that is no longer needed but still reachable from a GC root, so it is never collected. Activities are the classic victim (an Activity holds its whole view tree and bitmaps).

Common causes and fixes:

- Static field or singleton holding an Activity/View/Context → use application context, or don't store it.
- Non-static inner class / anonymous `Handler`, `Runnable`, `AsyncTask` outliving the activity → cancel in lifecycle, use coroutines bound to a scope.
- Listener registered and never unregistered (sensor, location, broadcast) → `DisposableEffect` / `DefaultLifecycleObserver`.
- Fragment view binding not cleared in `onDestroyView`.
- `GlobalScope` coroutines capturing a view or context.

```kotlin
// Leak: the singleton outlives the Activity
object Analytics { lateinit var context: Context }
Analytics.context = this            // Activity!

// Fix
Analytics.context = applicationContext
```

**Tools:** LeakCanary (debug builds, automatic heap dump and leak trace), Android Studio Memory Profiler (heap dump, allocation tracking), `adb shell dumpsys meminfo <pkg>`.

**Also:** large bitmaps (downsample with Coil/Glide), respond to `onTrimMemory`, avoid allocations in `onDraw` / tight loops (GC churn causes jank).

### 9.3 ANRs

An ANR happens when the main thread is blocked: no response to an input event within 5 s, a `BroadcastReceiver` not finishing within \~10 s (foreground), or a service not starting in time.

Finding the cause: Play Console ANR clusters or `/data/anr/traces.txt` show the main thread's stack. Common culprits: disk or network I/O on main, `SharedPreferences.commit()`, lock contention with a background thread, slow `Application.onCreate`, binder calls to slow system services, deadlocks.

Enable **StrictMode** in debug builds to catch disk and network access on the main thread:

```kotlin
if (BuildConfig.DEBUG) {
    StrictMode.setThreadPolicy(StrictMode.ThreadPolicy.Builder().detectAll().penaltyLog().build())
    StrictMode.setVmPolicy(StrictMode.VmPolicy.Builder().detectLeakedClosableObjects().detectActivityLeaks().penaltyLog().build())
}
```

### 9.4 App startup

- **Cold** (process created), **warm** (process alive, activity recreated), **hot** (activity brought to front).
- Measure with Macrobenchmark (`StartupTimingMetric`), and `adb shell am start -W`. Call `reportFullyDrawn()` when content is really shown.
- Fixes: keep `Application.onCreate` minimal; lazy-initialise SDKs (or initialise off the main thread); use the App Startup library to order initializers; avoid heavy DI graphs on startup (`Lazy<T>` / `Provider<T>`); use the SplashScreen API properly; ship a **baseline profile**.

### 9.5 Baseline profiles and R8

- **Baseline profile:** a list of classes and methods used in critical journeys (startup, scrolling). Shipped in the APK/AAB so ART compiles them ahead of time at install, instead of interpreting/JIT-ing on first runs. Typical improvement is roughly 20-30% faster startup and less jank. Generate with the Baseline Profile Gradle plugin + a Macrobenchmark test. **Startup profiles** additionally optimise dex layout.
- **R8:** shrinks (removes unused code), obfuscates and optimises (inlining, class merging). Enable `isMinifyEnabled = true` and `isShrinkResources = true` for release. Keep rules (`-keep`) are needed for reflection (e.g. Gson, some serializers, JNI). Upload the mapping file to Crashlytics/Play to de-obfuscate stack traces.

```kotlin
@RunWith(AndroidJUnit4::class)
class StartupBenchmark {
    @get:Rule val rule = MacrobenchmarkRule()
    @Test fun coldStart() = rule.measureRepeated(
        packageName = "com.example.app",
        metrics = listOf(StartupTimingMetric()),
        iterations = 10,
        startupMode = StartupMode.COLD
    ) { pressHome(); startActivityAndWait() }
}
```

### 9.6 Rendering and jank

- Use **Perfetto / System Trace** to see what runs on the main and RenderThread in each frame.
- In Views: flatten hierarchies (ConstraintLayout), avoid overdraw (*Debug GPU overdraw*), use `RecyclerView` with `DiffUtil`/`ListAdapter`, stable IDs, `setHasFixedSize`.
- In Compose: see section 4.6.

### 9.7 App size, network and battery

- App size: Android App Bundle (per-device APK splits), R8 + resource shrinking, WebP/vector images, dynamic feature modules, remove unused languages (`localeFilters` / `resourceConfigurations`).
- Network: compress (GZIP/Brotli), paginate, cache with ETags, batch requests, prefer one larger request over many on mobile radios.
- Battery: batch work with WorkManager, avoid wakelocks, use fused location with appropriate priority and interval.

### 9.8 Deeper dive: reading a LeakCanary trace

LeakCanary shows the chain of references from a GC root to the leaked object. Read it top to bottom and find the first reference that should not exist.

```text
┬───
│ GC Root: Thread object
├─ android.os.HandlerThread instance
│    Leaking: NO (thread is alive)
│    ↓ Thread.target
├─ com.example.session.SessionManager instance
│    Leaking: NO (it is a singleton)
│    ↓ SessionManager.listeners
│                     ~~~~~~~~~
├─ java.util.ArrayList instance
│    ↓ ArrayList[0]
├─ com.example.profile.ProfileActivity$sessionListener$1 instance
│    Leaking: UNKNOWN
│    ↓ ProfileActivity$sessionListener$1.this$0
╰→ com.example.profile.ProfileActivity instance
     Leaking: YES (Activity#mDestroyed is true)
```

Reading it: the singleton `SessionManager` holds a list of listeners; `ProfileActivity` added an anonymous listener (which holds `this$0`, the activity) and never removed it. The `~~~` underline marks the suspect reference. Fix: remove the listener in `onDestroy`, or better, expose session changes as a `Flow` and collect it with `repeatOnLifecycle`, so cleanup is automatic.

### 9.9 Deeper dive: reading an ANR trace

```text
"main" prio=5 tid=1 Blocked
  at com.example.data.LocalCache.get(LocalCache.kt:42)
  - waiting to lock <0x0a1b2c3d> (a java.lang.Object) held by thread 23
  at com.example.ui.HomeViewModel.<init>(HomeViewModel.kt:31)
  ...
"DefaultDispatcher-worker-3" prio=5 tid=23 Runnable
  at java.io.FileInputStream.read(Native method)
  at com.example.data.LocalCache.loadFromDisk(LocalCache.kt:88)
  - locked <0x0a1b2c3d> (a java.lang.Object)
```

Reading it: the main thread is **Blocked** waiting for a lock. Thread 23 holds that lock while reading from disk. So the background I/O itself is fine, but sharing a lock with the main thread made the main thread wait for disk. Fix: never take a lock on the main thread that background I/O can hold; make `get` a suspend function that reads off the main thread, and stop constructing data in the ViewModel's `init` synchronously.

Common ANR states to recognise: `Blocked` (lock contention), `Native` in a Binder call (slow system service or another app's provider), `Runnable` deep in your code (heavy computation), `Waiting` on a `CountDownLatch` or `Future.get()` (blocking on async work).

### 9.10 Deeper dive: a startup optimisation case study

An illustrative example (use your own numbers in interviews). Starting point: cold start 2.4 s at P50 on a mid-range phone. Steps taken, each measured with Macrobenchmark:

| Change | Cold start (P50) |
| --- | --- |
| Baseline | 2.4 s |
| Moved 3 analytics/ads SDK inits off the main thread, lazy on first use | 1.9 s |
| Replaced a synchronous `SharedPreferences` read of a 400 KB JSON blob with DataStore + async load | 1.6 s |
| Removed an eager Hilt `@Singleton` that built the full image cache at startup (made it `Lazy<T>`) | 1.5 s |
| Added a baseline profile for the startup and home-feed journeys | 1.15 s |
| Showed cached feed from Room first, refreshed network afterwards | Time to useful content: 1.3 s (from 3.1 s) |

How to tell it in an interview: name the tool (Perfetto trace showed 600 ms in `Application.onCreate`), the fix, and the number. Then the guard: a CI Macrobenchmark job that fails the build if startup regresses by more than 10%.

### 9.11 Deeper dive: allocation and garbage collection

ART uses a concurrent copying garbage collector; most collection runs in the background, but heavy allocation still costs CPU and can cause short pauses and jank.

```kotlin
// Bad: allocates in every frame
override fun onDraw(canvas: Canvas) {
    val paint = Paint().apply { color = Color.RED }          // new object 60-120 times a second
    canvas.drawText(formatter.format(Date()), x, y, paint)   // new Date and String each frame
}

// Better: allocate once, reuse
private val paint = Paint().apply { color = Color.RED }
override fun onDraw(canvas: Canvas) { canvas.drawText(cachedLabel, x, y, paint) }
```

Other sources of GC churn: string concatenation in loops (use `buildString`), boxing primitives in generic collections (`List<Int>` boxes; `IntArray` does not), `map`/`filter` chains in scroll callbacks, and logging that builds strings even when disabled. Find them with the Memory Profiler's allocation tracking or a Perfetto heap profile.

### Interview questions

1. **Walk me through how you would investigate a slow screen.** Reproduce on a low-end device with a release build → record a Perfetto trace / Compose recomposition counts → identify the long frames and what runs in them → fix (move work off main, reduce recomposition, paginate) → add a Macrobenchmark `FrameTimingMetric` test in CI to prevent regressions. {Medium}
2. **What is the difference between a memory leak and high memory usage?** A leak is unreachable-in-logic but reachable-in-GC memory that grows over time. High usage may be legitimate (big caches, bitmaps) and is fixed by sizing, not by breaking references. {Easy}
3. **How does ART run your code?** DEX bytecode is interpreted and JIT-compiled at first, hot methods recorded into profiles, then compiled AOT in the background when the device is idle and charging. Baseline profiles skip the wait for the first runs. {Hard}
4. **An SDK slows startup by 300 ms. What do you do?** Measure it in isolation, initialise it lazily on first use or on a background thread after first frame, talk to the vendor, or remove it. Show the before/after numbers. {Medium}
