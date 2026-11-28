# Kotlin

Interviewers use Kotlin questions to check two things: that you write safe, idiomatic code, and that you understand what the compiler does with it. Each concept below follows the same pattern: one line, what to say, an example, how it works, and follow-ups.

### 1.1 Null safety

**In one line:** Kotlin's type system separates types that can hold `null` (`String?`) from types that can't (`String`), so most null-pointer crashes become compile errors.

**Say this in the interview:** "In Kotlin, types are non-null by default. If something can be null, I have to say so with `?`, and then the compiler forces me to handle it: with a safe call `?.`, the Elvis operator `?:` for a default, or a smart cast after a null check. I avoid `!!` because it turns a compile-time guarantee back into a runtime crash. The weak spot is Java code: its types come in as platform types, so I add nullability annotations or treat them as nullable."

**Example:**

```kotlin
val city: String? = user?.address?.city          // safe call: null if any link is null
val length = city?.length ?: 0                   // Elvis: default when null
val query = intent.getStringExtra("q") ?: return // early exit if missing

fun transfer(from: Account?, amount: Long) {
    require(amount > 0) { "amount must be positive" }   // caller's mistake -> IllegalArgumentException
    checkNotNull(from) { "no source account" }          // our state is wrong -> IllegalStateException
    from.debit(amount)                                  // smart cast: from is non-null here
}
```

**How it works:**

- The compiler tracks nullability in types and smart-casts after checks (`if (x != null)`, `checkNotNull`, `requireNotNull`).
- Public Kotlin functions get runtime null checks on their non-null parameters, so Java passing `null` fails immediately with a clear message.
- Java types without annotations are **platform types** (`String!`): Kotlin lets you treat them either way, and a wrong guess crashes at runtime.
- `requireNotNull` and `checkNotNull` use **contracts** to tell the compiler the value is non-null afterwards.

**Common mistake:** Using `!!` to quiet the compiler. It only moves the crash to runtime.

**Follow-ups:**

