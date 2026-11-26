# Coding round

Two styles appear: classic algorithm problems, usually medium difficulty, and practical Android exercises such as building a small screen, fixing a buggy ViewModel or writing a cache. In both, the interviewer grades how you think as much as the code.

### 16.1 How to run a coding interview

**In one line:** clarify, state a brute force, improve it, code while talking, test with an example, then state the complexity.

**Say this in the interview:** "Let me restate the problem and check the edge cases: empty input, duplicates, very large input. The simple approach is to check every pair, which is O(n squared). We can do better with a hash map, trading O(n) memory for O(n) time. I'll code that, then walk through a small example and the edge cases."

**Example, the steps:**

1. **Clarify:** inputs, outputs, constraints, edge cases.
2. **Brute force:** say it and its complexity, even if you won't code it.
3. **Improve:** name the pattern, such as hashing, two pointers or a heap.
4. **Code:** talk while you write, use clear names.
5. **Test:** run a small example by hand, then the edge cases.
6. **Complexity:** time and space, and what you'd change for huge inputs.

**Common mistake:** Coding in silence before confirming the problem and its edge cases.

**Follow-ups:**

- *What if you get stuck?* Say what you are trying, solve a smaller example and ask a focused question.

### 16.2 Topics to revise

**In one line:** most problems use a small set of patterns, and Kotlin's standard library covers the data structures.

**Example:**

| Topic | Typical problems | Kotlin tools |
| --- | --- | --- |
| Arrays and strings, two pointers, sliding window | Longest substring without repeats, two sum, merge intervals | `HashMap`, `IntArray`, `buildString` |
| Hashing | Group anagrams, top-K frequent | `groupingBy { }.eachCount()` |
| Stacks and queues | Valid parentheses, next greater element | `ArrayDeque` |
| Linked lists | Reverse, detect a cycle, merge sorted lists | Classes with `var next` |
| Trees and graphs | BFS and DFS, level order, lowest common ancestor, islands, topological sort | Recursion, `ArrayDeque` |
| Heaps | K closest points, merge K lists | `PriorityQueue(compareBy { })` |
| Binary search | Rotated array search, first bad version | `binarySearch`, manual lo/hi |
| Dynamic programming | Climbing stairs, coin change, longest increasing subsequence | `IntArray(n + 1)` |
| Design | LRU cache, rate limiter | `LinkedHashMap(accessOrder = true)` |

**Common mistake:** Memorizing solutions without being able to explain why each pattern fits.

**Follow-ups:**

- *How should you practise?* Solve problems aloud, within a time limit, and explain the time and space cost.

### 16.3 Two Sum (hashing)

**In one line:** remember each number's index in a map, and for each element check whether its complement was already seen.

**Say this in the interview:** "Brute force checks every pair, O(n squared). Instead I walk once, and for each number look up `target - n` in a map of values I've seen. That's O(n) time and O(n) space."

**Example:**

```kotlin
fun twoSum(nums: IntArray, target: Int): IntArray {
    val seen = HashMap<Int, Int>()                 // value -> index
    nums.forEachIndexed { i, n ->
        seen[target - n]?.let { return intArrayOf(it, i) }
        seen[n] = i
    }
    return intArrayOf()
}
```

**Common mistake:** Adding the current number to the map before checking for its complement, which can use one element twice.

**Follow-ups:**

- *What if the array is already sorted?* Use two pointers from both ends: O(n) time with O(1) extra space.

### 16.4 Longest substring without repeats (sliding window)

**In one line:** keep a window with no repeated characters, and when a repeat appears, move the left edge past its previous position.

**Say this in the interview:** "I keep the last index of each character. As the right edge moves, if the character was seen inside the current window, I move the left edge just past it. The answer is the largest window. Each character is visited once, so it's O(n)."

**Example:**

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

**Common mistake:** Moving the left edge backwards when the repeated character was last seen before the current window.

**Follow-ups:**

- *Why is it O(n) if the window moves from both ends?* Both edges only move forward, so the total number of steps grows linearly.

### 16.5 Number of islands (BFS on a grid)

**In one line:** scan the grid, and each unvisited land cell starts a breadth-first search that marks its whole island as visited.

**Say this in the interview:** "Every time I find a '1' I count an island and flood-fill it with a queue, marking cells as visited. Each cell is processed once, so time and space are O(rows times columns). This modifies the input; if that's not allowed, I'd use a separate visited array."

