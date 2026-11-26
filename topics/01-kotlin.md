# Kotlin deep dive

Interviewers expect idiomatic, null-safe, immutable-by-default Kotlin, and an understanding of what the compiler generates.

### 1.1 Null safety

**Learn:** Types are non-null by default. `String?` may be null. Use `?.` (safe call), `?:` (Elvis), `let`, and avoid `!!` except where a null is a programming error you want to crash on.

```kotlin
val length = user?.address?.city?.length ?: 0
val name = intent.getStringExtra("name") ?: return  // early exit
```

**Platform types:** Values from Java (`String!`) have unknown nullability. Annotate Java code with `@Nullable/@NonNull` or treat results as nullable.

### 1.2 val vs var, immutability, data classes

- `val` is a read-only reference, not a deeply immutable object. `val list = mutableListOf()` can still change.
- Expose `List<T>` (read-only interface), keep `MutableList<T>` private.
- `data class` generates `equals`, `hashCode`, `toString`, `copy`, `componentN`. Only primary-constructor properties take part.

```kotlin
data class UiState(val loading: Boolean = false, val items: List<Item> = emptyList())
val next = state.copy(loading = true)   // immutable update
```

### 1.3 Sealed classes and interfaces

**Learn:** A closed hierarchy known at compile time, so `when` is exhaustive with no `else`. Ideal for UI state, results and events.

```kotlin
sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>
    data class Success<T>(val data: T) : LoadState<T>
    data class Error(val error: Throwable) : LoadState<Nothing>
}

when (state) {
    LoadState.Loading -> showSpinner()
    is LoadState.Success -> show(state.data)   // smart cast
    is LoadState.Error -> showError(state.error)
}
```

Sealed class vs enum: enum constants are single instances with the same shape; sealed subclasses can carry different data per case.

### 1.4 Scope functions

| Function | Receiver as | Returns | Typical use |
| --- | --- | --- | --- |
| `let` | `it` | lambda result | null checks, transform |
| `run` | `this` | lambda result | compute with object context |
| `with` | `this` | lambda result | group calls on an object |
| `apply` | `this` | the object | configure / builder |
| `also` | `it` | the object | side effects such as logging |

```kotlin
val intent = Intent(context, DetailActivity::class.java).apply {
    putExtra("id", id)
    flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
}
```

### 1.5 Extension functions and properties

Statically resolved helpers. They do not modify the class and cannot access private members. They dispatch on the *declared* type, not the runtime type.

```kotlin
fun Context.toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
val Int.dp: Int get() = (this * Resources.getSystem().displayMetrics.density).toInt()
```

### 1.6 Higher-order functions, inline, noinline, crossinline, reified

- A lambda passed to a normal function allocates a `Function` object. `inline` copies the function body and lambda into the call site, so there is no allocation and non-local `return` works.
- `noinline`: keep one lambda as an object (to store or pass on).
- `crossinline`: lambda is inlined but called from another context (e.g. inside a `Runnable`), so non-local return is forbidden.
- `reified`: only in inline functions; the generic type is available at runtime.

```kotlin
inline fun <reified T : Activity> Context.start() =
    startActivity(Intent(this, T::class.java))

context.start<SettingsActivity>()
```

### 1.7 Generics and variance

- `out T` (covariant): producer only. `List<out T>` means a `List<Cat>` is a `List<Animal>`.
- `in T` (contravariant): consumer only. `Comparator<in T>`.
- Invariant by default: `MutableList<Cat>` is **not** a `MutableList<Animal>`.
- Star projection `List<*>`: unknown type, read as `Any?`.
- Mnemonic: **PECS** (producer extends, consumer super) in Java = `out` / `in` in Kotlin.

### 1.8 Delegation

