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

### 1.2 val, var, immutability and data classes

**In one line:** `val` is a read-only reference, and a `data class` is a class for holding data that gets `equals`, `hashCode`, `toString` and `copy` generated for it.

**Say this in the interview:** "I default to `val` and immutable data, because immutable objects are thread-safe and easy to reason about. Note that `val` only means the reference can't change; a `val` list can still be a mutable list. For UI state I use data classes and update them with `copy`, and I expose read-only types like `List` while keeping `MutableList` private."

**Example:**

```kotlin
data class CartUiState(val items: List<CartItem> = emptyList(), val isLoading: Boolean = false)

private val _state = MutableStateFlow(CartUiState())
fun onLoading() = _state.update { it.copy(isLoading = true) }   // new object, old one untouched
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

**In one line:** a sealed class or interface is a closed set of subtypes known at compile time, so a `when` over it must handle every case.

**Say this in the interview:** "I use sealed types to model things that can be in exactly one of a few states, like UI state or a network result. The compiler checks that every `when` covers every case, so adding a new state shows me every place I need to update. Compared to an enum, each sealed subtype can carry different data. For IDs I use value classes, which give type safety without allocating an object in most cases."

**Example:**

```kotlin
sealed interface ProfileState {
    data object Loading : ProfileState
    data class Content(val user: User) : ProfileState
    data class Error(val message: String, val canRetry: Boolean) : ProfileState
}

when (state) {                                  // no 'else' needed: the compiler knows all cases
    ProfileState.Loading -> showSpinner()
    is ProfileState.Content -> show(state.user) // smart cast to Content
    is ProfileState.Error -> showError(state.message)
}

@JvmInline value class UserId(val raw: String)
@JvmInline value class OrderId(val raw: String)
fun cancel(order: OrderId, by: UserId) { }
cancel(userId, orderId)                         // compile error: arguments swapped
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

**In one line:** `inline` copies a function and its lambda arguments into each call site, removing lambda allocation and allowing `reified` type parameters.

**Say this in the interview:** "Normally every lambda you pass is an object. Marking a higher-order function `inline` makes the compiler paste its body and the lambda's body where it's called, so nothing is allocated. That's why `map`, `filter` and `let` are inline. It also allows a `return` inside the lambda to return from the outer function, and it enables `reified`, which keeps the generic type at runtime despite type erasure. I only inline small functions that take lambdas, because inlining large ones bloats the bytecode."

**Example:**

```kotlin
inline fun <reified T : Activity> Context.start() = startActivity(Intent(this, T::class.java))
context.start<SettingsActivity>()

fun findAdmin(users: List<User>): User? {
    users.forEach { if (it.isAdmin) return it }   // non-local return: allowed because forEach is inline
    return null
}
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

**In one line:** delegation hands the work of a property or an interface to another object, with the `by` keyword.

**Say this in the interview:** "Property delegates move get-and-set logic into a reusable object. `by lazy` computes a value on first access and is thread-safe by default; `by viewModels()` is a delegate that fetches the ViewModel from the right store. Class delegation, `class A(b: B) : B by b`, implements an interface by forwarding to another object, which is composition instead of inheritance."

**Example:**

```kotlin
private val viewModel: MainViewModel by viewModels()
private val formatter by lazy { DateTimeFormatter.ofPattern("d MMM") }        // created on first use
var query by Delegates.observable("") { _, old, new -> log("$old -> $new") }

