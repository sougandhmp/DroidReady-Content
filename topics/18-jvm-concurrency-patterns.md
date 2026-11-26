# JVM, concurrency and design patterns

Interviews at product companies often go below Android into the JVM: how memory works, what thread safety really means, and which design patterns you use and why. This section covers those foundations with Android examples.

### 18.1 Memory: stack, heap and garbage collection

**In one line:** each thread has its own stack for local variables and calls, all objects live on a shared heap, and the garbage collector frees objects that nothing alive can reach.

**Say this in the interview:** "The stack holds a thread's call frames and local variables and is freed when a function returns. Objects live on the heap, which every thread shares, and Android gives each app a heap limit; going over it throws `OutOfMemoryError`. ART's garbage collector frees any object that can't be reached from a GC root: static fields, local variables of running threads, JNI references. A memory leak is simply an object we no longer need that's still reachable from a root, like an Activity held in a static field."

**Example:**

```kotlin
object Cache {
    var screen: Activity? = null          // static field = GC root -> the Activity and its views can never be freed
}
```

**How it works:** most collection in ART is concurrent, so pauses are short, but heavy allocation in hot paths, such as creating objects in `onDraw` or during scrolling, still costs CPU and can cause jank. `ActivityManager.getMemoryClass()` reports the heap limit, often 256 to 512 MB on modern phones.

**Common mistake:** Thinking garbage collection makes memory leaks impossible.

**Follow-ups:**

- *What is a GC root?* A starting point the collector treats as reachable, such as a local variable of a running thread or a static field of a loaded class.

### 18.2 Reference types

**In one line:** strong references keep objects alive; weak references let the collector free the object; soft references are freed only under memory pressure.

**Say this in the interview:** "Normal references are strong. A `WeakReference` doesn't stop collection, so a long-lived object can point at an Activity without leaking it. But a weak reference is a safety net, not a design: the real fix is usually to unregister in the right lifecycle callback, or expose a `Flow` collected with the lifecycle. For caches I use `LruCache` rather than `SoftReference`, because soft references give poor control over what's evicted."

**Example:**

```kotlin
class LocationCallbackWrapper(activity: MapActivity) : LocationCallback() {
    private val activityRef = WeakReference(activity)          // doesn't keep the activity alive
    override fun onLocationResult(result: LocationResult) {
        activityRef.get()?.showLocation(result.lastLocation)  // null if the activity was collected
    }
}
```

| Type | Collected when | Android use |
| --- | --- | --- |
| Strong | Never, while reachable | Almost everything |
| `WeakReference` | At the next GC, if only weakly reachable | Pointing at an Activity or View from a longer-lived object |
| `SoftReference` | Only when memory is low | Rarely; prefer `LruCache` |
| `PhantomReference` | After the object is unreachable, to schedule cleanup | Native resource cleanup through `Cleaner` |

**Common mistake:** Reaching for `WeakReference` before fixing who holds the reference and for how long.

**Follow-ups:**

- *Weak vs soft reference?* A weak reference doesn't keep its object from being collected. A soft reference is usually kept until memory is needed.

### 18.3 Visibility and atomicity

**In one line:** sharing data between threads has two separate problems: other threads may not see a write (visibility), and multi-step updates can interleave and lose data (atomicity).

**Say this in the interview:** "Visibility means one thread writes a value but another keeps reading an old copy from a CPU cache or a compiler optimisation. Atomicity means `count++` is really read, add, write, so two threads can lose an update. The Java Memory Model's happens-before rules say when a write is guaranteed visible: releasing a lock, writing a `volatile` field, and starting or joining a thread all create that guarantee. So `@Volatile` fixes visibility for a flag, atomics fix a single counter, and a lock or `Mutex` protects several fields that change together. Best of all is avoiding shared mutable state: immutable data or keeping state on one thread."

**Example:**

```kotlin
// Visibility only: a flag written by one thread, read by another
@Volatile private var cancelled = false
fun cancel() { cancelled = true }
fun loop() { while (!cancelled) doWork() }

// Atomicity for one variable: never @Volatile alone for count++
private val count = AtomicInteger()
fun increment() = count.incrementAndGet()

// Several fields that must change together: a lock
private val lock = Any()
private var balance = 0L
private val history = mutableListOf<Long>()
fun deposit(amount: Long) = synchronized(lock) { balance += amount; history += amount }
```