```kotlin
// Property delegation
val repo by lazy { Repository() }                   // thread-safe by default (SYNCHRONIZED)
var name by Delegates.observable("") { _, old, new -> log("$old -> $new") }
private val viewModel: MainViewModel by viewModels()

// Class delegation: composition instead of inheritance
class LoggingList<T>(private val inner: MutableList<T>) : MutableList<T> by inner {
    override fun add(element: T): Boolean { log("add"); return inner.add(element) }
}
```

### 1.9 Other things you must know

- **`object` / `companion object`:** singletons; `companion` members are static-like; use `@JvmStatic` for Java callers.
- **`lateinit` vs `lazy`:** `lateinit var` for non-null values set later (DI, `onCreate`), not for primitives; `lazy` for `val` computed on first access.
- **`const val`:** compile-time constant, inlined; only primitives and String.
- **Value classes:** `@JvmInline value class UserId(val raw: String)` gives type safety with no allocation in most cases.
- **Equality:** `==` is structural (`equals`), `===` is referential.
- **Collections vs sequences:** `list.map{}.filter{}` creates intermediate lists; `asSequence()` is lazy and better for large chains with early termination.
- **`typealias`, destructuring, `takeIf`, `require`/`check`/`error`.**
- **K2 compiler:** Kotlin 2.x ships the new K2 compiler (faster builds, smarter smart-casts). Compose's compiler plugin now ships with Kotlin itself.

### 1.10 Deeper dive: what the compiler actually does

**Lambdas without `inline`.** Each lambda becomes an object implementing `Function1<P, R>` (or a static singleton if it captures nothing). If it captures a local `var`, Kotlin wraps that variable in a `Ref` object so the lambda can change it.

```kotlin
fun countClicks(button: Button) {
    var clicks = 0                      // becomes IntRef because the lambda mutates it
    button.setOnClickListener { clicks++ }
}
```

In a hot loop, each call that creates a capturing lambda allocates. That is exactly why `forEach`, `map`, `filter` on collections are `inline`: no lambda object is created at all.

**Non-local return in practice.**

```kotlin
fun findAdmin(users: List<User>): User? {
    users.forEach { if (it.isAdmin) return it }   // returns from findAdmin, allowed because forEach is inline
    return null
}

users.forEach { if (!it.active) return@forEach }  // label: acts like 'continue'
```

**Type erasure and `reified`.** On the JVM, `List<String>` and `List<Int>` are both just `List` at runtime. A normal generic function cannot check `x is T`. An `inline` function with `reified T` has the real type pasted in at each call site.

```kotlin
// Without reified: you must pass the class
fun <T> Gson.parse(json: String, type: Class<T>): T = fromJson(json, type)

// With reified: call sites read naturally
inline fun <reified T> Json.parse(json: String): T = decodeFromString<T>(json)
val user = json.parse<User>(body)

// Filtering by runtime type
inline fun <reified T> List<Any>.only(): List<T> = filterIsInstance<T>()
```

### 1.11 Deeper dive: collections vs sequences, with numbers

```kotlin
val result = (1..1_000_000).toList()
    .map { it * 2 }        // allocates a list of 1,000,000
    .filter { it % 3 == 0 } // allocates another list of ~333,333
    .first()                // we only needed one element

val fast = (1..1_000_000).asSequence()
    .map { it * 2 }
    .filter { it % 3 == 0 }
    .first()                // processes elements one by one; stops after the 3rd element
```

Collections are **eager** and process each step for all elements (horizontal). Sequences are **lazy** and push each element through the whole chain (vertical), stopping early. Rules of thumb: use collections for small lists or single operations (they are simpler and often faster due to less overhead); use sequences for long chains on large data, or when you use `first`, `take`, `find`.

### 1.12 Deeper dive: modelling with sealed types and value classes

A senior uses the type system to make invalid states impossible. Compare:

