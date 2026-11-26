# Dependency injection

DI means a class receives its dependencies instead of creating them. Benefits: testability (swap fakes), reuse, and clear lifetimes.

### 6.1 Manual DI first

Know how to do it by hand; it shows you understand what the frameworks generate.

```kotlin
class AppContainer(context: Context) {
    private val okHttp = OkHttpClient.Builder().build()
    private val api = Retrofit.Builder().baseUrl(BASE).client(okHttp)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType())).build()
        .create(ArticleApi::class.java)
    private val db = Room.databaseBuilder(context, AppDb::class.java, "app.db").build()
    val articleRepository: ArticleRepository = OfflineFirstArticleRepository(api, db.articleDao())
}
```

### 6.2 Hilt (built on Dagger)

Compile-time, code-generated, Android-aware. Errors appear at build time, not at runtime.

```kotlin
@HiltAndroidApp class App : Application()

@AndroidEntryPoint class MainActivity : ComponentActivity()

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides @Singleton
    fun okHttp(authInterceptor: AuthInterceptor): OkHttpClient =
        OkHttpClient.Builder().addInterceptor(authInterceptor).build()

    @Provides @Singleton
    fun api(client: OkHttpClient): ArticleApi = Retrofit.Builder()
        .baseUrl("https://api.example.com/").client(client)
        .addConverterFactory(Json.asConverterFactory("application/json".toMediaType()))
        .build().create(ArticleApi::class.java)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {
    @Binds abstract fun bindRepo(impl: OfflineFirstArticleRepository): ArticleRepository
}
```

- `@Provides`: you write the construction code (third-party classes).
- `@Binds`: map an interface to an implementation with an `@Inject constructor` (cheaper, abstract).
- **Qualifiers:** `@Qualifier annotation class IoDispatcher` to provide two instances of the same type.
- **Assisted injection:** `@AssistedInject` + `@AssistedFactory` for runtime parameters; Hilt ViewModels get nav args via `SavedStateHandle` or `@HiltViewModel(assistedFactory = ...)`.
- **Entry points:** `@EntryPoint` to get dependencies in classes Hilt cannot inject (ContentProvider, some library callbacks).
- **WorkManager:** `@HiltWorker` with `@AssistedInject constructor`.

### 6.3 Components and scopes

| Component | Scope annotation | Lifetime |
| --- | --- | --- |
| SingletonComponent | `@Singleton` | Application |
| ActivityRetainedComponent | `@ActivityRetainedScoped` | Survives config change |
| ViewModelComponent | `@ViewModelScoped` | One ViewModel |
| ActivityComponent | `@ActivityScoped` | One Activity instance |
| FragmentComponent | `@FragmentScoped` | One Fragment |
| ServiceComponent | `@ServiceScoped` | One Service |

Unscoped bindings create a **new instance every injection**. Scope only when you need shared state or the object is expensive; each scope holds memory and needs synchronisation.

### 6.4 Testing with Hilt

```kotlin
@HiltAndroidTest
@UninstallModules(DataModule::class)
class ArticlesScreenTest {
    @get:Rule val hilt = HiltAndroidRule(this)

    @Module @InstallIn(SingletonComponent::class)
    abstract class FakeDataModule {
        @Binds abstract fun repo(fake: FakeArticleRepository): ArticleRepository
    }
}
```

Or use `@TestInstallIn(components = [...], replaces = [DataModule::class])` once for the whole test source set.

### 6.5 Koin and alternatives

- **Koin:** a runtime service locator with a DSL; no codegen, quick to set up, works in Kotlin Multiplatform. Errors are found at runtime (mitigate with `verify()` tests). Koin Annotations adds compile-time checking.
- **Dagger (plain):** more control, used in large multi-module apps; more boilerplate.
- **kotlin-inject / Metro:** compile-time, KMP-friendly options.

### 6.6 Deeper dive: what Dagger and Hilt generate

For a class with an `@Inject` constructor, Dagger generates a factory at compile time:

```kotlin
class ArticleRepository @Inject constructor(private val api: ArticleApi, private val dao: ArticleDao)

// Generated (simplified, Java in reality)
class ArticleRepository_Factory(
    private val api: Provider<ArticleApi>,
    private val dao: Provider<ArticleDao>
) : Factory<ArticleRepository> {
    override fun get() = ArticleRepository(api.get(), dao.get())
}
```