**Example:**

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
```

**Common mistake:** Marking cells visited only when they leave the queue, so the same cell can be queued several times.

**Follow-ups:**

- *BFS or DFS?* Both work. Recursive DFS is short but can overflow the stack on a large grid, while BFS uses an explicit queue.

### 16.6 Top K frequent elements (heap)

**In one line:** count with a map, then keep a min-heap of size k so the least frequent element is evicted.

**Say this in the interview:** "Sorting all counts would be O(n log n). A min-heap capped at k keeps only the best k, so it's O(n log k). If asked for O(n), I'd use bucket sort by frequency."

**Example:**

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
```

**Common mistake:** Using a max-heap of every element and calling it O(n log k).

**Follow-ups:**

- *Why a min-heap rather than a max-heap?* Its top is the weakest of the k kept so far, so it is cheap to remove when a better item arrives.

### 16.7 LRU cache

**In one line:** a hash map gives O(1) lookup and a doubly linked list keeps usage order, so the least recently used entry is always at the end.

**Say this in the interview:** "In production I'd use `LinkedHashMap` with access order, or Android's `LruCache`. If asked to build it, I combine a `HashMap` from key to node with a doubly linked list: every access moves the node to the front, and when we're over capacity I remove the tail. Sentinel head and tail nodes avoid null checks. Both operations are O(1)."

**Example, the short version:**

```kotlin
class LruCache<K, V>(private val capacity: Int) {
    private val map = object : LinkedHashMap<K, V>(capacity, 0.75f, true) {   // accessOrder = true
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<K, V>) = size > capacity
    }
    @Synchronized fun get(key: K): V? = map[key]
    @Synchronized fun put(key: K, value: V) { map[key] = value }
}
```

**Example, from scratch:**

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
```

**Common mistake:** Moving an entry on write but not on read, so the eviction order is wrong.

**Follow-ups:**

- *How do you prove it works?* Walk through capacity 2: put 1, put 2, get 1, then put 3 evicts 2, because 1 was used more recently.
- *How would you size it by bytes?* Track a running size and evict until under the limit, like `android.util.LruCache.sizeOf`.

### 16.8 Coroutine utilities: debounce, limited concurrency, retry

**In one line:** practical rounds often ask for small coroutine helpers; know these three by heart.

**Say this in the interview:** "Debounce cancels the previous job on each call, so only the last call after a quiet period runs. For limited concurrency I launch all items with `async` but guard the work with a `Semaphore`, so only n run at once. Retry with exponential backoff doubles the delay each attempt and adds random jitter, so many clients don't retry at the same moment, and it only retries errors that are worth retrying."

**Example:**

```kotlin
fun <T> debounce(scope: CoroutineScope, waitMs: Long, action: (T) -> Unit): (T) -> Unit {
    var job: Job? = null
    return { param ->
        job?.cancel()
        job = scope.launch { delay(waitMs); action(param) }
    }
}

suspend fun <T, R> List<T>.mapConcurrently(limit: Int, transform: suspend (T) -> R): List<R> {
    val semaphore = Semaphore(limit)
    return coroutineScope {
        map { item -> async { semaphore.withPermit { transform(item) } } }.awaitAll()
    }
}

suspend fun <T> retryWithBackoff(
    times: Int = 3, initialDelayMs: Long = 500, factor: Double = 2.0, block: suspend () -> T
): T {
    var delayMs = initialDelayMs
    repeat(times - 1) {
        try { return block() } catch (e: IOException) { /* retry only network errors */ }
        delay(delayMs + Random.nextLong(0, delayMs / 2))   // jitter
        delayMs = (delayMs * factor).toLong()
    }
    return block()   // last attempt; the exception propagates
}
```

**Common mistake:** Retrying every error, including cancellation, with no limit or delay.

**Follow-ups:**

- *Debounce vs throttle?* Debounce waits for a quiet period. Throttle limits how often something runs while events keep arriving.

### 16.9 Find the bug

**In one line:** many practical rounds show broken Android code; these five bugs come up again and again.

**Say this in the interview:** "First I'll say what this code should do and what it does instead. Then I'll check the usual causes: lifecycle, threading, cancellation, shared mutable state and repeated work during recomposition. When I find the problem, I'll explain why it happens, make the smallest fix and say how I'd test it."

**Example:**

```kotlin
// Bug 1: keeps collecting while the app is in the background. Fix: repeatOnLifecycle(STARTED)
lifecycleScope.launch { viewModel.state.collect { render(it) } }

// Bug 2: exposes mutable state. Fix: private _state plus asStateFlow()
val state = MutableStateFlow(UiState())

// Bug 3: catching Exception also swallows CancellationException. Fix: rethrow it, or catch specific types
viewModelScope.launch { try { repo.load() } catch (e: Exception) { log(e) } }