```kotlin
// Weak: 8 combinations, several of them invalid (loading AND error AND data?)
data class ProfileState(val loading: Boolean, val user: User?, val error: String?)

// Strong: exactly 3 valid states
sealed interface ProfileState {
    data object Loading : ProfileState
    data class Content(val user: User, val isRefreshing: Boolean = false) : ProfileState
    data class Failed(val message: String, val canRetry: Boolean) : ProfileState
}
```

Value classes stop you mixing up IDs of the same primitive type:

```kotlin
@JvmInline value class UserId(val value: String)
@JvmInline value class OrderId(val value: String)

fun cancel(order: OrderId, by: UserId) { /* ... */ }
cancel(userId, orderId)   // compile error: arguments swapped, caught for free
```

### 1.13 Deeper dive: contracts, `require`, `check` and smart casts

```kotlin
fun transfer(amount: Long, from: Account?) {
    require(amount > 0) { "amount must be positive, was $amount" }   // IllegalArgumentException: caller's fault
    checkNotNull(from) { "source account missing" }                     // IllegalStateException: our state is wrong
    from.debit(amount)                                                   // smart cast: from is non-null here
}
```

`requireNotNull` and `checkNotNull` use Kotlin **contracts** to tell the compiler the value is non-null afterwards. You can write your own:

```kotlin
@OptIn(ExperimentalContracts::class)
fun String?.isUsable(): Boolean {
    contract { returns(true) implies (this@isUsable != null) }
    return !isNullOrBlank()
}

if (name.isUsable()) println(name.length)   // smart cast works
```

### 1.14 Deeper dive: the `equals`/`hashCode` trap with data classes

```kotlin
data class Item(val id: Int) { var quantity = 0 }   // quantity is NOT in equals/hashCode

val a = Item(1).apply { quantity = 5 }
val b = Item(1).apply { quantity = 9 }
println(a == b)   // true - surprising!
```

Also, never put a data class with `var` properties into a `HashSet` and then change those properties: its hash changes and the set can no longer find it. Keep data classes immutable.

### 1.15 Higher-order functions in depth

**Learn:** A higher-order function takes a function as a parameter, returns a function, or both. Kotlin treats functions as values: you can store them in variables, pass them around and return them. This replaces most of Java's single-method callback interfaces (`OnClickListener`, `Runnable`, `Comparator`).

**Function types.**

A function type lists the parameter types, an arrow, and the return type.

| Type | Meaning | Example value |
| --- | --- | --- |
| `() -> Unit` | No input, no result | `{ println("hi") }` |
| `(String) -> Int` | Takes a String, returns an Int | `{ s -> s.length }` |
| `(Int, Int) -> Int` | Two Ints in, one Int out | `{ a, b -> a + b }` |
| `((Int) -> Unit)?` | A nullable function (note the parentheses) | `null` |
| `String.(Int) -> String` | Function with a receiver: called on a String | `{ n -> this.repeat(n) }` |
| `suspend () -> User` | A suspending function | `{ api.getUser() }` |

Parameter names are optional and act as documentation: `(x: Int, y: Int) -> Point`. Arrows are right-associative, so `(Int) -> (Int) -> Unit` is a function that returns another function.

**Writing a higher-order function.**

```kotlin
// Takes a function as a parameter
fun <T> List<T>.countWhere(predicate: (T) -> Boolean): Int {
    var count = 0
    for (item in this) if (predicate(item)) count++   // invoke it like a normal function
    return count
}

val adults = people.countWhere { it.age >= 18 }       // trailing lambda, 'it' is the single parameter
```

Calling `predicate(item)` is the same as `predicate.invoke(item)`. A nullable function is called with `onDone?.invoke()`.

**Five ways to create a function value.**

