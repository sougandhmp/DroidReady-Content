# Coding round

Two styles appear: classic DSA (usually medium difficulty) and practical Android exercises (build a small screen, fix a buggy ViewModel, write a cache). In both, talk through your approach, state complexity, handle edge cases and write a test or two.

### 16.1 DSA topics to revise

| Topic | Typical problems | Kotlin tools |
| --- | --- | --- |
| Arrays / strings, two pointers, sliding window | Longest substring without repeats, two sum, merge intervals | `HashMap`, `IntArray`, `buildString` |
| Hashing | Group anagrams, top-K frequent | `groupingBy { }.eachCount()` |
| Stacks / queues | Valid parentheses, next greater element | `ArrayDeque` |
| Linked lists | Reverse, detect cycle, merge sorted | Data classes with `var next` |
| Trees / graphs | BFS/DFS, level order, LCA, number of islands, topological sort | Recursion, `ArrayDeque` |
| Heaps | K closest points, merge K lists | `PriorityQueue(compareBy { })` |
| Binary search | Search rotated array, first bad version | `binarySearch`, manual lo/hi |
| Dynamic programming | Climbing stairs, coin change, LIS | `IntArray(n + 1)` |
| Design | LRU cache, rate limiter | `LinkedHashMap(accessOrder = true)` |

### 16.2 Example: LRU cache (very common)

```kotlin
class LruCache<K, V>(private val capacity: Int) {
    private val map = object : LinkedHashMap<K, V>(capacity, 0.75f, true) {   // accessOrder = true
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<K, V>) = size > capacity
    }
    @Synchronized fun get(key: K): V? = map[key]
    @Synchronized fun put(key: K, value: V) { map[key] = value }
}
```

O(1) get and put. Follow-ups: implement it yourself with a `HashMap` + doubly linked list; make it thread-safe; size by bytes (like `android.util.LruCache.sizeOf`).

### 16.3 Example: debounce and throttle utilities

```kotlin
fun <T> debounce(scope: CoroutineScope, waitMs: Long, action: (T) -> Unit): (T) -> Unit {
    var job: Job? = null
    return { param ->
        job?.cancel()
        job = scope.launch { delay(waitMs); action(param) }
    }
}
```

### 16.4 Example: parallel requests with a concurrency limit

```kotlin
suspend fun <T, R> List<T>.mapConcurrently(limit: Int, transform: suspend (T) -> R): List<R> {
    val semaphore = Semaphore(limit)
    return coroutineScope {
        map { item -> async { semaphore.withPermit { transform(item) } } }.awaitAll()
    }
}

val thumbnails = imageUrls.mapConcurrently(limit = 4) { url -> loader.load(url) }
```

### 16.5 Example: retry with exponential backoff

```kotlin
suspend fun <T> retryWithBackoff(
    times: Int = 3, initialDelayMs: Long = 500, factor: Double = 2.0, block: suspend () -> T
): T {
    var delayMs = initialDelayMs
    repeat(times - 1) {
        try { return block() } catch (e: IOException) { /* retry */ }
        delay(delayMs + Random.nextLong(0, delayMs / 2))   // jitter
        delayMs = (delayMs * factor).toLong()
    }
    return block()   // last attempt; exception propagates
}
```

### 16.6 Practical take-home checklist

A take-home is graded on code quality as much as on features:

- Clear README: how to run, architecture choice, trade-offs, what you would do next.
- Layered architecture (UI / ViewModel / repository), DI, immutable `UiState`.
- Loading, empty, error and retry states; rotation and process death handled.
- Unit tests for ViewModel and repository; at least one UI test.
- No hardcoded strings (resources), dark mode, accessibility labels.
- Clean git history with meaningful commits; lint/Detekt passing.
- Don't over-engineer: a small app with 12 modules is a red flag.

### 16.7 Classic "find the bug" snippets

```kotlin
// Bug 1: collecting in lifecycleScope without repeatOnLifecycle -> keeps collecting in background
lifecycleScope.launch { viewModel.state.collect { render(it) } }

// Bug 2: exposing mutable state
val state = MutableStateFlow(UiState())        // should be private + asStateFlow()

// Bug 3: swallowing cancellation
viewModelScope.launch { try { repo.load() } catch (e: Exception) { log(e) } }

// Bug 4: blocking call on main
val user = runBlocking { api.getUser() }

// Bug 5: Compose - new list created every recomposition, no key
LazyColumn { items(data.filter { it.active }) { Row(it) } }   // remember the filter, add key
```