// Bug 4: blocks the main thread. Fix: launch a coroutine and call the suspend function
val user = runBlocking { api.getUser() }

// Bug 5: filters on every recomposition and has no keys. Fix: remember or move to the ViewModel, add key
LazyColumn { items(data.filter { it.active }) { Row(it) } }
```

**Common mistake:** Rewriting the code before explaining what causes the bug.

**Follow-ups:**

- *What is your first step?* Work out what should happen and what does happen, and reproduce it before changing the code.

### 16.10 Take-home assignments

**In one line:** a take-home is graded on code quality, structure and judgement as much as on features.

**Say this in the interview:** "In the README I explain how to run it, the architecture, the trade-offs I made, and what I'd do with more time. I keep it simple and complete rather than over-engineered."

**Example, a checklist:**

- README: how to run, architecture choice, trade-offs, next steps.
- Layers: UI, ViewModel and repository, with DI and an immutable `UiState`.
- States: loading, empty, error with retry; rotation and process death handled.
- Tests: ViewModel and repository unit tests, at least one UI test.
- Polish: strings in resources, dark mode, accessibility labels.
- Hygiene: clean commit history, lint and Detekt passing.
- Restraint: a small app split into 12 modules is a red flag.

**Common mistake:** Adding many layers and libraries while leaving core features or tests unfinished.

**Follow-ups:**

- *What goes in the README?* How to run it, your design choices, the trade-offs and what you would improve with more time.

### 16.11 Merge intervals

**In one line:** sort intervals by start time, then merge the current interval with the previous one whenever they overlap.

**Say this in the interview:** "If I sort by start time first, any overlapping intervals sit next to each other. I walk once, either extending the end of the last merged interval or starting a new one. Sorting takes O(n log n) and the pass takes O(n)."

**Example:**

```kotlin
fun mergeIntervals(intervals: Array<IntArray>): Array<IntArray> {
    if (intervals.isEmpty()) return emptyArray()
    intervals.sortBy { it[0] }
    val merged = ArrayList<IntArray>()
    for (curr in intervals) {
        if (merged.isEmpty() || merged.last()[1] < curr[0]) {
            merged.add(curr.copyOf())
        } else {
            merged.last()[1] = maxOf(merged.last()[1], curr[1])
        }
    }
    return merged.toTypedArray()
}
```

**Common mistake:** Overwriting `merged.last()[1] = curr[1]` instead of taking `maxOf`, which shrinks the interval when one range contains another.

**Follow-ups:**

- *How do you check if a person can attend all meetings?* Sort by start time and check whether `intervals[i][0] < intervals[i - 1][1]`.

### 16.12 Rate limiter (sliding window)

**In one line:** keep a queue of recent request timestamps per key, drop entries older than the window, and allow the request only if the queue is under the limit.

**Say this in the interview:** "For a sliding-window rate limiter, I keep an `ArrayDeque<Long>` of timestamps per user or endpoint and pass a clock lambda so unit tests don't sleep. On each call, I evict timestamps older than `now - windowMs` from the front, check `queue.size < maxRequests`, and append `now` if allowed."

**Example:**

```kotlin
class RateLimiter(private val maxRequests: Int, private val windowMs: Long, private val nowMs: () -> Long) {
    private val hits = HashMap<String, ArrayDeque<Long>>()