```kotlin
// 1. Lambda
val square: (Int) -> Int = { x -> x * x }

// 2. Anonymous function (explicit return type; 'return' returns from this function only)
val isEven = fun(x: Int): Boolean { return x % 2 == 0 }

// 3. Function reference to a top-level or member function
fun isOdd(x: Int) = x % 2 != 0
val odds = numbers.filter(::isOdd)
val lengths = words.map(String::length)          // unbound: the receiver becomes the first parameter
val greet = "Hi"::plus                           // bound: the receiver is fixed -> (Any?) -> String

// 4. Constructor reference
val users = names.map(::User)                    // calls User(name) for each name

// 5. A class implementing a function type
class Doubler : (Int) -> Int { override fun invoke(x: Int) = x * 2 }
val d: (Int) -> Int = Doubler()
```

Function references are common in Android code: `onClick = viewModel::onRefresh` passes a stable reference to Compose, and `flow.map(ArticleEntity::toDomain)` maps without writing a lambda.

**Lambda syntax rules to know.**

- The last expression in a lambda is its return value; there is no `return` keyword unless you use a label (`return@map value`).
- If the last parameter is a function, put the lambda outside the parentheses (trailing lambda). If it is the only argument, drop the parentheses: `run { ... }`.
- A single parameter can be referred to as `it`. Use a name when nesting lambdas, so readers know which `it` is meant.
- Use `_` for unused parameters: `map.forEach { (_, value) -> println(value) }`.
- Destructure data classes and pairs in parameters: `pairs.map { (a, b) -> a + b }`.

**Closures: lambdas capture their surroundings.**

A lambda can read and change variables from the scope where it was created, even after that scope has returned.

```kotlin
fun makeCounter(): () -> Int {
    var count = 0                 // captured by the lambda below
    return { ++count }            // returns a function
}

val next = makeCounter()
next(); next()
println(next())                   // 3: each counter keeps its own 'count'
```

Android warning: a lambda that captures an Activity, View or Fragment keeps it alive as long as the lambda lives. A listener stored in a singleton, or a long `postDelayed` callback, can leak the whole screen this way.

**Functions that return functions.**

```kotlin
fun debounceClick(intervalMs: Long = 500, onClick: () -> Unit): () -> Unit {
    var last = 0L
    return {
        val now = SystemClock.elapsedRealtime()
        if (now - last >= intervalMs) { last = now; onClick() }
    }
}

Button(onClick = remember { debounceClick { viewModel.submit() } }) { Text("Pay") }   // stops double taps
```

Returning a function lets you build behaviour from smaller parts. Other examples are a logging wrapper around any suspend call, or a validator built from rules: `val validate = allOf(notBlank, maxLength(50))`.

**Lambdas with receivers and DSLs.**

In a function type with a receiver, `A.() -> Unit`, the lambda's body runs as if it were a member of `A`, so `this` is the receiver and its members can be called directly. This is how `apply`, `buildString`, `buildList`, Gradle Kotlin DSL and Compose's `LazyListScope` work.

```kotlin
class RequestBuilder {
    var url = ""
    private val headers = mutableMapOf<String, String>()
    fun header(name: String, value: String) { headers[name] = value }
    fun build() = Request(url, headers.toMap())
}

fun request(block: RequestBuilder.() -> Unit): Request = RequestBuilder().apply(block).build()

val req = request {
    url = "https://api.example.com/articles"   // 'this' is the RequestBuilder
    header("Accept", "application/json")
}
```

The standard library uses the same idea everywhere:

```kotlin
val csv = buildString { append("id,title\n"); items.forEach { append("${it.id},${it.title}\n") } }
LazyColumn { items(articles) { ArticleRow(it) } }   // items() is a member of LazyListScope, the receiver
```

**SAM conversions and `fun interface`.**

A SAM (single abstract method) interface from Java, such as `Runnable` or `View.OnClickListener`, can be created from a lambda:

```kotlin
button.setOnClickListener { view -> viewModel.onBuy() }   // lambda converted to View.OnClickListener
handler.post { refresh() }                                // converted to Runnable
```

For your own Kotlin interfaces, declare them as `fun interface` to get the same conversion:

```kotlin
fun interface PriceFormatter { fun format(cents: Long): String }

val aud = PriceFormatter { cents -> "A$" + "%.2f".format(cents / 100.0) }
```

When to choose which: use a plain function type `(Long) -> String` for simple callbacks. Use a `fun interface` when you want a named type in public APIs, documentation, or Java callers, or when the type may later need default methods.

**Performance: `inline`, `noinline`, `crossinline`.**

Each lambda passed to a normal function is an object; capturing lambdas are allocated on each call. Marking a higher-order function `inline` copies its body and the lambda's body into the call site, so no object is created and non-local `return` works (see 1.6 and 1.10). Standard library functions like `map`, `filter`, `forEach`, `let` and `apply` are inline for this reason.

```kotlin
inline fun <T> measure(tag: String, block: () -> T): T {
    val start = System.nanoTime()
    return block().also { Log.d(tag, "took ${(System.nanoTime() - start) / 1_000_000} ms") }
}

val feed = measure("feed") { repository.loadFeed() }   // no lambda allocation
```

Do not inline large functions or functions whose lambda is stored for later; that is what `noinline` is for. Use `crossinline` when the lambda is called from another context, like inside a `Runnable` or another lambda.

**Common standard-library higher-order functions.**

| Function | What it does | Example |
| --- | --- | --- |
| `map` / `mapNotNull` | Transform each item (dropping nulls) | `dtos.mapNotNull { it.toDomainOrNull() }` |
| `filter` / `filterNot` | Keep matching items | `items.filter { it.inStock }` |
| `fold` / `reduce` | Combine into one value | `cart.fold(0L) { sum, i -> sum + i.price }` |
| `groupBy` / `associateBy` | Build maps | `articles.groupBy { it.topic }` |
| `sortedBy` / `sortedWith` | Sort by a key or comparator | `sortedWith(compareBy({ it.lastName }, { it.firstName }))` |
| `any` / `all` / `none` | Test items | `if (fields.all { it.isValid }) submit()` |
| `partition` | Split into two lists | `val (paid, unpaid) = invoices.partition { it.paid }` |
| `takeIf` / `takeUnless` | Value or null | `input.takeIf { it.isNotBlank() }` |
| `use` | Run then close a resource | `file.bufferedReader().use { it.readText() }` |

**Android examples in one place.**

```kotlin
// Compose: events up as function parameters
@Composable
fun ArticleRow(article: ArticleUi, onClick: (String) -> Unit, onBookmark: (String, Boolean) -> Unit) { /* ... */ }

// Coroutines: a suspend lambda as a parameter
suspend fun <T> retry(times: Int, block: suspend () -> T): T { /* ... */ }

// Flow operators are higher-order functions
repo.observe().map { it.toUi() }.filter { it.isNotEmpty() }

// Activity Result API: callback lambda
val pick = registerForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri -> uri?.let(::showImage) }
```

### 1.16 Other language features you may be asked about

**Operator overloading.** Implement a function marked `operator` with a fixed name to use symbols with your types.

```kotlin
data class Money(val cents: Long) {
    operator fun plus(other: Money) = Money(cents + other.cents)
    operator fun times(qty: Int) = Money(cents * qty)
    operator fun compareTo(other: Money) = cents.compareTo(other.cents)
}
val total = price * 3 + shipping
if (total > limit) showWarning()
```

Other operator names: `get`/`set` (indexing `a[i]`), `contains` (`in`), `invoke` (`a()`), `component1..N` (destructuring), `rangeTo` (`..`), `iterator` (`for` loops).

**Infix functions.** A member or extension with one parameter, marked `infix`, can be called without dots and parentheses: `1 to "one"` is `1.to("one")`. Use sparingly, for DSL-like readability.

```kotlin
infix fun Int.percentOf(total: Int) = total * this / 100
val discount = 15 percentOf 200   // 30
```

**Generic constraints.** Limit a type parameter with an upper bound, or several bounds with `where`.

