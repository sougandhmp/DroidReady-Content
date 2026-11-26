# Performance

Senior candidates are expected to have fixed real performance problems. Frame every answer the same way: measure, find the cause, fix it, prove it with numbers, and stop it coming back.

### 9.1 How to talk about performance

**In one line:** performance work is measure, diagnose, fix, verify and guard, with numbers at every step.

**Say this in the interview:** "I start from data, not guesses: Play Console vitals, Crashlytics, or a user complaint. I reproduce on a low-end device with a release build, profile with Perfetto or the Android Studio profilers, find the cause, fix it, and show the before and after numbers. Then I add a guard, like a Macrobenchmark test in CI, so it doesn't regress."

**Example:**

| Metric | Play's bad-behaviour threshold | Tools |
| --- | --- | --- |
| User-perceived crash rate | 1.09% overall, 8% per device model | Crashlytics, Play Console |
| User-perceived ANR rate | 0.47% overall, 8% per device model | Play Console, ANR traces |
| Cold start | Aim under ~1 s on mid-range devices | Macrobenchmark, `reportFullyDrawn()` |
| Jank | Frames over 16 ms (60 Hz) or 8 ms (120 Hz) | JankStats, Perfetto |

Apps above Play's thresholds can get less visibility in the store, so these numbers matter to the business.

### 9.2 Memory leaks

**In one line:** a memory leak is an object the app no longer needs that is still reachable from a GC root, so it can never be freed.

**Say this in the interview:** "The classic leak is an Activity: it holds the whole view tree and bitmaps, so leaking one wastes a lot of memory. Common causes are a singleton or static field holding an Activity or View, a listener registered but never unregistered, a delayed Handler callback or a lambda capturing the screen, and a Fragment binding not cleared in `onDestroyView`. I find leaks with LeakCanary in debug builds, which shows the reference chain, then fix the first reference that shouldn't exist."

**Example, reading a LeakCanary trace:**

```text
GC Root: Thread object
├─ com.example.session.SessionManager instance      Leaking: NO (singleton)
│    ↓ SessionManager.listeners                      <- suspect: the list keeps growing
├─ java.util.ArrayList instance
│    ↓ ArrayList[0]
├─ ProfileActivity$sessionListener$1 instance
│    ↓ this$0                                        <- the anonymous listener holds the activity
╰→ ProfileActivity instance                          Leaking: YES (destroyed)
```

Fix: unregister in `onDestroy`, or better, expose session changes as a Flow collected with `repeatOnLifecycle`, so cleanup is automatic.

**Follow-ups:**

- *Leak vs high memory use?* A leak grows over time because unneeded objects stay reachable. High usage can be legitimate, like big caches, and is fixed by sizing, not by breaking references.

### 9.3 ANRs

**In one line:** an ANR ("Application Not Responding") happens when the main thread is blocked, typically for about 5 seconds while handling input.

**Say this in the interview:** "To fix an ANR, I read the main thread's stack in the ANR trace from Play Console. The usual causes are disk or network I/O on the main thread, waiting on a lock held by a background thread, slow `Application.onCreate`, or slow Binder calls to the system. I turn on StrictMode in debug builds to catch disk and network access on the main thread before it ships."

**Example, reading an ANR trace:**

```text
"main" tid=1 Blocked
  at com.example.data.LocalCache.get(LocalCache.kt:42)
  - waiting to lock <0x0a1b2c3d> held by thread 23
"DefaultDispatcher-worker-3" tid=23 Runnable
  at java.io.FileInputStream.read(Native method)
  at com.example.data.LocalCache.loadFromDisk(LocalCache.kt:88)
  - locked <0x0a1b2c3d>
```

The main thread waits for a lock that a background thread holds while reading from disk. Fix: never share that lock with the main thread; make `get` a suspend function that reads off the main thread.

### 9.4 App startup

**In one line:** cold start time is how long it takes from tapping the icon to useful content, and most of it is usually spent in `Application.onCreate` and the first screen.

**Say this in the interview:** "I measure cold start with Macrobenchmark and call `reportFullyDrawn()` when real content is on screen. Then I move SDK initialisation off the main thread or make it lazy, use the App Startup library, inject expensive objects lazily, show cached data from the database first, and ship a baseline profile. I tell it as a story with numbers, for example 2.4 s down to 1.2 s."

**Example, an illustrative case study (use your own numbers):**