| Tool | Visibility | Atomicity | Use for |
| --- | --- | --- | --- |
| `@Volatile` | Yes | Single reads and writes only | Flags, double-checked locking |
| `AtomicInteger`, `AtomicReference` | Yes | Yes, one variable | Counters, compare-and-set |
| `synchronized`, `ReentrantLock` | Yes | Yes, a block | Several related fields |
| Coroutine `Mutex` | Yes | Yes, a block | The same, without blocking a thread |
| Thread confinement | Not needed | Not needed | State kept on one thread or dispatcher |
| Immutable data | Not needed | Not needed | Sharing `val` data classes freely |

**Common mistake:** Believing `@Volatile` makes a read-modify-write atomic.

**Follow-ups:**

- *Does an `AtomicInteger` make two related updates atomic?* No. It protects one value. Use a lock, or put the related values in one atomically updated object.

### 18.4 Double-checked locking and deadlocks

**In one line:** double-checked locking creates a singleton lazily with a lock taken only once, and needs `@Volatile`; deadlocks happen when threads wait for each other's locks.

**Say this in the interview:** "I check the instance without a lock, and only if it's null, lock and check again before creating it. The field must be `@Volatile`, otherwise another thread could see a non-null reference to an object whose constructor hasn't finished. In Kotlin I rarely write this by hand: `by lazy` is synchronized by default and Hilt's `@Singleton` handles it. For deadlocks, the rule is to always take locks in the same order, keep critical sections short, and never call unknown code, like callbacks, while holding a lock."

**Example:**

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

**Common mistake:** Leaving out `@Volatile` in hand-written double-checked locking.

**Follow-ups:**

- *Describe a deadlock.* Thread A holds lock 1 and waits for lock 2, while thread B holds lock 2 and waits for lock 1. Neither can continue.

### 18.5 Threads, executors and coroutines

**In one line:** threads are expensive operating-system resources, executors reuse a pool of them, and coroutines are lightweight tasks that share a few threads.

**Say this in the interview:** "Each thread costs about a megabyte of stack, so I almost never create them directly. Java code uses executors and thread pools; `HandlerThread` gives a thread with a message loop for legacy callback APIs like the camera. In Kotlin, coroutines are the default: a suspended coroutine releases its thread, so 10,000 concurrent coroutines can run on a handful of threads, while 10,000 threads would exhaust memory. To bridge, I can wrap an executor with `asCoroutineDispatcher()`."

**Example:**

```kotlin
val ioExecutor = Executors.newFixedThreadPool(4)
val dispatcher = ioExecutor.asCoroutineDispatcher()     // use with withContext(dispatcher) { ... }
```

| Tool | What it is | When to use |
| --- | --- | --- |
| `Thread` | One OS thread, about 1 MB of stack | Almost never directly |
| `ExecutorService` | A reusable pool of threads | Java code, libraries without coroutines |
| `HandlerThread` with `Handler` | A thread with a message loop | Camera callbacks, ordered legacy work |
| Coroutines | Lightweight tasks on shared thread pools | The default for Kotlin Android code |

**Common mistake:** Calling blocking code inside coroutines and assuming they stay lightweight.

**Follow-ups:**

- *Does suspending a coroutine block its thread?* No. It frees the thread. A blocking call inside a coroutine still blocks it.

### 18.6 Design patterns you already use on Android

**In one line:** Android and its libraries are full of classic patterns; name the pattern and point to where you use it.

**Say this in the interview:** "I see them every day: Builder in `Retrofit.Builder` and notifications, Observer in Flow and LiveData, Adapter in RecyclerView, Facade in a repository that hides Room, Retrofit and DataStore, Chain of responsibility in OkHttp interceptors, and Strategy when I swap implementations behind an interface. For example, in checkout each payment method is a strategy, and Hilt injects a map of them, so adding a method means adding a class and a binding without touching the use case."

**Example:**

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

