# Design

## `catalogue/models.py`

**Summary:** The data model follows one request from start to finish. A user from an institution asks for a specific version of a code package and states the purpose. A reviewer approves or rejects it. Every step goes into an audit log. I put the important rules in the database itself. Versions are unique per package. An approved or rejected request must record who reviewed it and when. I use PROTECT on every foreign key, so history cannot disappear. Each version stores a SHA-256 checksum, so users can confirm the file is exactly what I released. The audit log is append-only at the model level. In production, I would also lock it at the database level.

**Key decisions:**

- The `CheckConstraint` on `AccessRequest` refuses a decision with no reviewer attached. Accountability lives in the data layer, below the application code.
- Users who leave are deactivated (`is_active = False`), never deleted, so their name stays on every action they took.
- A partial index covers only pending requests, because reviewers mostly search for those. `AuditLog.timestamp` is indexed for date-range audits.

## Known limitations

- **`catalogue/models.py`: bulk changes can bypass the audit log protection.** Django bulk operations, such as `AuditLog.objects.all().delete()` or `.update()`, skip the model methods. Raw SQL skips them too. The model methods stop accidental changes in the application. In production, I would add database-level controls, for example a PostgreSQL trigger, or a database role with INSERT-only permission on the audit table.
- **`catalogue/models.py`: `is_restricted` is not enforced yet.** The database stores the flag, the admin shows it, and the API returns it, but the approval process does not check it. Next step: only reviewers with a dedicated permission can approve restricted packages.
