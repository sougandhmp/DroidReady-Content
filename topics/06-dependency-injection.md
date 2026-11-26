# Dependency injection

DI questions check whether you can wire a large app so it's testable, and whether you understand what Hilt and Dagger actually do.

### 6.1 What DI is and why it matters

**In one line:** dependency injection means a class receives the objects it needs, usually through its constructor, instead of creating them itself.

**Say this in the interview:** "If a ViewModel creates its own Retrofit client, I can't test it without a network and can't change the client without editing it. With DI, the ViewModel just asks for an `ArticleRepository` in its constructor, and something else decides which implementation to give it: the real one in the app, a fake in tests. That gives testability, reuse and clear lifetimes. A DI framework like Hilt only automates building and scoping that object graph."

**Example:**

```kotlin
// Without DI: hard-wired, untestable
class ArticlesViewModel : ViewModel() { private val repo = ArticleRepositoryImpl(RetrofitClient.api) }

// With DI: dependencies come in through the constructor
class ArticlesViewModel @Inject constructor(private val repo: ArticleRepository) : ViewModel()
```

**Common mistake:** Treating DI as a library feature. Passing dependencies into a constructor is already DI.

**Follow-ups:**

- *DI vs service locator?* With DI, dependencies are pushed in and visible in the constructor. A service locator is called from inside the class (`ServiceLocator.get<Repo>()`), which hides dependencies and makes tests harder.
- *Why prefer constructor injection over field injection?* Dependencies are explicit, fields can be `val`, and tests can build the class without a framework. Field injection is only for classes the system creates, like Activities.

### 6.2 Hilt basics

**In one line:** Hilt is Android's recommended DI library, built on Dagger, that generates the object graph at compile time and wires it into Android classes.

**Say this in the interview:** "I annotate the Application with `@HiltAndroidApp`, Activities and Fragments with `@AndroidEntryPoint`, and ViewModels with `@HiltViewModel`. Classes I own get `@Inject constructor`. For interfaces I use `@Binds` in an abstract module, and for third-party classes like Retrofit I use `@Provides`. Because the graph is checked at compile time, a missing dependency fails the build instead of crashing a user's app."

**Example:**

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides @Singleton
    fun okHttp(auth: AuthInterceptor): OkHttpClient = OkHttpClient.Builder().addInterceptor(auth).build()

    @Provides @Singleton
    fun api(client: OkHttpClient): ArticleApi = Retrofit.Builder()
        .baseUrl("https://api.example.com/").client(client)
        .addConverterFactory(Json.asConverterFactory("application/json".toMediaType()))
        .build().create(ArticleApi::class.java)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {
    @Binds abstract fun articleRepository(impl: OfflineFirstArticleRepository): ArticleRepository
}
```

**How it works:** for every `@Inject` constructor, Dagger generates a factory class. Components connect the factories into a graph. A `@Singleton` binding is wrapped in `DoubleCheck`, which creates it once with double-checked locking. `@AndroidEntryPoint class MainActivity` really extends a generated `Hilt_MainActivity` that injects fields in `onCreate`.

**Common mistake:** Creating a class with its constructor yourself and expecting Hilt to fill its `@Inject` fields.

**Follow-ups:**

- *`@Binds` vs `@Provides`?* `@Binds` maps an interface to an implementation that has an `@Inject` constructor; it's abstract and cheaper. `@Provides` is a function where you write the construction code yourself.

### 6.3 Components and scopes

**In one line:** each Hilt component lives as long as an Android class, and a scope annotation makes a binding one shared instance within that component.

**Say this in the interview:** "Without a scope, Hilt creates a new instance every time something asks for it. `@Singleton` gives one per app, `@ViewModelScoped` one per ViewModel, `@ActivityRetainedScoped` one that survives rotation, and so on. I only scope objects that hold shared state or are expensive to create, because a scoped object stays in memory for the whole component's life."

**Example:**

| Component | Scope | Lives as long as |
| --- | --- | --- |
| `SingletonComponent` | `@Singleton` | The application process |
| `ActivityRetainedComponent` | `@ActivityRetainedScoped` | An activity, across rotation |
| `ViewModelComponent` | `@ViewModelScoped` | One ViewModel |
| `ActivityComponent` | `@ActivityScoped` | One activity instance |
| `FragmentComponent` | `@FragmentScoped` | One fragment |
| `ServiceComponent` | `@ServiceScoped` | One service |

**Common mistake:** Marking everything `@Singleton`, which keeps objects alive longer than they are needed.

**Follow-ups:**

- *`@Singleton` vs `@ActivityRetainedScoped`?* A singleton lives as long as the app process. An activity-retained object lives through configuration changes and goes when the activity finishes.

### 6.4 Qualifiers, assisted injection and multibindings

**In one line:** qualifiers tell apart two bindings of the same type, assisted injection mixes graph dependencies with runtime values, and multibindings collect many implementations into a set or map.

**Say this in the interview:** "When I need two `CoroutineDispatcher`s, I define qualifiers like `@IoDispatcher` and `@DefaultDispatcher`. When a class needs something only known at runtime, like an article ID, I use `@AssistedInject` with an `@AssistedFactory`. And when several modules each contribute an implementation, like app initializers or payment methods, I use `@IntoSet` or `@IntoMap` so no central list has to know about them all."

**Example:**

```kotlin
@Qualifier @Retention(AnnotationRetention.BINARY) annotation class IoDispatcher

