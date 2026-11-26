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

### Interview questions

1. **DI vs service locator?** With DI, dependencies are pushed in through the constructor and are visible in the signature. A service locator is pulled from inside the class, which hides dependencies and makes testing harder. {Easy}
2. **Why is constructor injection preferred over field injection?** Dependencies are explicit, the object is valid when constructed, fields can be `val`, and tests can build it without the framework. Field injection is only for framework-created classes (Activity, Fragment). {Easy}
3. **How does Hilt get a ViewModel with dependencies?** `@HiltViewModel` generates a factory registered in a map; `hiltViewModel()` / `by viewModels()` uses `HiltViewModelFactory`, which builds it from the `ViewModelComponent`. {Hard}
4. **What does `@Singleton` on an unscoped module function mean?** That binding is created once per `SingletonComponent`, i.e. once per app process. It is not a Java static singleton; tests get a fresh component. {Medium}
