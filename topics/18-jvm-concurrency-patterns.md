# JVM, concurrency and design patterns

Interviews at product companies often go below Android into the JVM: how memory works, what thread-safety really means, and which design patterns you use and why. This section covers those foundations with Android examples.

### 18.1 Memory: stack, heap and garbage collection

- **Stack:** one per thread. Holds local variables and call frames; freed automatically when a function returns.
- **Heap:** shared by all threads. Every object lives here. Android gives each app a heap limit (check `ActivityManager.getMemoryClass()`, often 256-512 MB on modern phones); exceeding it throws `OutOfMemoryError`.
- **Garbage collection:** ART frees objects that can no longer be reached from a **GC root**. Roots include static fields, local variables of running threads, active JNI references and the main thread's message queue. Most collection is concurrent, but heavy allocation still costs CPU and can cause jank.

A memory leak is an object that is no longer needed but is still reachable from a root, so the GC can't free it. That is why a static field holding an Activity leaks the whole screen.

### 18.2 Reference types

| Type | Collected when | Android use |
| --- | --- | --- |
| Strong (normal) | Never, while reachable | Almost everything |
| `WeakReference` | At the next GC, if only weakly reachable | Pointing at an Activity or View from a longer-lived object without leaking it |
| `SoftReference` | Only when memory is low | Rarely; prefer `LruCache` for caches, because soft references give poor control |
| `PhantomReference` | After finalisation, to schedule cleanup | Low-level native resource cleanup (`Cleaner`) |

```kotlin
class LocationCallbackWrapper(activity: MapActivity) : LocationCallback() {
    private val activityRef = WeakReference(activity)          // doesn't keep the activity alive
    override fun onLocationResult(result: LocationResult) {
        activityRef.get()?.showLocation(result.lastLocation)  // null if the activity was collected
    }
}
```

A weak reference is a safety net, not a design. The better fix is usually to unregister in the right lifecycle callback or to expose a `Flow` collected with the lifecycle.

### 18.3 The Java memory model, visibility and atomicity

Two separate problems appear when threads share data:

- **Visibility:** one thread writes a value, but another thread keeps seeing an old copy (from a CPU cache or a compiler optimisation).
- **Atomicity:** an operation like `count++` is really read, add, write. Two threads can interleave and lose an update.

The Java Memory Model defines **happens-before** rules: if action A happens-before action B, B is guaranteed to see A's effects. Unlocking a lock, writing a `volatile` field and starting or joining a thread all create happens-before edges.

```kotlin
// Visibility only: a flag written by one thread, read by another
@Volatile private var cancelled = false
fun cancel() { cancelled = true }
fun loop() { while (!cancelled) doWork() }

// Atomicity: use atomics or a lock, never @Volatile alone for count++
private val count = AtomicInteger()
fun increment() = count.incrementAndGet()

// Several fields that must change together: a lock
private val lock = Any()
private var balance = 0L
private val history = mutableListOf<Long>()
fun deposit(amount: Long) = synchronized(lock) { balance += amount; history += amount }
```

| Tool | Gives visibility | Gives atomicity | Use for |
| --- | --- | --- | --- |
| `@Volatile` | Yes | Only single reads/writes | Flags, double-checked locking |
| `AtomicInteger`, `AtomicReference` | Yes | Yes, for one variable | Counters, compare-and-set |
| `synchronized` / `ReentrantLock` | Yes | Yes, for a block | Several related fields |
| Coroutine `Mutex` | Yes | Yes, for a block | Same, without blocking a thread |
| Thread confinement | Not needed | Not needed | Keep the state on one thread or one dispatcher |
| Immutable data | Not needed | Not needed | Share `val` data classes freely |

**Double-checked locking**, the classic singleton question:

```kotlin
class Database private constructor(context: Context) {
    companion object {
        @Volatile private var instance: Database? = null
        fun get(context: Context): Database =
            instance ?: synchronized(this) {
                instance ?: Database(context.applicationContext).also { instance = it }
            }
    }
}
```

`@Volatile` is required: without it, another thread could see a non-null reference to a half-constructed object. In Kotlin, `by lazy` (default `SYNCHRONIZED` mode) or Hilt `@Singleton` do this for you.

**Deadlock:** two threads each hold one lock and wait for the other's. Avoid by always taking locks in the same order, keeping critical sections short, and never calling unknown code (callbacks) while holding a lock.

### 18.4 Threads, executors and coroutines

| Tool | What it is | When to use |
| --- | --- | --- |
| `Thread` | One OS thread (~1 MB stack) | Almost never directly |
| `ExecutorService` / thread pool | Reuses a fixed set of threads | Java code, libraries without coroutines |
| `HandlerThread` + `Handler` | A thread with a message loop | Camera callbacks, ordered work from legacy APIs |
| Coroutines | Lightweight tasks multiplexed onto thread pools | Default for Kotlin Android code |