| Pattern | Idea | Android example |
| --- | --- | --- |
| Singleton | One instance for the process | Room database, `OkHttpClient` (Hilt `@Singleton`) |
| Builder | Build complex objects step by step | `NotificationCompat.Builder`, `Retrofit.Builder` |
| Factory | Hide which class gets created | `ViewModelProvider.Factory` |
| Observer | Subscribers react to changes | `Flow`, `StateFlow`, `LiveData`, lifecycle observers |
| Adapter | Make one interface fit another | `RecyclerView.Adapter` turns data into views |
| Facade | One simple API over a complex subsystem | A repository over Room, Retrofit and DataStore |
| Strategy | Swap algorithms behind an interface | Payment processors, caching policies |
| Decorator | Wrap an object to add behaviour | `BufferedInputStream`, a caching repository wrapping a network one |
| Chain of responsibility | Pass a request along handlers | OkHttp interceptors |
| Dependency injection | Receive collaborators instead of creating them | Hilt, Koin |

**Common mistake:** Naming patterns without saying what problem each one solves in your code.

**Follow-ups:**

- *Which pattern does a repository follow?* The Repository pattern. It also acts as a Facade when it hides several data sources behind one API.

### 18.7 SOLID with Android examples

**In one line:** five principles that keep code easy to change: single responsibility, open/closed, Liskov substitution, interface segregation and dependency inversion.

**Say this in the interview:** "The one I lean on most is dependency inversion: my ViewModel depends on an `ArticleRepository` interface, the data layer implements it with Retrofit and Room, and tests swap in a fake. Open/closed is the payment strategy map: new behaviour without editing existing code. And Liskov matters for fakes: a fake repository must honour the same contract as the real one, for example emitting cached data first, or the tests lie."

**Example:**

| Principle | Means | Android example |
| --- | --- | --- |
| Single responsibility | One reason to change | The ViewModel holds screen state; a mapper formats; a data source does networking |
| Open/closed | Extend without editing | New payment methods through the strategy map |
| Liskov substitution | Subtypes behave like their base | A fake repository honours the real contract |
| Interface segregation | Small, focused interfaces | Split `UserRepository` into `ProfileReader` and `ProfileWriter` |
| Dependency inversion | Depend on abstractions | The ViewModel depends on an interface, not on Retrofit |

**Common mistake:** Reciting the five definitions with no example from your own work.

**Follow-ups:**

- *What does dependency inversion look like on Android?* The domain defines a repository interface, and the data layer implements it.

### Interview questions

1. **What is a GC root, and how does it relate to memory leaks?** A starting point the collector treats as always alive: static fields, live threads' local variables, JNI references. A leak is an unneeded object still reachable from a root, such as an Activity in a static field. {Medium}
2. **When would you use `WeakReference`?** When a longer-lived object must point at an Activity or View without keeping it alive. Prefer proper unregistration or lifecycle-aware flows; a weak reference is a fallback. {Medium}
3. **Is `@Volatile var count` enough for a thread-safe counter?** No. It gives visibility, but `count++` is read-modify-write and can lose updates. Use `AtomicInteger`, a lock, a `Mutex`, or keep it on one thread. {Easy}
4. **Why does double-checked locking need `@Volatile`?** Without it, another thread can see the reference before the constructor finishes and use a half-built object. `@Volatile` adds the happens-before guarantee. {Hard}
5. **How do you avoid deadlocks?** Take locks in a fixed order, keep critical sections short, don't call external code while holding a lock, and prefer immutable data, thread confinement or a coroutine `Mutex`. {Medium}
6. **Why are coroutines cheaper than threads?** A suspended coroutine gives its thread back, so thousands share a small pool, while each thread needs its own stack of about a megabyte. {Easy}
7. **Which design patterns do you see in Android?** Builder (Retrofit, notifications), Observer (Flow, LiveData), Adapter (RecyclerView), Facade (repositories), Chain of responsibility (OkHttp interceptors), Factory (ViewModel factories), Singleton (Room via DI). {Easy}
8. **Explain dependency inversion with an example.** The ViewModel depends on an `ArticleRepository` interface; the data layer implements it with Retrofit and Room; tests use a fake, and the network library can change without touching the ViewModel. {Medium}
