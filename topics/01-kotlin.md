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

### Interview questions

1. **Why is `!!` a code smell?** It converts a compile-time guarantee into a runtime crash. Prefer early return, `requireNotNull` with a message, or modelling the state so null cannot happen. {Easy}
2. **What does `inline` buy you, and when is it harmful?** It removes lambda allocation and enables `reified`. It bloats bytecode if the function body is large; only inline small functions that take lambdas. {Medium}
3. **`data class` inheritance?** A data class cannot be `open`. It can implement interfaces or extend a sealed class. {Easy}
4. **How does `lazy` work under the hood?** It holds an initializer and a value field; the default mode uses double-checked locking. Use `LazyThreadSafetyMode.NONE` on the main thread for slight speed-up. {Medium}
5. **Difference between `List` and `MutableList` when passing to Java?** Java sees both as `java.util.List` and can mutate it; read-only is a compile-time view only. {Medium}