```kotlin
fun <T : Comparable<T>> List<T>.largest(): T? = maxOrNull()

fun <T> copyIfReady(item: T) where T : Parcelable, T : Validatable { /* ... */ }
```

**Type aliases.** Give long function types or generic types a readable name. No new type is created; it is only an alias.

```kotlin
typealias OnArticleClick = (articleId: String) -> Unit
typealias ArticleCache = MutableMap<String, List<Article>>
```

### 1.17 Java interoperability

Most large Android codebases mix Java and Kotlin, and SDKs written in Kotlin are often called from Java. Know both directions.

**Calling Kotlin from Java.**

| Kotlin | What Java sees | Fix for a nicer Java API |
| --- | --- | --- |
| Top-level `fun format()` in `Utils.kt` | `UtilsKt.format()` | `@file:JvmName("Utils")` gives `Utils.format()` |
| `companion object { fun create() }` | `Foo.Companion.create()` | `@JvmStatic` gives `Foo.create()` |
| `companion object { val TAG = "x" }` | `Foo.Companion.getTAG()` | `const val` (primitives, String) or `@JvmField` gives a static field |
| `fun draw(color: Int = RED)` | Only `draw(int)` with all parameters | `@JvmOverloads` generates `draw()` too |
| `fun save()` that throws `IOException` | No `throws` clause, so Java can't catch `IOException` | `@Throws(IOException::class)` |
| Two extensions that clash after type erasure | Compile error | `@JvmName("filterValidInt")` on one of them |

```kotlin
@file:JvmName("Analytics")
package com.example.analytics

class Tracker @JvmOverloads constructor(
    private val endpoint: String,
    private val batchSize: Int = 20,
    private val debug: Boolean = false
) {
    companion object {
        const val VERSION = "3.1.0"
        @JvmStatic fun createDefault(): Tracker = Tracker("https://events.example.com")
    }

    @Throws(IOException::class)
    fun flush() { /* ... */ }
}
```

```java
// Java callers now get a natural API
Tracker t = new Tracker("https://events.example.com");   // overload from @JvmOverloads
Tracker d = Tracker.createDefault();                    // static thanks to @JvmStatic
String v = Tracker.VERSION;
try { t.flush(); } catch (IOException e) { /* compiles thanks to @Throws */ }
```

Kotlin also adds runtime null checks on public functions with non-null parameters: if Java passes `null`, the call fails at once with a `NullPointerException` that names the parameter, instead of failing later somewhere else.

**Calling Java from Kotlin.**

- Java types without nullability annotations become **platform types** (`String!`). Kotlin trusts you; a wrong guess crashes at runtime. Add `@Nullable`/`@NonNull` (AndroidX or JSpecify) to Java code you own.
- Java getters and setters appear as properties: `view.getVisibility()` becomes `view.visibility`.
- Java SAM interfaces accept lambdas: `executor.execute { work() }`.
- Java checked exceptions are not checked in Kotlin, so you must remember to catch them.
- Escape Kotlin keywords used as Java names with backticks, for example Mockito's `when` method.

### 1.18 What's new in Kotlin 2.2 and 2.3

Interviewers like to hear that you follow the language. Features that are **stable** now:

**Guard conditions in `when`** (stable in 2.2): add an `if` to a branch of a `when` with a subject, without nesting.

```kotlin
fun label(state: UploadState): String = when (state) {
    is UploadState.Running if state.progress > 0.9f -> "Almost done"
    is UploadState.Running -> "Uploading ${(state.progress * 100).toInt()}%"
    is UploadState.Failed if state.canRetry -> "Failed - tap to retry"
    is UploadState.Failed -> "Failed"
    UploadState.Done -> "Uploaded"
}
```

**Non-local `break` and `continue`** (stable in 2.2): use them inside lambdas passed to inline functions, such as `forEach`.