@Provides @IoDispatcher fun io(): CoroutineDispatcher = Dispatchers.IO

class ArticleExporter @AssistedInject constructor(
    private val repo: ArticleRepository,           // from the graph
    @Assisted private val articleId: String        // from the caller
) {
    @AssistedFactory interface Factory { fun create(articleId: String): ArticleExporter }
}

@Binds @IntoSet abstract fun analyticsInit(i: AnalyticsInitializer): AppInitializer   // collected into Set<AppInitializer>
```

**Common mistake:** Providing two bindings of the same type without a qualifier, then being surprised by a duplicate binding error.

**Follow-ups:**

- *When do you need assisted injection?* When a constructor needs both objects from the graph and a value known only at runtime, such as an ID.

### 6.5 Testing with Hilt, and alternatives

**In one line:** in tests, replace production modules with test modules that bind fakes; outside Hilt, Koin and kotlin-inject are common choices.

**Say this in the interview:** "For instrumented tests I use `@HiltAndroidTest` and replace a module with `@TestInstallIn(replaces = [DataModule::class])`, which binds a fake repository for the whole test suite. For plain unit tests I don't need Hilt at all: I just call the constructor with fakes. As for alternatives, Koin is a runtime service locator with a simple DSL that works in Kotlin Multiplatform, but errors show up at runtime; Dagger and Hilt catch them at compile time."

**Example:**

```kotlin
@Module
@TestInstallIn(components = [SingletonComponent::class], replaces = [DataModule::class])
abstract class FakeDataModule {
    @Binds abstract fun repo(fake: FakeArticleRepository): ArticleRepository
}
```

**Common mistake:** Using Hilt in plain unit tests where calling the constructor with fakes is simpler.

**Follow-ups:**

- *Do unit tests need Hilt?* Usually not. With constructor injection, the test creates the class and passes fakes.

### 6.6 Entry points and WorkManager

**In one line:** use `@EntryPoint` when a class Hilt can't inject directly needs something from the graph, and `@HiltWorker` for WorkManager workers.

**Say this in the interview:** "Hilt can't generate code for classes it doesn't control, such as a `ContentProvider`, an App Startup `Initializer`, or a third-party library class. For those, I define an `@EntryPoint` interface installed in the right component, usually `SingletonComponent`, and fetch it with `EntryPointAccessors.fromApplication`. For WorkManager, I annotate the worker with `@HiltWorker`, use `@AssistedInject`, and configure `HiltWorkerFactory` in the Application class."

**Example:**

```kotlin
@EntryPoint
@InstallIn(SingletonComponent::class)
interface SyncEntryPoint { fun repository(): ArticleRepository }

val repo = EntryPointAccessors.fromApplication(context, SyncEntryPoint::class.java).repository()
```

**Common mistake:** Creating a custom `Worker` with `@Inject constructor` without `@HiltWorker` and `@AssistedInject`, so `Context` and `WorkerParameters` fail to bind.

**Follow-ups:**

- *When do you need `EntryPointAccessors`?* Whenever a class outside Hilt's supported Android types needs to pull a dependency from a Hilt component.

### Interview questions

1. **What is dependency injection, and what problem does it solve?** A class receives its dependencies instead of creating them. It makes code testable (swap in fakes), reusable, and gives clear control over object lifetimes. {Easy}
2. **Why prefer constructor injection over field injection?** Dependencies are visible and required, fields can be immutable, and tests can construct the class without a framework. Use field injection only for system-created classes like Activities. {Easy}
3. **`@Binds` or `@Provides`?** `@Binds` maps an interface to an implementation with an `@Inject` constructor and generates less code. `@Provides` is for objects you must build yourself, like Retrofit or third-party classes. {Easy}
4. **What does `@Singleton` mean in Hilt?** One instance per `SingletonComponent`, which lives as long as the app process. Unscoped bindings create a new instance every time they're injected. {Medium}
5. **How does Hilt create a ViewModel with dependencies?** `@HiltViewModel` makes Hilt generate a factory; `hiltViewModel()` or `by viewModels()` uses Hilt's ViewModel factory to build it from the `ViewModelComponent`. {Medium}
6. **How do you inject a runtime value, like an ID, along with graph dependencies?** Assisted injection: `@AssistedInject` on the constructor, `@Assisted` on the runtime parameter, and an `@AssistedFactory` interface the caller uses. {Medium}
7. **How do you provide two objects of the same type?** Define qualifier annotations, like `@IoDispatcher` and `@DefaultDispatcher`, and put them on both the provider and the injection point. {Easy}
8. **How do you replace a dependency with a fake in Hilt tests?** Use `@TestInstallIn(replaces = [...])` or `@UninstallModules` plus a test module that binds the fake. {Medium}
9. **Hilt or Koin?** Hilt (Dagger) checks the graph at compile time and is fast at runtime but needs code generation. Koin is simpler and multiplatform but resolves at runtime, so errors appear when the app runs. {Medium}
10. **What is the difference between DI and a service locator?** DI pushes dependencies in, so they're visible in the constructor. A service locator is pulled from inside the class, which hides dependencies and makes testing harder. {Easy}
11. **How do you inject dependencies into a class Hilt doesn't support directly, like a `ContentProvider`?** Define an `@EntryPoint` interface installed in `SingletonComponent` and retrieve it via `EntryPointAccessors.fromApplication(context, ...)`. {Medium}
