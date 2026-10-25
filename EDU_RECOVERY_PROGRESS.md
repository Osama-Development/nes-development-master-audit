# NES EDU recovery progress

Status: all 94 planned source references were materialized and hash-verified. Static inspection covers 2,439 PHP occurrences, 371 SQL occurrences, 42 distinct SQL byte sets and 13 patch packages. No PHP application, migration or imported SQL was executed.

## Confirmed component evidence

- The mapping currently contains 28 candidate package states and 36 component occurrences across student and management families.
- V3.14 packages contain an `it-lms` student root and a separate `nes-admin` root. The administration bundle embeds a student snapshot rather than proving a single linear release.
- The embedded student view and standalone V3.12.1 share 262 relative paths but differ in six files affecting payment proof, bootstrap, student/logout flow, upload and download behavior. They are related forks, not byte-identical duplicates.
- The reviewed differences add isolated managed sessions, a view guard, actor auditing and an impersonation banner around shared student storage.
- A package named `FULL-NO-SQL` still includes original settings and an access-code file. Its raw archive is unsafe for public publication despite omitting SQL.
- The administration bootstrap expects `admin.local.php`, which is missing from the deployment root. Examples and original settings do not justify inventing deployable credentials.
- Authentication invokes a support migration path during login. This behavior is documented from static source reading only.

## Publication decision

Raw SQL, access codes, local configuration, user/student records and original sensitive settings remain private. Sanitized source states and schema-only derivatives require final review before a public repository or release is created.
