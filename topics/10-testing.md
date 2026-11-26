# Testing

A senior engineer sets the testing strategy for a team. Know which kind of test catches which bug, how to keep tests fast and reliable, and how to test coroutines and Compose.

### 10.1 The testing pyramid

**In one line:** most tests should be fast unit tests, fewer should be integration tests, and only a handful should be slow end-to-end UI tests.

**Say this in the interview:** "Unit tests on the JVM cover ViewModels, use cases, repositories and mappers; they run in milliseconds, so I write lots of them. Integration tests check pieces working together, like a DAO against an in-memory Room database or Retrofit against MockWebServer. A small set of UI tests covers the critical user journeys, and screenshot tests catch visual regressions. That balance gives fast feedback without a slow, flaky suite."

**Example:**

| Level | Share | Tests | Tools |
| --- | --- | --- | --- |
| Unit | ~70% | ViewModels, use cases, repositories, mappers | JUnit, coroutines-test, Turbine, Truth |
| Integration | ~20% | Room DAOs, repository + DB, API parsing | Robolectric, in-memory Room, MockWebServer |
| UI / end-to-end | ~10% | Critical journeys | Compose test, Espresso, Gradle Managed Devices |
| Screenshot | As needed | Design-system components | Roborazzi, Paparazzi |

**Common mistake:** Relying mostly on end-to-end tests, which are slow and tend to be flaky.

**Follow-ups:**

- *What belongs in an end-to-end test?* A few critical user journeys, where the parts must work together.

### 10.2 Fakes vs mocks

**In one line:** a fake is a simple working implementation, like an in-memory repository; a mock records calls so you can verify them.

**Say this in the interview:** "I prefer fakes for things like repositories, because tests then check behaviour, not implementation details, and they survive refactoring. Google recommends this too. I use mocks for collaborators whose only effect is being called, like analytics or loggers, where verifying the call is the point."

**Example:**

```kotlin
class FakeArticleRepository : ArticleRepository {
    private val articles = MutableStateFlow<List<Article>>(emptyList())
    var shouldFail = false
    fun emit(list: List<Article>) { articles.value = list }
    override fun observeAll() = articles
    override suspend fun refresh() = if (shouldFail) Result.failure(IOException()) else Result.success(Unit)
}

val analytics = mockk<Analytics>(relaxed = true)          // a mock where the call is what matters
verify { analytics.log(match { it.name == "checkout_success" }) }
```

**Common mistake:** Verifying every internal call with mocks, so tests break on harmless refactoring.

**Follow-ups:**

- *When is a mock the better choice?* When the important result is that a call happened, such as sending an analytics event.

### 10.3 Testing ViewModels and coroutines

**In one line:** replace `Dispatchers.Main` with a test dispatcher, run tests in `runTest`, and check flows with Turbine.

**Say this in the interview:** "A ViewModel uses `Dispatchers.Main`, which doesn't exist on the JVM, so a JUnit rule swaps it for a test dispatcher. `runTest` uses virtual time, so delays are skipped. `StandardTestDispatcher` lets me check intermediate states like 'loading' by advancing time myself; `UnconfinedTestDispatcher` runs everything eagerly when I only care about the end result. I inject all dispatchers so they share one test scheduler."

**Example:**

```kotlin
class MainDispatcherRule(val dispatcher: TestDispatcher = UnconfinedTestDispatcher()) : TestWatcher() {
    override fun starting(d: Description) = Dispatchers.setMain(dispatcher)
    override fun finished(d: Description) = Dispatchers.resetMain()
}

@Test fun `shows error when refresh fails`() = runTest {
    val repo = FakeArticleRepository().apply { shouldFail = true }
    val vm = ArticlesViewModel(repo)
    vm.uiState.test { assertNotNull(expectMostRecentItem().errorMessage) }
}
```

**Common mistake:** Using test dispatchers that don't share one scheduler, so virtual time doesn't control all the work.

**Follow-ups:**

- *Why does a ViewModel test need `Dispatchers.setMain`?* `viewModelScope` uses the main dispatcher, and a local JVM test has no Android main thread.

### 10.4 Integration tests: Room and the network

**In one line:** test the real Room and Retrofit setup against an in-memory database and a fake HTTP server.

**Say this in the interview:** "For Room I build an in-memory database and test DAOs directly, including that Flows emit after writes. For the network I use MockWebServer: it returns canned JSON or error codes, so I test the real Retrofit and serialization setup. That catches bugs fakes can't, like a wrong JSON field name or a missing query parameter."

**Example:**

```kotlin
@Test fun `parses articles and sends page parameter`() = runTest {
    server.enqueue(MockResponse().setBody("""[{"id":"1","title":"Hello","topic":"android","publishedAt":0}]"""))
    val result = api.getArticles(page = 2)
    assertEquals("Hello", result.single().title)
    assertEquals("/articles?page=2&size=20", server.takeRequest().path)
}
```

**Common mistake:** Faking the DAO in a test that is meant to check the real SQL.

**Follow-ups:**

- *Why use an in-memory Room database?* It runs real queries with a clean database for each test, without keeping data afterwards.

### 10.5 UI and screenshot tests