- *Why is `!!` a code smell?* It throws an NPE at runtime; prefer an early return, a default, or `requireNotNull` with a message.
- *`require` vs `check`?* `require` validates arguments (the caller's fault); `check` validates the object's own state (see section 1.16).
- *When is `!!` acceptable?* Only when `null` strictly means a programmer bug and crashing immediately is intended: in unit tests (to fail fast), for proven invariants the compiler can't smart-cast (such as `_binding!!` between `onCreateView` and `onDestroyView`, or an entry just inserted into a map), or for required screen/contract arguments—though `requireNotNull(arg) { "message" }` or `checkNotNull(...)` is still preferred for clearer crash diagnostics. Never use `!!` on network, database, user-input, or unannotated Java values.
- *Why does smart-casting fail on a `var` property?* A `var` (or a `val` with a custom `get()`) could change between the null check and its use; capture it in a local `val current = x` or use `x?.let { ... }`.
- *What is the trap with `?.let { ... } ?: run { ... }`?* If the `let` block itself returns `null`, the Elvis `?:` branch runs too! Use a plain `if (x != null) ... else ...` when you don't need a non-null transformed result.

### 1.2 val, var, immutability and data classes

**In one line:** `val` is a read-only reference, `var` is mutable, immutability prevents shared-state bugs, and a `data class` generates `equals`, `hashCode`, `toString` and `copy` for model classes.

**Say this in the interview:** "I default to `val` and immutable data, because immutable objects are thread-safe and easy to reason about. Note that `val` only means the reference can't be reassigned; a `val` pointing to a `MutableList` can still be mutated. For UI state I use `data class`es and update them with `copy()`, exposing read-only `List`s while keeping `MutableList` private."

**`val` vs `var`:** `val` assigns a read-only reference once (compiled to a `final` field on JVM, though a `val` with a custom `get()` can still return different values). `var` allows reassignment.

```kotlin
val name = "Sam"       // cannot reassign name
var count = 0
count++                // allowed
```

**Immutability (`List` vs `MutableList`):** Kotlin separates read-only collection interfaces (`List`, `Set`, `Map`) from mutable ones (`MutableList`). A `val` reference to a `MutableList` only locks the variable, not the underlying collection.

```kotlin
val items = mutableListOf("a", "b")
items.add("c")         // compiles: the list itself is mutable, only the reference is val
val readOnly: List<String> = items.toList()   // defensive immutable snapshot
```

**`data class`:** A class for holding data. The compiler generates `equals()`, `hashCode()`, `toString()`, `copy()`, and `componentN()` destructuring functions from **primary constructor** properties only. Data classes cannot be `open`, `abstract`, `sealed`, or `inner`, though they can implement interfaces or extend a `sealed class`. `copy()` is shallow—nested mutable objects are still shared.

```kotlin
data class CartUiState(val items: List<CartItem> = emptyList(), val isLoading: Boolean = false)

private val _state = MutableStateFlow(CartUiState())
fun onLoading() = _state.update { it.copy(isLoading = true) }   // new object, old one untouched
val (items, loading) = _state.value                           // destructuring via component1/component2
```

**How it works:**

- A data class generates `equals`/`hashCode`/`toString`/`copy`/`componentN` from the **primary constructor** properties only.
- Data classes can't be `open`, but can implement interfaces or extend sealed types.
- `copy` is shallow: nested mutable objects are shared.

**Common mistake:** Treating `val` as deep immutability. A `val` can still point to a list that changes.

**Follow-ups:**

- *What's the trap with properties declared in the class body?* They are not part of `equals`. `data class Item(val id: Int) { var qty = 0 }`: two items with different `qty` are still equal.
- *Why not put a data class with `var` fields in a `HashSet`?* If a field changes, its hash changes and the set can't find it any more.
- *`val` vs `const val`?* `const val` is a compile-time constant (primitives and `String`), inlined where used; `val` is read at runtime.

### 1.3 Sealed classes, enums and value classes

**In one line:** sealed types model closed hierarchies where each case can carry its own data, enums represent a fixed set of singleton constants, and value classes wrap a single value with zero allocation in most cases.

**Say this in the interview:** "I use `sealed` types to model states where each case has different data, like UI state or network results, so `when` is checked exhaustively at compile time. I use `enum class` when the cases are fixed singletons with the same shape, like days or sort orders. And I use `@JvmInline value class` for type-safe IDs or units without paying for an extra heap object."

**Sealed class & sealed interface:** A closed hierarchy whose direct subclasses must be declared in the same package and module, so the compiler knows every subtype at compile time and requires no `else` branch in `when`. Constructors are `protected` by default (can be `private`). Use a `sealed interface` when subtypes don't share state or need to implement multiple hierarchies; use a `sealed class` when they share constructor parameters or state.

```kotlin
sealed interface ProfileState {
    data object Loading : ProfileState
    data class Content(val user: User) : ProfileState
    data class Error(val message: String, val canRetry: Boolean) : ProfileState
}

when (state) {                                  // exhaustive: no 'else' needed
    ProfileState.Loading -> showSpinner()
    is ProfileState.Content -> show(state.user)
    is ProfileState.Error -> showError(state.message)
}
```

**Enum class:** A fixed set of singleton constants, each of which is an instance of the enum class. Enums can hold constructor properties, declare methods, and implement interfaces (but cannot extend classes). Since Kotlin 1.9, prefer `entries` (returns an immutable `EnumEntries` list) over `values()` (which allocates a new array on every call).

```kotlin
enum class SortOrder(val label: String) {
    NEWEST("Newest"),
    POPULAR("Most popular");
    fun isDefault() = this == NEWEST
}
val all = SortOrder.entries                      // no array allocation unlike values()
```

**Value class (`@JvmInline value class`):** Wraps a single `val` property for compile-time type safety without runtime allocation—the compiler unboxes it to the underlying type in most call sites. It cannot have `init` backing fields or extend classes (only interfaces), and it gets boxed back into a wrapper object when used as a nullable type, generic type argument, or via an interface.

```kotlin
@JvmInline value class UserId(val raw: String)
@JvmInline value class OrderId(val raw: String)
fun cancel(order: OrderId, by: UserId) { }
// cancel(userId, orderId)                       // compile error: arguments swapped
```

**How it works:**

- All direct subclasses of a sealed type must be in the same package and module, so the compiler knows the full list.
- Compare the weak alternative `data class State(val loading: Boolean, val user: User?, val error: String?)`: 8 combinations, several impossible. Sealed types make invalid states unrepresentable.
- A value class is usually compiled to its single underlying value, so there's no object allocation (it is boxed when used as a generic or nullable type).

**Common mistake:** Adding an `else` branch to a `when` over a sealed type, which hides the compile error you would get for a new subtype.

**Follow-ups:**

- *Sealed class vs enum?* Enum constants are single instances with the same shape; sealed subtypes can have different properties and many instances.
- *Sealed class vs sealed interface?* A class can implement several sealed interfaces; use a sealed class when subtypes share state or constructor logic.

### 1.4 Scope functions

**In one line:** `let`, `run`, `with`, `apply` and `also` run a block of code on an object so you don't have to repeat its name.

**Say this in the interview:** "Kotlin has five scope functions. They all run a lambda in the context of an object, and they differ in only two ways: whether the lambda sees the object as `this` or `it`, and whether the call returns the object itself or the lambda's result. `apply` and `also` return the object, so I use `apply` to configure something and `also` for side effects like logging. `let`, `run` and `with` return the result, so I use `?.let` for nullable values and `run` or `with` to compute something from an object's members."

**Example:**

```kotlin
val intent = Intent(context, DetailActivity::class.java).apply {   // configure, get the object back
    putExtra("id", articleId)
    flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
}
val user = repo.loadUser(id).also { Log.d(TAG, "loaded ${it.id}") }  // side effect, same object back
savedState?.getString(KEY)?.let { viewModel.restore(it) }           // only when not null
val isValid = form.run { email.isNotBlank() && password.length >= 8 } // compute a result
with(binding) { title.text = article.title; author.text = article.author }  // group calls
```

| Function | Object is | Returns | Use for |
| --- | --- | --- | --- |
| `apply` | `this` | the object | Configuring |
| `also` | `it` | the object | Side effects (logging, validation) |
| `let` | `it` | lambda result | Null checks, transforming |
| `run` | `this` | lambda result | Computing with many members |
| `with(x)` | `this` | lambda result | Grouping calls on a non-null object |

**How it works:** they are small `inline` functions in the standard library, so they cost nothing at runtime. `inline fun <T> T.apply(block: T.() -> Unit): T { block(); return this }` takes a lambda with a receiver (hence `this`); `inline fun <T, R> T.let(block: (T) -> R): R = block(this)` passes the object as a parameter (hence `it`).

**Common mistake:** Deeply nesting `?.let` (use names or a plain `if`), or forgetting that `let` returns the lambda's result while `also` returns the object.

**Follow-ups:**

- *What are `takeIf` and `takeUnless`?* They return the object or `null` depending on a condition: `input.takeIf { it.isNotBlank() }?.let(::search)`.

### 1.5 Extension functions

**In one line:** an extension function adds a function to an existing type without changing or inheriting from it.

**Say this in the interview:** "Extensions let me write `context.toast("Saved")` instead of a static utility call. They're resolved statically: the compiler turns them into a static function that takes the receiver as its first parameter. So they can't access private members, and they dispatch on the declared type, not the runtime type. I use them for small, focused helpers, and keep business logic in real classes."

**Example:**

```kotlin
fun Context.toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
val Int.dp: Int get() = (this * Resources.getSystem().displayMetrics.density).toInt()
fun ArticleEntity.toDomain() = Article(id, title, publishedAt)   // mappers between layers
```

**How it works:** `fun Context.toast(...)` compiles to a static method `toast(Context, String)`. If a class has a member with the same signature, the member wins.

**Common mistake:** Expecting an extension to be chosen by the runtime type. It is resolved from the declared type.

**Follow-ups:**

- *Extension vs utility class?* Same bytecode; extensions read better and are discoverable through autocomplete.
- *Can you override an extension?* No; they're static. `open` behaviour needs a member function.

### 1.6 Higher-order functions and lambdas

**In one line:** a higher-order function takes a function as a parameter or returns one; a lambda is a function written inline as a value.

**Say this in the interview:** "Kotlin treats functions as values with real types, like `(String) -> Int`. That lets me pass behaviour around, which replaces Java's single-method callback interfaces. I use it every day: Compose event callbacks like `onClick: (String) -> Unit`, Flow operators like `map` and `filter`, and DSLs like `buildString` or `LazyColumn`, which use lambdas with receivers. Lambdas also capture variables from where they're created, which is useful but is also a common source of Activity leaks."

**Example:**

```kotlin
// A higher-order function: takes a predicate
fun <T> List<T>.countWhere(predicate: (T) -> Boolean): Int = count(predicate)
val adults = people.countWhere { it.age >= 18 }   // trailing lambda, 'it' = the single parameter

// Function references instead of lambdas
val lengths = words.map(String::length)            // (String) -> Int
Button(onClick = viewModel::onRefresh) { Text("Refresh") }

// A function that returns a function, with a closure
fun debounced(intervalMs: Long = 500, action: () -> Unit): () -> Unit {
    var last = 0L                                  // captured and kept between calls
    return { val now = SystemClock.elapsedRealtime(); if (now - last >= intervalMs) { last = now; action() } }
}

// A lambda with a receiver: 'this' is the builder, which is how DSLs work
fun request(block: RequestBuilder.() -> Unit): Request = RequestBuilder().apply(block).build()
val req = request { url = "https://api.example.com"; header("Accept", "application/json") }
```

**How it works:**

- Function types: `() -> Unit`, `(Int, Int) -> Int`, nullable `((Int) -> Unit)?` (call with `?.invoke()`), with receiver `String.() -> Unit`, suspending `suspend () -> T`.
- Ways to create a function value: a lambda, an anonymous function `fun(x: Int) = x * 2`, a reference (`::isOdd`, `String::length`, `::User`), or a class implementing the function type.
- The last expression in a lambda is its result; use `return@label` to return early from a lambda.
- A capturing lambda is an object; if it captures a local `var`, Kotlin wraps the variable in a `Ref` object.
- Java SAM interfaces (`Runnable`, `View.OnClickListener`) accept lambdas; declare your own as `fun interface` to get the same.

**Common mistake:** Giving a long-lived object a lambda that captures an Activity and never removing it.

**Follow-ups:**

- *Higher-order function vs Java callback interface?* No interface per callback, shorter syntax, and `inline` removes the allocation.
- *How can a lambda leak an Activity?* It captures the Activity (or `this`), and a longer-lived object such as a singleton listener or a delayed Handler callback keeps the lambda alive.
- *`fun interface` vs function type?* A function type for simple callbacks; a `fun interface` when you want a named type for a public or Java-facing API.

### 1.7 inline, noinline, crossinline and reified

**In one line:** `inline` copies a function and its lambdas into each call site, `noinline` keeps a lambda as an object, `crossinline` forbids non-local returns, and `reified` preserves generic types at runtime.

**Say this in the interview:** "Every regular lambda allocates an object. Marking a small higher-order function `inline` pastes its body and lambdas at the call site, removing allocation and enabling non-local returns and `reified` types. I add `noinline` if one lambda must be stored as an object, and `crossinline` if a lambda is executed inside another context like a `Runnable`."

**`inline`:** Copies the function body and lambda arguments directly into the caller's bytecode, avoiding `Function` object allocation and allowing non-local `return` from the enclosing function. Avoid inlining large functions without lambda parameters, as it bloats bytecode.

```kotlin
inline fun measureMs(block: () -> Unit): Long {
    val start = System.nanoTime()
    block()
    return (System.nanoTime() - start) / 1_000_000
}
```

**`noinline`:** Opts a specific lambda parameter out of inlining so you can store it in a variable, pass it to a non-inline function, or return it.

```kotlin
inline fun runBoth(inlined: () -> Unit, noinline stored: () -> Unit): () -> Unit {
    inlined()
    return stored                                // allowed only because stored is noinline
}
```

**`crossinline`:** Marks an inlined lambda that is called from a different execution context (such as a `Runnable`, callback, or nested object). It forbids non-local `return` inside that lambda while still avoiding allocation.

```kotlin
inline fun postOnMain(crossinline action: () -> Unit) {
    Handler(Looper.getMainLooper()).post { action() }   // non-local return disallowed here
}
```

**`reified`:** Only usable on `inline` functions; replaces JVM type erasure by substituting the real type argument at each call site, letting you check `is T` or use `T::class.java`.

```kotlin
inline fun <reified T : Activity> Context.start() = startActivity(Intent(this, T::class.java))
context.start<SettingsActivity>()
```

**How it works:**

- On the JVM, generics are erased: `List<String>` is just `List` at runtime, so `x is T` is normally impossible. With `reified`, the real type is inserted at each call site.
- `noinline` keeps one lambda as an object, for example because you store it.
- `crossinline` is for a lambda called from another context (inside a `Runnable` or another lambda); it forbids non-local `return`.

**Common mistake:** Marking functions `inline` everywhere for speed. The benefit is mainly for small functions that take lambdas.

**Follow-ups:**

- *When is `inline` harmful?* Large function bodies (bigger APK), public inline functions in libraries (their body becomes part of your API), or lambdas that are stored.
- *What does `return@forEach` do?* Returns from the lambda only, like `continue`.

### 1.8 Generics and variance

**In one line:** variance says whether a `Box<Cat>` can be used where a `Box<Animal>` is expected: `out` means yes (the box only produces), `in` means the reverse (the box only consumes).

**Say this in the interview:** "Generic types are invariant by default: a `MutableList<Cat>` is not a `MutableList<Animal>`, because you could add a Dog to it. If a type only returns `T`, I mark it `out T` and it becomes covariant, like Kotlin's read-only `List<out E>`. If it only accepts `T`, I mark it `in T`, like `Comparator<in T>`. It's the same idea as Java's 'producer extends, consumer super'."

**Example:**

```kotlin
interface Source<out T> { fun next(): T }          // producer: Source<Cat> is a Source<Animal>
interface Sink<in T> { fun accept(item: T) }       // consumer: Sink<Animal> is a Sink<Cat>

fun <T : Comparable<T>> List<T>.largest(): T? = maxOrNull()                       // upper bound
fun <T> save(item: T) where T : Parcelable, T : Validatable { }                    // several bounds
```

**How it works:** `out`/`in` at the declaration is declaration-site variance; `List<out Animal>` at a use site is use-site variance (like Java wildcards). `List<*>` is a star projection: an unknown type you can read as `Any?`.

**Common mistake:** Expecting `MutableList<Cat>` to work where `MutableList<Animal>` is needed because `Cat` is an `Animal`.

**Follow-ups:**

- *Why is `List` covariant but `MutableList` invariant?* `List` only returns elements; `MutableList` also accepts them, which would break type safety.

### 1.9 Delegation: lazy, observable, viewModels and class delegation

**In one line:** delegation forwards property access (`by lazy`, `observable`, `viewModels`) or interface implementation (`class A : B by b`) to another object.

**Say this in the interview:** "Property delegates reuse getter/setter logic across properties. `by lazy` computes a `val` once on first read; `Delegates.observable` reacts to `var` changes; `by viewModels()` fetches a ViewModel from the right store. Class delegation implements an interface by forwarding calls to a collaborator—composition without boilerplate."

**`by lazy`:** Computes a `val` once on first access and caches it. Uses `LazyThreadSafetyMode.SYNCHRONIZED` (double-checked locking) by default; use `NONE` for main-thread-only properties.

```kotlin
private val formatter by lazy(LazyThreadSafetyMode.NONE) { DateTimeFormatter.ofPattern("d MMM") }
```

**`Delegates.observable` (and `vetoable`):** `observable` invokes a callback *after* a `var` changes; `vetoable` runs *before* the assignment and can reject the new value by returning `false`.

```kotlin
var query by Delegates.observable("") { _, old, new -> log("$old -> $new") }
var age by Delegates.vetoable(0) { _, _, new -> new >= 0 }   // rejects negative values
```

**`by viewModels()` (Android delegate):** Lazily looks up or creates a `ViewModel` scoped to the Activity/Fragment `ViewModelStoreOwner` without calling `ViewModelProvider` manually.

```kotlin
private val viewModel: MainViewModel by viewModels()
```

**Class delegation (`by`):** Implements an interface by forwarding all its methods to a wrapped instance, letting you override only the methods you want to customize.

```kotlin
class LoggingList<T>(private val inner: MutableList<T>) : MutableList<T> by inner {
    override fun add(element: T): Boolean { log("add $element"); return inner.add(element) }
}
```

**How it works:** the compiler generates a hidden field holding the delegate and calls its `getValue`/`setValue`. `lazy` uses double-checked locking by default (`LazyThreadSafetyMode.SYNCHRONIZED`); `NONE` is faster for main-thread-only use.

**Common mistake:** Using `by lazy` for a value that must change when its inputs change. It is computed once and kept.

**Follow-ups:**

- *`lateinit` vs `lazy`?* `lateinit var` is for non-null values set later from outside (DI, `onCreate`), not for primitives; `lazy` is for a `val` computed once on first access.

### 1.10 Companion objects and object declarations

**In one line:** a `companion object` belongs to a class, an `object` declaration defines a thread-safe singleton, and an `object` expression creates an anonymous instance.

**Say this in the interview:** "Kotlin has no `static` keyword. A `companion object` is a single object tied to a class—unlike Java statics, it's a real object that can implement interfaces. An `object` declaration creates a lazy, thread-safe singleton (`INSTANCE`). And an `object : Interface` expression creates an anonymous class instance on the spot."

**Companion object:** One per class, initialized when the class loads. Compiles to a nested `Foo.Companion` class; add `@JvmStatic`, `@JvmField`, or `const val` for true Java statics.

```kotlin
class ArticleFragment : Fragment() {
    companion object {
        const val TAG = "ArticleFragment"
        fun newInstance(id: String) = ArticleFragment().apply { arguments = bundleOf("id" to id) }
    }
}
```

**`object` declaration (singleton):** Declares a class and its single instance in one step, initialized lazily and thread-safely on first access. Cannot have constructors.

```kotlin
object Analytics { fun track(event: String) { } }
```

**`data object` (Kotlin 1.9+):** A singleton that generates a clean `toString()` (returning the simple class name instead of `ClassName@hash`), `equals()`, and `hashCode()`—ideal for empty states in `sealed` hierarchies.

```kotlin
sealed interface UiState {
    data object Loading : UiState   // println(Loading) -> "Loading"
}
```

**`object` expression (anonymous object):** Creates an ad-hoc implementation of one or more interfaces or classes.

```kotlin
val watcher = object : TextWatcher { /* ... */ }
```

**How it works:**

| | `object` declaration | `companion object` |
| --- | --- | --- |
| Belongs to | Package or enclosing scope | Its enclosing class (`1` per class) |
| Accessed as | `Analytics.track(...)` | `MyClass.create()` (or `MyClass.Companion.create()` in Java) |
| Initialized | Lazily on first access | When the enclosing class is loaded |
| Private access | Cannot see another class's `private` members | Can access `private` constructors and members of its class |

| Kotlin | Compiled to |
| --- | --- |
| `companion object { fun create() }` | Nested class `Foo.Companion` and a static field; Java calls `Foo.Companion.create()` |
| `const val TAG` | A `public static final` field on `Foo` |
| `@JvmStatic fun create()` | A real static method on `Foo` |
| `object Analytics` | A class with a static `INSTANCE`, initialised lazily and thread-safely |

**Common mistake:** Using a companion object as a home for unrelated helpers and mutable global state.

**Follow-ups:**

- *Is a companion object the same as static?* No: it's an object instance; add `@JvmStatic` or `const` for true statics.
- *When not to use one?* For general helpers, top-level functions are simpler. Never store a `Context` or Activity in a companion or `object`: it lives as long as the process and leaks the screen.

### 1.11 Collections vs sequences

**In one line:** collection operations are eager and create a new list at every step; sequences are lazy and process one element at a time through the whole chain.

**Say this in the interview:** "`list.map { }.filter { }` builds a full intermediate list after each step. A `Sequence` passes each element through all the steps before moving to the next, and stops early with `first` or `take`. I use plain collections for small lists, which is most of the time, and sequences for long chains over large data or when I only need the first few results."

**Example:**

```kotlin
val first = (1..1_000_000).asSequence()
    .map { it * 2 }
    .filter { it % 3 == 0 }
    .first()           // processes only 3 elements, then stops; no intermediate lists
```

**Common mistake:** Switching to a sequence for every chain. For small lists, the overhead can outweigh the saving.

**Follow-ups:**

- *Are sequences always faster?* No; for small collections the extra overhead can make them slower.

### 1.12 Operators, infix functions and type aliases

**In one line:** `operator` overloads symbols like `+` and `[]`, `infix` enables dot-free calls for single-parameter functions, and `typealias` gives an existing type a shorter name.

**Say this in the interview:** "Operator overloading maps fixed function names to symbols for domain types like `Money`. Infix functions make DSLs and pairs read like natural language (`1 to "one"`). Type aliases simplify long generic or function signatures without creating a wrapper class."

**Operator overloading (`operator`):** Gives custom meaning to operators (`+` -> `plus`, `[]` -> `get`/`set`, `in` -> `contains`, `()` -> `invoke`).

```kotlin
data class Money(val cents: Long) {
    operator fun plus(o: Money) = Money(cents + o.cents)
    operator fun compareTo(o: Money) = cents.compareTo(o.cents)
}
val total = price + shipping
```

**Infix functions (`infix`):** Member or extension functions with a single parameter (no `vararg` or defaults) that can be called without a dot or parentheses.

```kotlin
infix fun Int.percentOf(total: Int) = total * this / 100
val discount = 15 percentOf 200                      // 30
```

**Type aliases (`typealias`):** An alias for an existing type (zero runtime overhead, interchangeable with the underlying type; use `@JvmInline value class` if you want type safety).

```kotlin
typealias OnArticleClick = (articleId: String) -> Unit
```

**Common mistake:** Overloading an operator with a meaning readers would not guess from the symbol.

**Follow-ups:**

- *Other operator names?* `get`/`set` (`a[i]`), `contains` (`in`), `invoke` (`a()`), `componentN` (destructuring), `rangeTo` (`..`), `iterator` (`for`).

### 1.13 Java interoperability

**In one line:** Kotlin and Java call each other directly; a few annotations and API habits make Kotlin feel natural from Java and keep Java safe from Kotlin.

**Say this in the interview:** "Most big codebases mix both languages. From Java, a Kotlin companion function looks like `Foo.Companion.create()` and default arguments don't exist, so for Java-facing APIs I add `@JvmStatic`, `@JvmField`, `@JvmOverloads`, `@JvmName`, and `@Throws`, and prefer `fun interface` over `(T) -> Unit` so Java callers don't have to return `Unit.INSTANCE`. In the other direction, Java types without nullability annotations become platform types (`String!`), so I annotate Java APIs I own and enable Android's `Interoperability` lint checks."

**Example:**

```kotlin
@file:JvmName("Analytics")                       // Java sees Analytics.xyz(), not AnalyticsKt.xyz()

fun interface EventListener { fun onEvent(name: String) } // SAM: Java avoids returning Unit.INSTANCE

class Tracker @JvmOverloads constructor(          // Java gets Tracker(String), Tracker(String, int), ...
    val endpoint: String, val batchSize: Int = 20
) {
    companion object {
        @JvmField val DEFAULT_TIMEOUT_MS = 5_000L // exposed as static field (not Companion.get...)
        @JvmStatic fun createDefault() = Tracker("https://events.example.com")
    }
    @Throws(IOException::class) fun flush() { }   // Java can now catch checked IOException
}
```

**How it works:**

- **Collections:** Kotlin's read-only `List` is just `java.util.List` in Java—return defensive copies or `Collections.unmodifiableList(...)` from public APIs if Java callers might mutate them.
- **Interop lint checks:** Android Studio / Gradle `android { lint { enable += "Interoperability" } }` flags Java APIs missing nullability annotations, non-standard property prefixes, Kotlin hard keywords (like `when`), and SAM parameters not placed last.

**Common mistake:** Trusting values from unannotated Java as non-null, or exposing `(T) -> Unit` lambdas to Java callers.

**Follow-ups:**

- *Why do custom Views often use `@JvmOverloads`?* The framework calls Java-style constructors (`Context`, `AttributeSet`), and default arguments alone don't create them. You can also write the constructors yourself, which is safer when the parent class applies a default style.
- *What happens if Java passes null to a non-null Kotlin parameter?* An immediate `NullPointerException` naming the parameter.

### 1.14 What's new in Kotlin 2.2 and 2.3

**In one line:** recent versions added guard conditions in `when`, non-local `break`/`continue`, multi-dollar strings and nested type aliases as stable features.

**Say this in the interview:** "Kotlin 2.x moved to the K2 compiler, which is faster and smarter about smart casts, and the Compose compiler now ships with Kotlin. Recent stable features I use: guard conditions, so a `when` branch can have an `if`; `break` and `continue` inside inline lambdas like `forEach`; and since 2.3, nested type aliases. I also watch experimental ones like explicit backing fields, which would remove the `_state`/`state` pattern in ViewModels."

**Example:**

```kotlin
fun label(s: UploadState) = when (s) {
    is UploadState.Running if s.progress > 0.9f -> "Almost done"      // guard condition (2.2)
    is UploadState.Running -> "Uploading"
    is UploadState.Failed -> "Failed"
    UploadState.Done -> "Done"
}

for (batch in batches) batch.items.forEach { if (it.isCorrupt) continue; upload(it) }   // non-local continue (2.2)
```

**Common mistake:** Presenting an experimental feature as stable. Check its status for the Kotlin version you name.

**Follow-ups:**

- *Which features are still experimental?* Context parameters (preview in 2.2), explicit backing fields and the unused-return-value checker (experimental in 2.3).

### 1.15 Interfaces, abstract classes and initialization order

**In one line:** prefer interfaces for shared capabilities without state, abstract classes when subclasses share state or constructors, and never call `open` members inside `init`.

**Say this in the interview:** "A class can implement many interfaces but extend only one class. Kotlin interfaces can hold default method bodies and abstract properties, though no backing fields. I use an abstract class when subclasses share mutable state or constructor logic. During construction, `init` blocks and property initializers run top-to-bottom in declaration order before any secondary constructor body—and a superclass `init` runs before subclass properties are initialized."

**Interface:** Defines a contract of methods and properties; supports default implementations and custom `get()` accessors, but cannot hold constructors or backing fields. A class can implement multiple interfaces.

```kotlin
interface Clickable {
    val label: String
    fun onClick() = println("Clicked $label")
}
```

**Abstract class:** Cannot be instantiated directly, can hold constructors, `protected` state, and backing fields, and a subclass can extend only one.

```kotlin
abstract class BaseAdapter(protected val tag: String) {
    abstract fun bind(position: Int)
}
```

**Initialization order (`init` & constructors):** Property initializers and `init` blocks execute in top-to-bottom source order before any secondary constructor body. Superclass initialization completes *before* subclass properties are set, so calling an `open` method in a base `init` can read `null` on a non-null subclass property.

```kotlin
open class Base { init { println(label()) }; open fun label() = "base" }
class Child : Base() { private val name = "child"; override fun label() = name }   // prints null!
```

**Common mistake:** Calling an `open` method from a superclass `init` block, which runs before subclass properties are set.

**Follow-ups:**

- *Can a Kotlin interface have properties?* Yes—abstract properties or properties with custom `get()` accessors, as long as they have no backing field.

### 1.16 Preconditions: require vs check

**In one line:** `require` validates caller arguments (`IllegalArgumentException`), while `check` validates the object's or program's current state (`IllegalStateException`).

**Say this in the interview:** "I use Kotlin's standard-library preconditions to fail fast with clear messages instead of letting bad inputs or invalid state corrupt data downstream. `require` and `requireNotNull` guard arguments passed in by the caller—a failure means 'you called me wrong'. `check` and `checkNotNull` guard the object's own state—a failure means 'I'm not ready for this call right now'. Both also use Kotlin contracts, so a successful `requireNotNull` or `checkNotNull` smart-casts the variable to non-null."

**Example:**

| | `require` / `requireNotNull` | `check` / `checkNotNull` |
| --- | --- | --- |
| Guards | Arguments passed in by the caller | State of the object or program |
| Throws | `IllegalArgumentException` | `IllegalStateException` |
| A failure means | "You called me wrong" | "I'm not ready for this call right now" |

```kotlin
class Player {
    private var prepared = false

    fun seekTo(positionMs: Long) {
        require(positionMs >= 0) { "positionMs must be >= 0, was $positionMs" } // bad input
        check(prepared) { "Call prepare() before seekTo()" }                     // bad state
        // ...
    }
}
```

**Common mistake:** Using `require` for internal state checks or `check` for parameter validation, which throws the wrong exception type for callers and crash triage.

**Follow-ups:**

- *Why pass a lazy lambda `{ "..." }` to `require` or `check`?* The message string is only built when the condition fails, avoiding string allocation on every valid call.

### 1.17 Nested, inner, open and annotation classes

**In one line:** Kotlin classes are `final` and nested classes are static by default; `open` enables inheritance, `inner` holds a reference to the outer instance, and `annotation class` attaches metadata.

**Say this in the interview:** "Kotlin makes classes `final` and nested classes static by default so you don't accidentally allow fragile inheritance or leak an outer `Activity`. I only add `open` when a class is designed for subclassing, only add `inner` when a nested class truly needs its outer instance, and use `annotation class` for Hilt qualifiers or compile-time metadata."

**Regular (`final`) vs. `open class`:** Classes and methods in Kotlin are `final` by default. Mark a class `open` to allow subclassing, and mark individual methods/properties `open` to allow `override`.

```kotlin
open class BaseScreen { open fun onReady() {} }
class HomeScreen : BaseScreen() { override fun onReady() {} }
```

**Nested `class` (static by default):** Declared inside another class without `inner`. Holds no reference to the outer instance, so it cannot leak an `Activity` or `Fragment` (e.g. `RecyclerView.ViewHolder`).

```kotlin
class Outer {
    private val secret = 1
    class Nested { fun greet() = "hi" }          // cannot access secret; no Outer reference
}
```

**`inner class`:** Holds an implicit reference to its enclosing instance (`this@Outer`), letting it access outer properties and methods—but if an `inner class` listener outlives an `Activity`, it leaks the `Activity`.

```kotlin
class Outer {
    private val secret = 1
    inner class Inner { fun read() = secret }    // holds implicit reference to Outer
}
```

**`annotation class`:** Defines metadata tags (`@Target`, `@Retention`) read by compilers, Hilt, Room, or reflection.

```kotlin
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class IoDispatcher
```

**Common mistake:** Marking a nested listener or adapter `inner` when it doesn't need the outer instance, creating a hidden memory leak.

**Follow-ups:**

- *How is Kotlin's nested class different from Java's?* In Java, a nested class without `static` holds an outer reference by default; in Kotlin, it's the reverse—nested classes are static unless marked `inner`.

### Interview questions

1. **Why should you avoid `!!`, and what do you use instead?** `!!` throws a NullPointerException at runtime, which throws away Kotlin's compile-time safety. Use a safe call with a default, an early return, or `requireNotNull` with a clear message. {Easy}
2. **What does `inline` do, and when shouldn't you use it?** It copies the function and its lambdas into each call site, so no lambda object is created, non-local `return` works and `reified` is possible. Avoid it for large functions or lambdas you store, because it grows the bytecode. {Medium}
3. **Can a data class be inherited?** No, a data class can't be `open`. It can implement interfaces or extend a sealed class, which is how sealed UI states are built. {Easy}
4. **How does `by lazy` work?** It stores an initializer and computes the value on first access, using double-checked locking by default, so it's thread-safe. Use `LazyThreadSafetyMode.NONE` when only the main thread reads it. {Medium}
5. **If you pass a Kotlin `List` to Java, can Java change it?** Yes. Read-only is a compile-time view in Kotlin; Java sees `java.util.List` and can call `add` if the real object is mutable. {Medium}
6. **What is a higher-order function, and why is it better than a Java callback interface?** A function that takes or returns a function. Kotlin has real function types, so you don't need an interface per callback, lambdas are short, and `inline` removes the allocation. {Easy}
7. **What is a lambda with a receiver, and where have you used one?** Its type is `A.() -> R`, so inside the lambda `this` is the receiver. It powers `apply`, `buildString`, Compose scopes like `LazyListScope`, and the Gradle Kotlin DSL. {Medium}
8. **How can a lambda leak an Activity?** It captures the Activity or `this`. If a longer-lived object keeps the lambda, such as a singleton listener or a delayed Handler callback, the Activity can't be garbage collected. {Medium}
9. **What does `@JvmOverloads` do?** Java can't use Kotlin default arguments, so it only sees the full signature. `@JvmOverloads` generates the shorter overloads. It's a common shortcut for custom View constructors, but check that each one still calls the right superclass constructor, or the view can lose its default style. {Easy}
10. **What are guard conditions in `when`?** Since Kotlin 2.2, a branch of a `when` with a subject can add an `if`, like `is Failed if state.canRetry ->`, instead of nesting another `if`. {Easy}
11. **What is a companion object, and how is it different from Java `static`?** One object per class, created when the class loads, whose members you call through the class name. Unlike statics it is a real object that can implement interfaces; use `const`, `@JvmField` or `@JvmStatic` for true statics. {Easy}
12. **How do you choose between `let`, `run`, `with`, `apply` and `also`?** Ask two questions: do I want the object back (`apply` to configure, `also` for side effects) or a result (`let` for nullable values, `run` or `with` to compute)? And does `this` or `it` read better? {Easy}
13. **What is the difference between a sealed class and an enum?** Enum values are fixed single instances with the same properties. Sealed subtypes can each carry different data and have many instances, and `when` is still checked for every case. {Easy}
14. **Explain `out` and `in` in Kotlin generics.** `out T` means the type only produces `T`, so `Source<Cat>` can be used as `Source<Animal>`. `in T` means it only consumes `T`, so `Sink<Animal>` can be used as `Sink<Cat>`. Without either, the type is invariant. {Hard}
15. **When would you use a sequence instead of a list?** For long chains of operations over large data, or when you only need the first few results, because sequences are lazy and avoid intermediate lists. For small lists, plain collections are simpler and often faster. {Medium}
16. **When do you choose an interface over an abstract class in Kotlin?** Use an interface for capabilities a class can combine with others (multiple inheritance, no backing fields); use an abstract class when subclasses share state, backing fields or constructor setup. {Easy}
17. **When do you use `require` vs `check` in Kotlin?** Use `require` (or `requireNotNull`) to validate caller arguments, throwing `IllegalArgumentException` when the caller passed bad input; use `check` (or `checkNotNull`) to validate the object's or program's state, throwing `IllegalStateException` when it isn't ready for the call. {Easy}
18. **How can you still get a `NullPointerException` in pure Kotlin without using `!!`?** Calling an `open` method from a superclass `init` block before subclass properties are set, reading Java platform types (`String!`), uninitialized `lateinit` access (`UninitializedPropertyAccessException`), or reflection-based deserializers like Gson writing `null` into non-null `val` fields. {Hard}
19. **Why does `list as? List<String>` generate an 'Unchecked cast' warning?** Because of JVM type erasure, `List<String>` is just `List` at runtime, so `as?` only checks the outer `List` and not its elements. Use `(list as? List<*>)?.filterIsInstance<String>()` to check elements safely. {Medium}
20. **Why does smart-casting fail on a `var` property, and how do you solve it?** A `var` (or `val` with a custom getter) can change between the null check and its usage, so the compiler can't guarantee it stays non-null. Capture a local snapshot (`val current = x; if (current != null) ...`) or use `x?.let { ... }`. {Medium}
21. **What is the difference between `<T>` and `<T : Any>` in Kotlin generics?** An unconstrained `<T>` has an implicit upper bound of `Any?`, allowing nullable types like `Box<String?>`, while `<T : Any>` restricts `T` to non-null types (and `T & Any` represents definitely non-nullable types for Java interop). {Medium}
22. **How does `?.let { ... } ?: run { ... }` behave as an if-else replacement, and what is the hidden trap?** If the `?.let` block evaluates to `null` (for example calling a function returning `Unit?` or nullable), the `?: run` branch executes even though the receiver was non-null. Use a standard `if (x != null) ... else ...` instead. {Medium}
23. **What is the difference between a nested class and an `inner class` in Kotlin?** A nested class has no reference to the outer class (static by default, safer against leaks); an `inner class` holds an implicit reference to the outer instance and can access its members. {Easy}
24. **What does `data object` add over a plain `object`?** Since Kotlin 1.9, `data object` generates a clean `toString()` returning the class name (instead of `ClassName@hash`) plus `equals()` and `hashCode()`, making it ideal for empty states in `sealed` hierarchies. {Easy}
