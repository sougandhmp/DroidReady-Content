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

### Interview questions

1. **Walk me through how you would investigate a slow screen.** Reproduce on a low-end device with a release build → record a Perfetto trace / Compose recomposition counts → identify the long frames and what runs in them → fix (move work off main, reduce recomposition, paginate) → add a Macrobenchmark `FrameTimingMetric` test in CI to prevent regressions. {Medium}
2. **What is the difference between a memory leak and high memory usage?** A leak is unreachable-in-logic but reachable-in-GC memory that grows over time. High usage may be legitimate (big caches, bitmaps) and is fixed by sizing, not by breaking references. {Easy}
3. **How does ART run your code?** DEX bytecode is interpreted and JIT-compiled at first, hot methods recorded into profiles, then compiled AOT in the background when the device is idle and charging. Baseline profiles skip the wait for the first runs. {Hard}
4. **An SDK slows startup by 300 ms. What do you do?** Measure it in isolation, initialise it lazily on first use or on a background thread after first frame, talk to the vendor, or remove it. Show the before/after numbers. {Medium}
