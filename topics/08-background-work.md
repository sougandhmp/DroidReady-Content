# Background work

Android aggressively limits background execution to save battery. Pick the tool by **who started the work, whether it must finish, and whether it needs an exact time**.

### 8.1 Choosing the right API

| Need | Use | Example |
| --- | --- | --- |
| Short work while the app is open | Coroutine in `viewModelScope` / app scope | Load a screen |
| Deferrable work that must complete, even after reboot | **WorkManager** | Upload photos, sync, send analytics |
| Long work the user is aware of, now | **Foreground service** with a notification | Music, navigation, an active call, workout tracking |
| User-initiated data transfer | WorkManager expedited / user-initiated data transfer job (Android 14+) | Large file download the user tapped |
| Exact time | `AlarmManager.setExactAndAllowWhileIdle` (needs `SCHEDULE_EXACT_ALARM` or `USE_EXACT_ALARM`) | Alarm clock, calendar reminder |
| Server-driven | FCM high-priority message → WorkManager | New message sync |

### 8.2 WorkManager

Persists work in its own database, respects constraints, retries with backoff, and survives process death and reboot.

```kotlin
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted ctx: Context,
    @Assisted params: WorkerParameters,
    private val repo: ArticleRepository
) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result =
        if (repo.refresh().isSuccess) Result.success()
        else if (runAttemptCount < 3) Result.retry() else Result.failure()
}

val request = PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS)   // minimum 15 min
    .setConstraints(Constraints(requiredNetworkType = NetworkType.UNMETERED, requiresBatteryNotLow = true))
    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
    .build()

WorkManager.getInstance(context)
    .enqueueUniquePeriodicWork("sync", ExistingPeriodicWorkPolicy.KEEP, request)
```

Also know: chaining (`beginWith(a).then(b)`), unique work policies (`KEEP`, `REPLACE`, `APPEND`), input/output `Data` (small, < 10 KB), observing with `getWorkInfoByIdFlow`, `setExpedited()` for important short work, and `setForeground()` for long-running work.

### 8.3 Foreground services

- Must show a notification within \~5 s of `startForegroundService`.
- Since Android 14 you must declare a **`foregroundServiceType`** (`mediaPlayback`, `location`, `dataSync`, `camera`, `health`, `shortService`...) plus the matching permission, and Play reviews the declaration.
- Apps cannot start foreground services from the background (Android 12+), with a few exemptions (e.g. high-priority FCM, exact alarms).
- Android 15 limits `dataSync` foreground services to about 6 hours per 24 h; prefer WorkManager for syncs.

### 8.4 Doze, App Standby and buckets

- **Doze:** when the device is idle and unplugged, network and wakelocks are deferred to maintenance windows; alarms are delayed unless `AllowWhileIdle`.
- **App Standby Buckets:** active, working set, frequent, rare, restricted. Rarely used apps get fewer jobs and alarms.
- Test with `adb shell dumpsys deviceidle force-idle` and `adb shell am set-standby-bucket <pkg> rare`.

### Interview questions

1. **Why not just use a background Service for syncing?** Background services are killed within about a minute after the app leaves the foreground (Android 8+). WorkManager is the supported, battery-friendly path. {Easy}
2. **Does WorkManager guarantee exact timing?** No. It guarantees eventual execution when constraints are met. Periodic work has a 15-minute minimum and can drift. {Easy}
3. **What happens to WorkManager work if the user force-stops the app?** It is cancelled and does not run until the app is opened again; force-stop clears scheduled jobs and alarms. {Medium}
4. **How do you report progress from a worker?** `setProgress(workDataOf("progress" to 40))` and observe `WorkInfo.progress` from the UI. {Medium}