```kotlin
// Bridging an executor-based Java API to coroutines
val ioExecutor = Executors.newFixedThreadPool(4)
val dispatcher = ioExecutor.asCoroutineDispatcher()     // use with withContext(dispatcher) { ... }
```

Because suspended coroutines release their thread, 10,000 concurrent coroutines can run on a handful of threads, while 10,000 threads would exhaust memory.

### 18.5 Design patterns you already use on Android

| Pattern | Idea | Android example |
| --- | --- | --- |
| Singleton | One instance for the process | `Room` database, `OkHttpClient` (scoped by Hilt `@Singleton`) |
| Builder | Build complex objects step by step | `NotificationCompat.Builder`, `Retrofit.Builder`, `AlertDialog.Builder` |
| Factory | Hide which class gets created | `ViewModelProvider.Factory`, `Fragment.instantiate` |
| Observer | Subscribers react to changes | `Flow` / `StateFlow`, `LiveData`, lifecycle observers |
| Adapter | Make one interface fit another | `RecyclerView.Adapter` turns data into views |
| Facade | One simple API over a complex subsystem | A `Repository` over Room, Retrofit and DataStore |
| Strategy | Swap algorithms behind an interface | Different `PaymentProcessor`s, caching policies |
| Decorator | Wrap an object to add behaviour | `BufferedInputStream`, a caching repository wrapping a network one |
| Chain of responsibility | Pass a request along handlers | OkHttp interceptors |
| Dependency injection | Receive collaborators instead of creating them | Hilt, Koin |

**Strategy plus dependency injection, a typical interview example:**

```kotlin
interface PaymentProcessor { suspend fun pay(order: Order): PaymentResult }
class CardProcessor @Inject constructor(private val api: CardApi) : PaymentProcessor { /* ... */ }
class WalletProcessor @Inject constructor(private val wallet: WalletClient) : PaymentProcessor { /* ... */ }

class CheckoutUseCase @Inject constructor(
    private val processors: Map<PaymentMethod, @JvmSuppressWildcards PaymentProcessor>   // Hilt multibinding
) {
    suspend operator fun invoke(order: Order) = processors.getValue(order.method).pay(order)
}
```

Adding a new payment method means adding a class and a binding, without changing `CheckoutUseCase`.

### 18.6 SOLID with Android examples

| Principle | Means | Android example |
| --- | --- | --- |
| **S**ingle responsibility | One reason to change | The ViewModel handles screen state; formatting lives in a mapper; networking in a data source |
| **O**pen/closed | Extend without editing | New payment methods through the strategy map above |
| **L**iskov substitution | Subtypes behave like their base | A `FakeArticleRepository` must honour the same contract (e.g. emit current data first), or tests lie |
| **I**nterface segregation | Small, focused interfaces | Split a large `UserRepository` into `ProfileReader` and `ProfileWriter` when screens need only one |
| **D**ependency inversion | Depend on abstractions | The ViewModel depends on an `ArticleRepository` interface, not on Retrofit |

### Interview questions

1. **What is a GC root, and how does it relate to memory leaks?** A GC root is a starting point the collector treats as always alive: static fields, live threads' local variables, JNI references. A leak is an unneeded object still reachable from a root, for example an Activity referenced from a static field. {Medium}
2. **When would you use `WeakReference`?** When a longer-lived object must point at a short-lived one (an Activity or View) without keeping it alive, such as a callback from a system service. Prefer proper unregistration or lifecycle-aware flows; a weak reference is a fallback. {Medium}
3. **Is `@Volatile var count` enough for a thread-safe counter?** No. `@Volatile` gives visibility, but `count++` is read-modify-write and can lose updates. Use `AtomicInteger`, a lock, a coroutine `Mutex`, or confine the counter to one thread. {Easy}
4. **Why does double-checked locking need `@Volatile`?** Without it, the reference can become visible to another thread before the object's constructor has finished, so that thread may use a half-built object. `@Volatile` adds the happens-before guarantee. {Hard}
5. **How do you avoid deadlocks?** Take locks in a fixed global order, keep critical sections short, avoid calling external code while holding a lock, and prefer immutable data, thread confinement or coroutine `Mutex` with structured concurrency. {Medium}
6. **Which design patterns do you see in Android and its libraries?** Builder (Retrofit, notifications), Observer (Flow, LiveData), Adapter (RecyclerView), Facade (repositories), Chain of responsibility (OkHttp interceptors), Factory (ViewModel factories), Singleton (Room, OkHttpClient via DI). {Easy}
7. **Explain dependency inversion with an example from your app.** The ViewModel depends on an interface such as `ArticleRepository`, defined near the domain. The data layer implements it with Retrofit and Room. Tests swap in a fake, and the network library can change without touching the ViewModel. {Medium}
