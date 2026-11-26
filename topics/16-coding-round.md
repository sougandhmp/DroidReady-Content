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

### 16.8 Deeper dive: worked DSA solutions with reasoning

For each problem, say the brute force first, then improve it, and state time and space complexity.

**Two Sum (hashing).** Find indices of two numbers that add up to a target. Brute force checks every pair: O(n²). Better: remember each number's index, and for each element check whether its complement was already seen.

```kotlin
fun twoSum(nums: IntArray, target: Int): IntArray {
    val seen = HashMap<Int, Int>()                 // value -> index
    nums.forEachIndexed { i, n ->
        seen[target - n]?.let { return intArrayOf(it, i) }
        seen[n] = i
    }
    return intArrayOf()
}
// O(n) time, O(n) space
```

**Longest substring without repeating characters (sliding window).** Keep a window `[left, right]` with no repeats. When a repeat appears, move `left` past the previous occurrence.

```kotlin
fun lengthOfLongestSubstring(s: String): Int {
    val lastIndex = HashMap<Char, Int>()
    var left = 0; var best = 0
    for ((right, c) in s.withIndex()) {
        lastIndex[c]?.let { if (it >= left) left = it + 1 }
        lastIndex[c] = right
        best = maxOf(best, right - left + 1)
    }
    return best
}
// "abcabcbb" -> 3 ("abc"). O(n) time, O(min(n, alphabet)) space
```

**Number of islands (BFS on a grid).** Scan the grid; each unvisited land cell starts a BFS that marks its whole island.

```kotlin
fun numIslands(grid: Array<CharArray>): Int {
    val dirs = listOf(1 to 0, -1 to 0, 0 to 1, 0 to -1)
    var count = 0
    for (r in grid.indices) for (c in grid[0].indices) {
        if (grid[r][c] != '1') continue
        count++
        val queue = ArrayDeque<Pair<Int, Int>>().apply { add(r to c) }
        grid[r][c] = '0'                                         // mark visited
        while (queue.isNotEmpty()) {
            val (cr, cc) = queue.removeFirst()
            for ((dr, dc) in dirs) {
                val nr = cr + dr; val nc = cc + dc
                if (nr in grid.indices && nc in grid[0].indices && grid[nr][nc] == '1') {
                    grid[nr][nc] = '0'; queue.add(nr to nc)
                }
            }
        }
    }
    return count
}
// O(rows x cols) time and space
```

Mention that it modifies the input; copy the grid first if that is not allowed.

**Top K frequent elements (heap).** Count with a map, then keep a min-heap of size k so the least frequent is evicted.

```kotlin
fun topKFrequent(nums: IntArray, k: Int): List<Int> {
    val counts = nums.toList().groupingBy { it }.eachCount()
    val heap = PriorityQueue<Map.Entry<Int, Int>>(compareBy { it.value })
    for (e in counts.entries) {
        heap.add(e)
        if (heap.size > k) heap.poll()
    }
    return heap.map { it.key }
}
// O(n log k) time, O(n) space. Follow-up: bucket sort gives O(n).
```

**LRU cache from scratch (hash map + doubly linked list).** The map gives O(1) lookup; the list keeps usage order so the least recently used node is at the tail.

```kotlin
class LRUCache(private val capacity: Int) {
    private class Node(val key: Int, var value: Int) { var prev: Node? = null; var next: Node? = null }
    private val map = HashMap<Int, Node>()
    private val head = Node(0, 0); private val tail = Node(0, 0)        // sentinels avoid null checks
    init { head.next = tail; tail.prev = head }

    fun get(key: Int): Int {
        val node = map[key] ?: return -1
        remove(node); addFirst(node)
        return node.value
    }

    fun put(key: Int, value: Int) {
        map[key]?.let { remove(it) }
        val node = Node(key, value)
        map[key] = node; addFirst(node)
        if (map.size > capacity) {
            val lru = tail.prev!!
            remove(lru); map.remove(lru.key)
        }
    }

    private fun remove(n: Node) { n.prev!!.next = n.next; n.next!!.prev = n.prev }
    private fun addFirst(n: Node) { n.next = head.next; n.prev = head; head.next!!.prev = n; head.next = n }
}
// get and put are O(1)
```

Walk through a small example aloud (capacity 2: put 1, put 2, get 1, put 3 evicts 2) to show it works before the interviewer asks.