    @Synchronized
    fun allow(key: String): Boolean {
        val now = nowMs()
        val q = hits.getOrPut(key) { ArrayDeque() }
        while (q.isNotEmpty() && now - q.first() >= windowMs) q.removeFirst()
        if (q.size >= maxRequests) return false
        q.addLast(now)
        return true
    }
}
```

**Common mistake:** Using `System.currentTimeMillis()` directly instead of a monotonic or injected clock, making tests flaky.

**Follow-ups:**

- *Sliding window vs token bucket?* A token bucket uses O(1) memory per key (just tokens and last refill time) instead of storing every timestamp.

### 16.13 Topological sort (dependency order)

**In one line:** track each node's in-degree, start a queue with nodes that have zero dependencies, and peel them off one by one.

**Say this in the interview:** "Resolving module or App Startup initializer order is topological sort. I build an adjacency list and an in-degree count for each node. Any node with in-degree 0 goes into a queue; as I pop each node, I decrement its neighbours' in-degrees and enqueue any that hit 0. If the output has fewer items than the total nodes, there's a dependency cycle."

**Example:**

```kotlin
fun buildOrder(nodes: List<String>, deps: List<Pair<String, String>>): List<String>? {
    val adj = nodes.associateWith { mutableListOf<String>() }
    val inDegree = nodes.associateWith { 0 }.toMutableMap()
    for ((before, after) in deps) {
        adj.getValue(before).add(after)
        inDegree[after] = inDegree.getValue(after) + 1
    }
    val q = ArrayDeque(inDegree.filterValues { it == 0 }.keys)
    val order = ArrayList<String>(nodes.size)
    while (q.isNotEmpty()) {
        val cur = q.removeFirst().also(order::add)
        for (next in adj.getValue(cur)) {
            val deg = inDegree.getValue(next) - 1
            inDegree[next] = deg
            if (deg == 0) q.addLast(next)
        }
    }
    return order.takeIf { it.size == nodes.size }   // null means cycle
}
```

**Common mistake:** Forgetting to detect cycles when `order.size < nodes.size`.

**Follow-ups:**

- *Time and space complexity?* O(V + E) for both, where V is nodes and E is dependency edges.

### 16.14 In-memory cache with TTL

**In one line:** store each value alongside its expiry timestamp, reject expired entries on read, and inject the clock so tests stay deterministic.

**Say this in the interview:** "In Android repos I often need a short-lived cache for config or search results. I wrap each value with `expiresAtMs`, check expiry lazily on `get`, and cap size with a `LinkedHashMap` so it doesn't grow unbounded. Injecting `nowMs: () -> Long` lets unit tests advance time without `delay`."

**Example:**

```kotlin
class TtlCache<K, V>(private val ttlMs: Long, private val maxSize: Int = 100, private val nowMs: () -> Long) {
    private data class Entry<V>(val value: V, val expiresAt: Long)
    private val map = object : LinkedHashMap<K, Entry<V>>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<K, Entry<V>>?) = size > maxSize
    }

    @Synchronized fun put(key: K, value: V) { map[key] = Entry(value, nowMs() + ttlMs) }
    @Synchronized fun get(key: K): V? {
        val entry = map[key] ?: return null
        if (nowMs() >= entry.expiresAt) { map.remove(key); return null }
        return entry.value
    }
}
```

**Common mistake:** Never bounding the cache size or forgetting to remove expired entries on `get`.

**Follow-ups:**

- *How do you test expiry without sleeping?* Pass a fake clock `var time = 0L; TtlCache(ttlMs = 1_000) { time }` and increment `time` in the test.

### Interview questions

1. **Implement an LRU cache with O(1) operations.** Combine a hash map from key to node with a doubly linked list; move nodes to the front on access and evict from the tail when over capacity. In production, `LinkedHashMap` with access order or `LruCache`. {Medium}
2. **Find two numbers that add up to a target.** One pass with a map of seen values to indices, checking for the complement: O(n) time and space. {Easy}
3. **Longest substring without repeating characters?** Sliding window with the last index of each character; move the left edge past repeats. O(n). {Medium}
4. **Count islands in a grid.** BFS or DFS from each unvisited land cell, marking the island as visited. O(rows times columns). {Medium}
5. **Top K frequent elements?** Count with a map, keep a min-heap of size k: O(n log k); bucket sort gives O(n). {Medium}
6. **Write a debounce function with coroutines.** Keep the last job, cancel it on each call, and launch a new one that delays and then runs the action. {Medium}
7. **Run 100 downloads, at most 4 at a time.** `async` for each item inside `coroutineScope`, with a `Semaphore(4)` and `withPermit` around the work, then `awaitAll`. {Hard}
8. **What's wrong with `catch (e: Exception)` inside a coroutine?** It also catches `CancellationException`, so the coroutine ignores cancellation. Rethrow it or catch specific exceptions. {Medium}
9. **What do you put in a take-home README?** How to run it, the architecture and why, trade-offs and shortcuts, and what you'd improve with more time. {Easy}
10. **How do you merge overlapping intervals?** Sort by start time, then walk once: append non-overlapping intervals and extend the last end with `maxOf` when they overlap. O(n log n) time. {Medium}
11. **How would you implement a sliding-window rate limiter in Kotlin?** Store an `ArrayDeque<Long>` of timestamps per key with an injected clock, evict entries older than `now - windowMs`, and allow the call only if `size < maxRequests`. {Medium}
12. **How do you order tasks or initializers that have dependencies?** Use topological sort (Kahn's algorithm): track in-degrees, start a queue with in-degree 0 nodes, decrement neighbours as you pop, and flag a cycle if fewer than all nodes are output. {Medium}
13. **How do you build and test an in-memory cache with a TTL?** Store values with an `expiresAt` timestamp in a bounded `LinkedHashMap`, evict expired entries on `get`, and inject a clock lambda so unit tests can advance time deterministically. {Medium}