The component wires these factories into a graph. A `@Singleton` binding is wrapped in `DoubleCheck`, which creates the object once with double-checked locking. Because the graph is checked at compile time, a missing binding fails the build with a message like `[Dagger/MissingBinding] ArticleApi cannot be provided without an @Provides-annotated method`, instead of crashing a user's app.

Hilt adds generated base classes: `@AndroidEntryPoint class MainActivity` really extends `Hilt_MainActivity`, which injects fields in `onCreate`.

### 6.7 Deeper dive: qualifiers for dispatchers and scopes

```kotlin
@Qualifier @Retention(AnnotationRetention.BINARY) annotation class IoDispatcher
@Qualifier @Retention(AnnotationRetention.BINARY) annotation class DefaultDispatcher
@Qualifier @Retention(AnnotationRetention.BINARY) annotation class ApplicationScope

@Module @InstallIn(SingletonComponent::class)
object CoroutinesModule {
    @Provides @IoDispatcher fun io(): CoroutineDispatcher = Dispatchers.IO
    @Provides @DefaultDispatcher fun default(): CoroutineDispatcher = Dispatchers.Default

    @Provides @Singleton @ApplicationScope
    fun appScope(@DefaultDispatcher d: CoroutineDispatcher): CoroutineScope = CoroutineScope(SupervisorJob() + d)
}

class SyncRepository @Inject constructor(
    @IoDispatcher private val io: CoroutineDispatcher,
    @ApplicationScope private val appScope: CoroutineScope   // for work that must outlive a screen
)
```

In tests, replace `CoroutinesModule` with one that returns a `StandardTestDispatcher`.

### 6.8 Deeper dive: assisted injection for runtime values

Some dependencies come from the graph, others only exist at runtime (an ID, a callback):

```kotlin
class ArticleExporter @AssistedInject constructor(
    private val repo: ArticleRepository,        // from the graph
    @Assisted private val articleId: String     // supplied by the caller
) {
    @AssistedFactory interface Factory { fun create(articleId: String): ArticleExporter }
}

class ShareViewModel @Inject constructor(private val exporterFactory: ArticleExporter.Factory) : ViewModel() {
    fun export(id: String) = viewModelScope.launch { exporterFactory.create(id).export() }
}
```

For ViewModels, Hilt supports the same idea:

```kotlin
@HiltViewModel(assistedFactory = DetailViewModel.Factory::class)
class DetailViewModel @AssistedInject constructor(
    @Assisted val id: String,
    private val repo: ArticleRepository
) : ViewModel() {
    @AssistedFactory interface Factory { fun create(id: String): DetailViewModel }
}

val vm = hiltViewModel<DetailViewModel, DetailViewModel.Factory> { it.create(articleId) }
```

### 6.9 Deeper dive: multibindings for plug-in style features

Collect many implementations into a `Set` or `Map` without a central list. Useful for app initializers, analytics trackers or deep-link handlers contributed by different modules.

```kotlin
interface AppInitializer { fun init(app: Application) }

// In :core:analytics
@Module @InstallIn(SingletonComponent::class)
abstract class AnalyticsInitModule {
    @Binds @IntoSet abstract fun bind(i: AnalyticsInitializer): AppInitializer
}

// In :core:logging
@Module @InstallIn(SingletonComponent::class)
abstract class LoggingInitModule {
    @Binds @IntoSet abstract fun bind(i: TimberInitializer): AppInitializer
}

@HiltAndroidApp
class App : Application() {
    @Inject lateinit var initializers: Set<@JvmSuppressWildcards AppInitializer>
    override fun onCreate() { super.onCreate(); initializers.forEach { it.init(this) } }
}
```

Adding a new module that contributes an initializer requires no change to `App`. `@IntoMap` with a `@StringKey` works the same way for keyed lookups.

### Interview questions

1. **DI vs service locator?** With DI, dependencies are pushed in through the constructor and are visible in the signature. A service locator is pulled from inside the class, which hides dependencies and makes testing harder. {Easy}
2. **Why is constructor injection preferred over field injection?** Dependencies are explicit, the object is valid when constructed, fields can be `val`, and tests can build it without the framework. Field injection is only for framework-created classes (Activity, Fragment). {Easy}
3. **How does Hilt get a ViewModel with dependencies?** `@HiltViewModel` generates a factory registered in a map; `hiltViewModel()` / `by viewModels()` uses `HiltViewModelFactory`, which builds it from the `ViewModelComponent`. {Hard}
4. **What does `@Singleton` on an unscoped module function mean?** That binding is created once per `SingletonComponent`, i.e. once per app process. It is not a Java static singleton; tests get a fresh component. {Medium}