```kotlin
for (batch in batches) {
    batch.items.forEach { item ->
        if (item.isCorrupt) continue      // skips to the next batch
        if (quotaExceeded()) break        // leaves the outer for loop
        upload(item)
    }
}
```

**Multi-dollar string interpolation** (stable in 2.2): with a `$$` prefix, a single `$` is literal and `$$name` interpolates. Handy for JSON schemas, regex and templates that contain `$`.

```kotlin
val schema = $$"""{ "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "$$title" }"""
```

**Nested type aliases** (stable in 2.3): declare a `typealias` inside a class.

```kotlin
class ArticleRepository {
    typealias Cache = MutableMap<String, List<Article>>
    private val cache: Cache = mutableMapOf()
}
```

**Data-flow-based exhaustiveness for `when`** (stable in 2.3): the compiler remembers which cases you already handled with earlier checks, so you no longer need a dummy `else`.

**`return` in expression bodies with an explicit return type** (enabled by default in 2.3):

```kotlin
fun discount(user: User?): Int = user?.tier?.discount ?: return 0
```

**Experimental or preview features** worth recognising (don't rely on them in production code without opting in):

- **Context parameters** (preview in 2.2): `context(logger: Logger) fun sync() { logger.info("...") }` passes dependencies implicitly; it replaces the older context receivers.
- **Explicit backing fields** (experimental in 2.3): removes the `_state` / `state` pair in ViewModels.

```kotlin
// Today
private val _city = MutableStateFlow("")
val city: StateFlow<String> get() = _city

// With explicit backing fields (opt-in)
val city: StateFlow<String>
    field = MutableStateFlow("")
```

- **Unused return value checker** (experimental in 2.3): warns when you ignore a function's result, e.g. calling `list.plus(item)` and forgetting the returned list.

### Interview questions

1. **Why is `!!` a code smell?** It converts a compile-time guarantee into a runtime crash. Prefer early return, `requireNotNull` with a message, or modelling the state so null cannot happen. {Easy}
2. **What does `inline` buy you, and when is it harmful?** It removes lambda allocation and enables `reified`. It bloats bytecode if the function body is large; only inline small functions that take lambdas. {Medium}
3. **`data class` inheritance?** A data class cannot be `open`. It can implement interfaces or extend a sealed class. {Easy}
4. **How does `lazy` work under the hood?** It holds an initializer and a value field; the default mode uses double-checked locking. Use `LazyThreadSafetyMode.NONE` on the main thread for slight speed-up. {Medium}
5. **Difference between `List` and `MutableList` when passing to Java?** Java sees both as `java.util.List` and can mutate it; read-only is a compile-time view only. {Medium}
6. **What is a higher-order function, and how is it different from a Java callback interface?** A function that takes or returns a function. Kotlin has real function types, so you don't need an interface per callback, lambdas are short, and `inline` removes the lambda allocation. {Easy}
7. **What is a lambda with receiver, and where is it used?** Its type is `A.() -> R`; inside the lambda, `this` is the receiver. It powers `apply`, `buildString`, Compose scopes such as `LazyListScope`, the Gradle Kotlin DSL and type-safe builders. {Medium}
8. **Why can a lambda cause a memory leak on Android?** It captures variables from its scope, including the enclosing Activity or Fragment. If a longer-lived object keeps the lambda (a singleton listener, a delayed Handler callback), the screen can't be garbage collected. {Medium}
9. **What does `@JvmOverloads` do, and when do you need it?** Java can't use Kotlin default arguments, so it only sees the full signature. `@JvmOverloads` generates extra overloads that drop the defaulted parameters from the right. You need it for Kotlin APIs called from Java, including custom View constructors. {Easy}
10. **What are guard conditions in `when`?** Since Kotlin 2.2 (stable), a branch of a `when` with a subject can add `if`, for example `is Failed if state.canRetry ->`. This avoids nested `if` or `when` blocks inside a branch. {Easy}
