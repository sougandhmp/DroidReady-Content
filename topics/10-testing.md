# Testing strategy

A senior defines the testing strategy for the team, not just writes tests. Know the pyramid, what each layer catches, and how to keep tests fast and reliable.

### 10.1 The pyramid

| Level | Runs on | Speed | What to test | Tools |
| --- | --- | --- | --- | --- |
| Unit (\~70%) | JVM | ms | ViewModels, use cases, repositories, mappers | JUnit, kotlinx-coroutines-test, Turbine, MockK, Truth |
| Integration (\~20%) | JVM (Robolectric) or device | s | Room DAOs, repository + DB, navigation | Robolectric, in-memory Room, MockWebServer |
| UI / E2E (\~10%) | Device / emulator | s-min | Critical user journeys | Compose test, Espresso, UI Automator, Gradle Managed Devices |
| Screenshot | JVM | s | Visual regressions in components | Paparazzi, Roborazzi, Compose Preview Screenshot Testing |

### 10.2 Fakes vs mocks

- **Fake:** a working lightweight implementation (in-memory repository). Tests behaviour, survives refactors. Google recommends fakes.
- **Mock:** records and verifies calls (`verify { api.get() }`). Useful for checking interactions with things you do not own; over-use couples tests to implementation.

```kotlin
class FakeArticleRepository : ArticleRepository {
    private val articles = MutableStateFlow<List<Article>>(emptyList())
    var shouldFail = false
    fun emit(list: List<Article>) { articles.value = list }
    override fun observeAll() = articles
    override suspend fun refresh() = if (shouldFail) Result.failure(IOException()) else Result.success(Unit)
}
```

### 10.3 ViewModel test with coroutines

```kotlin
class MainDispatcherRule(val dispatcher: TestDispatcher = UnconfinedTestDispatcher()) : TestWatcher() {
    override fun starting(d: Description) = Dispatchers.setMain(dispatcher)
    override fun finished(d: Description) = Dispatchers.resetMain()
}

class ArticlesViewModelTest {
    @get:Rule val mainRule = MainDispatcherRule()
    private val repo = FakeArticleRepository()

    @Test fun `shows error when refresh fails`() = runTest {
        repo.shouldFail = true
        val vm = ArticlesViewModel(GetArticlesUseCase(repo), RefreshArticlesUseCase(repo))
        vm.uiState.test {
            val state = expectMostRecentItem()
            assertThat(state.errorMessage).isNotNull()
        }
    }
}
```

### 10.4 Room and network integration tests

```kotlin
@RunWith(AndroidJUnit4::class)
class ArticleDaoTest {
    private lateinit var db: AppDb
    @Before fun setUp() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), AppDb::class.java).build()
    }
    @After fun tearDown() = db.close()

    @Test fun upsertThenObserve() = runTest {
        db.articleDao().upsertAll(listOf(entity("1")))
        assertThat(db.articleDao().observeAll().first()).hasSize(1)
    }
}
```

For network code, use **MockWebServer** to return canned JSON, error codes and slow responses, testing the real Retrofit + serializer setup.

### 10.5 Compose UI test

```kotlin
@get:Rule val compose = createComposeRule()

@Test fun showsArticlesAndHandlesClick() {
    var clicked: String? = null
    compose.setContent {
        ArticlesScreen(state = ArticlesUiState(articles = listOf(ArticleUi("1", "Hello"))), onClick = { clicked = it })
    }
    compose.onNodeWithText("Hello").assertIsDisplayed().performClick()
    assertEquals("1", clicked)
}
```

### 10.6 Flaky tests and CI

- Causes: real time / `Thread.sleep`, shared state between tests, animations, network, unordered async work.
- Fixes: inject dispatchers and clocks, `runTest` virtual time, idling resources / `waitUntil`, disable animations, hermetic tests with fakes, Gradle Managed Devices for consistent emulators, test orchestrator to isolate state.
- Quarantine and track flaky tests rather than retrying silently.

### Interview questions

1. **What makes code testable?** Constructor injection, interfaces at boundaries, no hidden statics, injected dispatchers/clocks, pure functions for logic, stateless UI. {Easy}
2. **How do you test a Flow that emits several values over time?** Turbine (`test { awaitItem() }`) inside `runTest`; or collect into a list in `backgroundScope`. {Medium}
3. **What is your target code coverage?** Coverage is a signal, not a goal. Aim for high coverage on domain and ViewModel logic, test critical journeys end to end, and use coverage to find untested branches, not to hit a number. {Easy}
4. **Robolectric vs instrumented tests?** Robolectric runs Android framework code on the JVM (fast, good for CI); instrumented tests run on a real device (accurate, slower). Use both: Robolectric for most, a small device suite for critical paths. {Medium}