**In one line:** Compose UI tests find elements by semantics and interact with them; screenshot tests compare rendered components with saved images.

**Say this in the interview:** "Because my screens are stateless, I test them by passing fake state into `createComposeRule`, finding nodes by text or test tag, clicking, and asserting the callback fired. For visuals I use Roborazzi or Paparazzi on the JVM, recording golden images for each component in light, dark and large-font variants, and failing the PR if they change unexpectedly."

**Example:**

```kotlin
@Test fun showsArticleAndHandlesClick() {
    var clicked: String? = null
    compose.setContent { ArticlesScreen(state = ArticlesUiState(articles = listOf(ArticleUi("1", "Hello"))), onClick = { clicked = it }) }
    compose.onNodeWithText("Hello").assertIsDisplayed().performClick()
    assertEquals("1", clicked)
}
```

**Common mistake:** Finding nodes in ways tied to layout structure, so small UI changes break the tests.

**Follow-ups:**

- *What does a screenshot test miss?* Behaviour. It shows how something looks, so you still need tests that interact with it.

### 10.6 Testing process death

**In one line:** test that state restores after process death by building the ViewModel with a pre-filled `SavedStateHandle`, and by killing the app manually.

**Say this in the interview:** "`SavedStateHandle` is a plain class, so I can create one with saved values and check the ViewModel restores them. For `rememberSaveable` there's `StateRestorationTester` in Compose tests. And before a release I background the app, run `adb shell am kill`, and reopen it from Recents on every screen with user input."

**Example:**

```kotlin
@Test fun `restores step after process death`() {
    val vm = SignUpViewModel(SavedStateHandle(mapOf("step" to 2)))
    assertEquals(2, vm.step.value)
}
```

**Common mistake:** Treating rotation as the same test as process death.

**Follow-ups:**

- *What survives in `SavedStateHandle`?* Small saved values, such as an ID or a search query. Reload the larger data from them.

### 10.7 Test-driven development and flaky tests

**In one line:** TDD means writing a failing test, then the code to pass it, then refactoring; flaky tests come from time, shared state and real I/O.

**Say this in the interview:** "I use test-first for business rules, reducers and every bug fix: the test that reproduces the bug comes first, so it can never return. For UI layout I write tests after the design settles. Flaky tests usually come from real time, `Thread.sleep`, animations, shared state between tests or real network calls, so I inject clocks and dispatchers, use virtual time, disable animations and keep tests hermetic with fakes. I quarantine a flaky test and fix it, rather than retrying silently."

**Example:** fixing the bug "a full discount plus a coupon gives a negative total", test first:

```kotlin
// 1. Write a test that fails because of the bug
class TotalTest {
    @Test
    fun totalIsNeverNegative() {
        assertEquals(0, totalCents(priceCents = 500, discountPercent = 100, couponCents = 100))
    }
}

// 2. Make the smallest fix that passes it: coerceAtLeast(0)
fun totalCents(priceCents: Int, discountPercent: Int, couponCents: Int): Int =
    (priceCents * (100 - discountPercent) / 100 - couponCents).coerceAtLeast(0)

// 3. Refactor if needed, with the test still passing
```

**Common mistake:** Fixing a flaky test with a longer sleep or automatic retries.

**Follow-ups:**

- *What do you do with a flaky test?* Find the source of randomness, such as timing or shared state. If you must quarantine it, give it an owner and a fix.

### Interview questions

1. **Describe your testing strategy for an Android app.** Many fast unit tests for ViewModels and domain logic, integration tests for Room and the network, a few UI tests for critical journeys, and screenshot tests for the design system, all running in CI. {Medium}
2. **Fakes or mocks?** Fakes for repositories and data sources, because tests check behaviour and survive refactoring. Mocks when the call itself is what you verify, like analytics. {Easy}
3. **How do you test a ViewModel that uses `viewModelScope`?** Replace `Dispatchers.Main` with a test dispatcher in a JUnit rule, run the test in `runTest`, inject fakes, and assert on the `StateFlow` with Turbine. {Medium}
4. **`StandardTestDispatcher` or `UnconfinedTestDispatcher`?** Standard queues work until you advance time, so you can check intermediate states like loading. Unconfined runs eagerly, for tests where only the final state matters. {Medium}
5. **What does MockWebServer catch that a fake doesn't?** Real parsing and request problems: wrong JSON field names, missing query parameters, broken converters and HTTP error handling. {Medium}
6. **How do you test process death?** Build the ViewModel with a pre-filled `SavedStateHandle`, use `StateRestorationTester` for Compose, and manually kill the app with `adb shell am kill` before releases. {Medium}
7. **What makes tests flaky, and how do you fix it?** Real time and sleeps, animations, shared state, real network and unordered async work. Inject clocks and dispatchers, use virtual time, disable animations and keep tests hermetic. {Medium}
8. **Do you practise TDD?** Give an honest answer: test-first for business rules, reducers and bug fixes (the reproducing test comes first), and tests after the design settles for UI. {Easy}
9. **What code coverage do you aim for?** Coverage is a signal, not a target. Aim high on domain and ViewModel logic, cover critical journeys end to end, and use coverage to find untested branches. {Easy}