class LoggingList<T>(private val inner: MutableList<T>) : MutableList<T> by inner {
    override fun add(element: T): Boolean { log("add $element"); return inner.add(element) }
}
```

**How it works:** the compiler generates a hidden field holding the delegate and calls its `getValue`/`setValue`. `lazy` uses double-checked locking by default (`LazyThreadSafetyMode.SYNCHRONIZED`); `NONE` is faster for main-thread-only use.

**Common mistake:** Using `by lazy` for a value that must change when its inputs change. It is computed once and kept.

**Follow-ups:**

- *`lateinit` vs `lazy`?* `lateinit var` is for non-null values set later from outside (DI, `onCreate`), not for primitives; `lazy` is for a `val` computed once on first access.

### 1.10 Companion objects and object declarations

**In one line:** a companion object is a single object that belongs to a class, so its members are called through the class name, like `ArticleFragment.newInstance(id)`.

**Say this in the interview:** "Kotlin has no `static` keyword. A class can declare one `companion object`; there's exactly one per class, created when the class loads, and its members are called through the class name, so it plays the role of static members. Unlike statics, it's a real object: it can implement interfaces and have extension functions. On the JVM it becomes a nested class called `Companion` plus a static field, and `const val`, `@JvmField` and `@JvmStatic` turn members into true statics for Java. For a plain singleton I use an `object` declaration."

**Example:**

```kotlin
class ArticleFragment : Fragment() {
    companion object {
        const val TAG = "ArticleFragment"
        private const val ARG_ID = "id"
        fun newInstance(id: String) = ArticleFragment().apply { arguments = bundleOf(ARG_ID to id) }
    }
}

object Analytics { fun track(event: String) { } }                 // singleton, created on first access

val watcher = object : TextWatcher { /* ... */ }                  // object expression: a new anonymous object
```

**How it works:**

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

**In one line:** `operator` lets your types use symbols like `+` and `[]`; `infix` lets a one-parameter function be called without dots; `typealias` gives a type a shorter name.

**Say this in the interview:** "Operator overloading maps symbols to functions with fixed names, so `a + b` calls `a.plus(b)`. I use it for value types like `Money`. Infix functions read like keywords, like `1 to "one"`. Type aliases just rename a type, which is handy for long function types; they don't create a new type."

**Example:**

```kotlin
data class Money(val cents: Long) {
    operator fun plus(o: Money) = Money(cents + o.cents)
    operator fun compareTo(o: Money) = cents.compareTo(o.cents)
}
val total = price + shipping
if (total > limit) warn()

infix fun Int.percentOf(total: Int) = total * this / 100
val discount = 15 percentOf 200                      // 30

typealias OnArticleClick = (articleId: String) -> Unit
```

**Common mistake:** Overloading an operator with a meaning readers would not guess from the symbol.

**Follow-ups:**

- *Other operator names?* `get`/`set` (`a[i]`), `contains` (`in`), `invoke` (`a()`), `componentN` (destructuring), `rangeTo` (`..`), `iterator` (`for`).

### 1.13 Java interoperability

**In one line:** Kotlin and Java call each other directly; a few annotations make Kotlin APIs feel natural from Java.

**Say this in the interview:** "Most big codebases mix both languages. From Java, a Kotlin companion function looks like `Foo.Companion.create()` and default arguments don't exist, so for Java-facing APIs I add `@JvmStatic`, `@JvmOverloads`, `@JvmField` and `@Throws`. In the other direction, Java types without nullability annotations become platform types, so I annotate Java code I own or treat its values as nullable."

**Example:**

```kotlin
@file:JvmName("Analytics")                       // Java sees Analytics.xyz(), not AnalyticsKt.xyz()

class Tracker @JvmOverloads constructor(          // Java gets Tracker(String), Tracker(String, int), ...
    val endpoint: String, val batchSize: Int = 20
) {
    companion object { @JvmStatic fun createDefault() = Tracker("https://events.example.com") }
    @Throws(IOException::class) fun flush() { }   // Java can now catch IOException
}
```

**Common mistake:** Trusting values from unannotated Java as non-null.

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

**Say this in the interview:** "A class can implement many interfaces but extend only one class. Kotlin interfaces can hold default method bodies and abstract properties, though no backing fields. I use an abstract class when subclasses share mutable state or constructor logic. During construction, `init` blocks and property initializers run top-to-bottom in declaration order before any secondary constructor body—and a superclass `init` runs before subclass properties are initialized, so calling an `open` method there can read `null` even on a non-null property."

**Example:**

```kotlin
interface Clickable { fun onClick() }
abstract class BaseAdapter(protected val tag: String)   // holds shared state
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