| Change | Cold start (P50) |
| --- | --- |
| Starting point | 2.4 s |
| Three SDKs initialised lazily, off the main thread | 1.9 s |
| A large synchronous SharedPreferences read moved to DataStore | 1.6 s |
| An eager singleton image cache made lazy | 1.5 s |
| Baseline profile for startup and the home feed | 1.15 s |

### 9.5 Baseline profiles and R8

**In one line:** a baseline profile tells the system which code to compile ahead of time, and R8 shrinks, obfuscates and optimises the release build.

**Say this in the interview:** "Without a baseline profile, the first runs after install interpret and JIT-compile code, which is slow. A baseline profile lists the classes and methods used in key journeys, like startup and scrolling, so they're compiled at install time; that often makes startup around 20 to 30 percent faster. I generate it with the Baseline Profile Gradle plugin and a Macrobenchmark test. R8 removes unused code and resources and optimises the rest; I keep only what reflection needs with keep rules and upload the mapping file so crash reports are readable."

**Example:**

```kotlin
@Test fun coldStart() = rule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(StartupTimingMetric()),
    iterations = 10,
    startupMode = StartupMode.COLD
) { pressHome(); startActivityAndWait() }
```

### 9.6 Rendering, jank and garbage collection

**In one line:** jank happens when a frame takes longer than the display's frame time, often because of work on the main thread or too much allocation.

**Say this in the interview:** "I record a Perfetto system trace and look at what runs on the main thread and RenderThread in the slow frames. Fixes are usually moving work off the main thread, reducing recomposition in Compose, flattening view hierarchies, using `DiffUtil` for lists, and avoiding allocations in hot paths like `onDraw` or scroll callbacks, because constant allocation makes the garbage collector work harder."

**Example:**

```kotlin
// Bad: a new Paint 60-120 times a second
override fun onDraw(canvas: Canvas) { canvas.drawText(label, x, y, Paint().apply { color = Color.RED }) }

// Better: allocate once
private val paint = Paint().apply { color = Color.RED }
override fun onDraw(canvas: Canvas) { canvas.drawText(label, x, y, paint) }
```

### 9.7 App size, network and battery

**In one line:** ship less code and data, send fewer and smaller requests, and batch background work.

**Say this in the interview:** "For size I publish an App Bundle so each device gets only what it needs, turn on R8 and resource shrinking, use vector or WebP images, and move rarely used features into dynamic modules. For network I paginate, compress, cache with ETags and batch requests. For battery I let WorkManager batch background work, avoid wakelocks, and request location at the lowest accuracy and frequency that works."

### Interview questions

1. **How would you investigate a slow screen?** Reproduce on a low-end device with a release build, record a Perfetto trace or check Compose recomposition counts, find the long frames and what runs in them, fix it, then add a Macrobenchmark frame-timing test so it doesn't regress. {Medium}
2. **What are the most common causes of memory leaks on Android?** Static fields or singletons holding an Activity or View, listeners never unregistered, delayed Handler callbacks or lambdas capturing the screen, and Fragment view bindings not cleared in `onDestroyView`. {Easy}
3. **How do you find and fix a memory leak?** Use LeakCanary in debug builds, read the reference chain from the GC root, find the first reference that shouldn't exist, and remove it, often by unregistering or using lifecycle-aware collection. {Medium}
4. **What causes ANRs, and how do you diagnose one?** A blocked main thread: I/O on the main thread, lock contention, slow `Application.onCreate` or slow Binder calls. Read the main thread's stack in the Play Console ANR trace and use StrictMode in debug builds. {Medium}
5. **How do you improve cold start time?** Measure with Macrobenchmark, make SDK initialisation lazy or move it off the main thread, avoid eager singletons, show cached data first, and ship a baseline profile. {Medium}
6. **What is a baseline profile?** A list of classes and methods used in key journeys, shipped with the app so they're compiled ahead of time at install, making startup and scrolling faster from the first launch. {Medium}
7. **What does R8 do, and what can go wrong?** It removes unused code, renames and optimises the rest. Code accessed by reflection can be removed or renamed by mistake, so it needs keep rules; upload the mapping file to read crash reports. {Medium}
8. **An SDK adds 300 ms to startup. What do you do?** Measure it alone, initialise it lazily or after the first frame on a background thread, talk to the vendor, or remove it, and show the before and after numbers. {Hard}
9. **What is the difference between a memory leak and high memory use?** A leak grows over time because unneeded objects stay reachable. High use can be legitimate, like big caches or bitmaps, and is fixed by sizing them, not by breaking references. {Medium}
