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

### 8.5 Deeper dive: chaining workers for a photo upload

Compress, then upload, then clean up, where each step only runs if the previous one succeeded:

```kotlin
val input = workDataOf("uri" to photoUri.toString())

val compress = OneTimeWorkRequestBuilder<CompressWorker>().setInputData(input).build()
val upload = OneTimeWorkRequestBuilder<UploadWorker>()
    .setConstraints(Constraints(requiredNetworkType = NetworkType.CONNECTED))
    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
    .build()
val cleanup = OneTimeWorkRequestBuilder<CleanupWorker>().build()

WorkManager.getInstance(context)
    .beginUniqueWork("upload-$photoId", ExistingWorkPolicy.KEEP, compress)
    .then(upload)        // receives CompressWorker's output Data as its input
    .then(cleanup)
    .enqueue()
```

If `compress` fails, `upload` and `cleanup` are marked failed too. Unique work with `KEEP` prevents the same photo being uploaded twice if the user taps again.

Observing progress in the UI:

```kotlin
val info by WorkManager.getInstance(context)
    .getWorkInfosForUniqueWorkFlow("upload-$photoId")
    .collectAsStateWithLifecycle(initialValue = emptyList())
```

### 8.6 Deeper dive: a foreground service, complete

A workout tracker that records location while the screen is off:

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />
<service android:name=".TrackingService" android:foregroundServiceType="location" android:exported="false" />
```

```kotlin
@AndroidEntryPoint
class TrackingService : LifecycleService() {
    @Inject lateinit var tracker: LocationTracker

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val notification = NotificationCompat.Builder(this, CHANNEL_TRACKING)
            .setContentTitle("Recording your run")
            .setSmallIcon(R.drawable.ic_run)
            .setOngoing(true)
            .addAction(R.drawable.ic_stop, "Stop", stopPendingIntent())
            .build()
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        lifecycleScope.launch { tracker.locations().collect { saveToDb(it) } }
        return START_STICKY
    }
}

// Start it from the UI, while the app is visible
ContextCompat.startForegroundService(context, Intent(context, TrackingService::class.java))
```

Points to mention: request location permission (and `POST_NOTIFICATIONS` on Android 13+) before starting; the user can stop it from the notification; save points to Room so nothing is lost if the process dies; return `START_STICKY` only if restarting makes sense.

### 8.7 Deeper dive: exact alarms done right

```kotlin
val alarmManager = context.getSystemService<AlarmManager>()!!
if (Build.VERSION.SDK_INT >= 31 && !alarmManager.canScheduleExactAlarms()) {
    context.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM))   // ask the user
    return
}
val pi = PendingIntent.getBroadcast(
    context, reminder.id.hashCode(),
    Intent(context, ReminderReceiver::class.java).putExtra("id", reminder.id),
    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
)
alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, reminder.timeMillis, pi)
```

Alarms are cleared on reboot, so also listen for `BOOT_COMPLETED` and reschedule from the database. Use exact alarms only for user-visible, time-critical features (alarm clocks, calendar reminders); everything else should use inexact alarms or WorkManager.

### 8.8 Deeper dive: push-triggered sync

Sending the whole payload in a push message is fragile (size limits, ordering, missed messages). A robust pattern is "tickle and sync":

```kotlin
class AppMessagingService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        when (message.data["type"]) {
            "sync" -> WorkManager.getInstance(this).enqueueUniqueWork(
                "sync", ExistingWorkPolicy.REPLACE,
                OneTimeWorkRequestBuilder<SyncWorker>().setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST).build()
            )
        }
    }
    override fun onNewToken(token: String) { /* send the new token to your backend */ }
}
```

The push only says "something changed"; the worker fetches the real data with the last sync cursor. Missed or duplicate pushes do no harm because the sync is idempotent.

### Interview questions

1. **Why not just use a background Service for syncing?** Background services are killed within about a minute after the app leaves the foreground (Android 8+). WorkManager is the supported, battery-friendly path. {Easy}
2. **Does WorkManager guarantee exact timing?** No. It guarantees eventual execution when constraints are met. Periodic work has a 15-minute minimum and can drift. {Easy}
3. **What happens to WorkManager work if the user force-stops the app?** It is cancelled and does not run until the app is opened again; force-stop clears scheduled jobs and alarms. {Medium}
4. **How do you report progress from a worker?** `setProgress(workDataOf("progress" to 40))` and observe `WorkInfo.progress` from the UI. {Medium}
